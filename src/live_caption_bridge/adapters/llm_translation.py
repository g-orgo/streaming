import logging
import os
import time
from functools import wraps
from typing import Any, Callable, TypeVar, cast

import httpx

from live_caption_bridge.ports.translation import (
    # TranslationPort,
    TranslationResult,
    TranslationValidationError,
    validate_result,
)


F = TypeVar("F", bound=Callable[..., Any])


logger = logging.getLogger(__name__)

def _build_prompt(text: str, target_lang:str) -> str:
    return (
        f"Translate the following text to: {target_lang}"
        f"Respond ONLY with a JSON object containing "
        f'{{"translated": "<translated text>"}}. Text: {text}'
    )

def _retry(max_attempts: int = 2, delay_s: float = 0.5) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last: BaseException | None = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in (429, 502, 503, 504):
                        last = e
                        if attempt < max_attempts - 1:
                            time.sleep(delay_s * (attempt + 1))
                            continue
                    raise
            if last is not None:
                raise last
        return cast(F, wrapper)
    return decorator

class LLMTranslation:
    def __init__(
        self,
        url: str | None = None,
        model: str | None = None,
        timeout_s: float = 15.0
    ) -> None:
        self._url = url if url is not None else os.getenv("LCB_LLM_URL", "http://localhost:11434/api/generate")
        self._model = model if model is not None else os.getenv("LCB_LLM_MODEL", "qwen3:4b")
        self._timeout = timeout_s
        self._client = httpx.Client(timeout=httpx.Timeout(self._timeout))

    @_retry()
    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str
    ) -> TranslationResult:
        prompt = _build_prompt(text, target_lang)
        payload : dict[str, str | bool] = {"model": self._model, "prompt": prompt, "stream": False}
        logger.debug(f"Enviando tradução para {self._url}")
        try:
            resp = self._client.post(self._url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            raw = data.get("response", "")
        except httpx.HTTPStatusError as err:
            if err.response.status_code in (429, 502, 503, 504):
                raise
            logger.warning(f"Erro HTTP ao chamar LLM: {err.response.status_code} - {err}")
            return TranslationResult(text, source_lang, target_lang, uncertain=True)
        except (httpx.RequestError, ValueError) as err:
            logger.warning(f"Falha na requisição: {err}")
            return TranslationResult(text, source_lang, target_lang, uncertain=True)
        import json as _json
        try:
            parsed = _json.loads(raw)
            translated = parsed.get("translated", raw)
        except (_json.JSONDecodeError, TypeError):
            translated = raw.strip()
        if not translated:
            translated = text
        result = TranslationResult(translated, source_lang, target_lang)
        try:
            validate_result(result)
        except TranslationValidationError:
            return TranslationResult(text, source_lang, target_lang, uncertain=True)
        return result
    
