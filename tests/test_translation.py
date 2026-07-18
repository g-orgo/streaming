import pytest

from live_caption_bridge.ports.translation import (
    TranslationPort,
    TranslationResult,
    TranslationValidationError,
    validate_result,
    
)


class FakeTranslation:
    def __init__(self) -> None:
        self._map: dict[tuple[str, str, str], TranslationResult] = {}

    def add(
        self, text: str, src: str, tgt: str, result: TranslationResult
    ) -> None:
        self._map[(text, src, tgt)] = result

    def translate(
        self, text: str, source_lang: str, target_lang: str
    ) -> TranslationResult:
        key = (text, source_lang, target_lang)
        return self._map.get(
            key,
            TranslationResult(
                text=text,
                source_lang=source_lang,
                target_lang=target_lang,
                uncertain=True,
            ),
        )


def test_fake_translates_en_to_pt() -> None:
    t: TranslationPort = FakeTranslation()
    result = t.translate("hello", "en", "pt")
    assert result.text == "hello"
    assert result.source_lang == "en"
    assert result.target_lang == "pt"
    assert result.uncertain is True


def test_fake_returns_mapped_text() -> None:
    f = FakeTranslation()
    f.add("hello", "en", "pt", TranslationResult("olá", "en", "pt"))
    result = f.translate("hello", "en", "pt")
    assert result.text == "olá"
    assert result.uncertain is False


def test_rejects_empty_text() -> None:
    r = TranslationResult("", "en", "pt")
    with pytest.raises(TranslationValidationError, match="vazio"):
        validate_result(r)


def test_rejects_missing_language() -> None:
    r = TranslationResult("hello", "", "pt")
    with pytest.raises(TranslationValidationError, match="ausente"):
        validate_result(r)


def test_rejects_same_language() -> None:
    r = TranslationResult("hello", "en", "en")
    with pytest.raises(TranslationValidationError, match="igual"):
        validate_result(r)


def test_passes_valid_result() -> None:
    r = TranslationResult("olá", "en", "pt")
    validate_result(r)
