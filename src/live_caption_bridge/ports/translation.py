from typing import Protocol

# from live_caption_bridge.domain.models import Caption

class TranslationResult:
    def __init__ (
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        uncertain: bool = False,
    ) -> None:
        self.text = text
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.uncertain = uncertain

class TranslationPort(Protocol):
    def translate(self, text: str, source_lang: str, target_lang: str) -> TranslationResult:
        ...

class TranslationValidationError(ValueError):
    ...


def validate_result(result: TranslationResult) -> None:
    if not result.text or not result.text.strip():
        raise TranslationValidationError("texto vazio")
    if not result.source_lang or not result.target_lang:
        raise TranslationValidationError("idioma ausente")
    if result.source_lang == result.target_lang:
        raise TranslationValidationError("idioma destino igual à origem")
    # ensure uncertain is exactly a bool (not an int or other subclass)
    if type(result.uncertain) is not bool:
        raise TranslationValidationError("uncertain deve ser bool")
