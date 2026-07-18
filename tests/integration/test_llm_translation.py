import pytest
import httpx

from live_caption_bridge.adapters.llm_translation import LLMTranslation


@pytest.fixture
def fake_ollama(httpserver) -> httpx.URL: # type: ignore
    httpserver.expect_ordered_request("/api/generate").respond_with_json( # type: ignore
        {"response": '{"translated": "olá"}'}
    )
    return httpserver.url_for("/api/generate") # type: ignore


def test_translation_against_fake_server(fake_ollama: httpx.URL) -> None:
    t = LLMTranslation(url=str(fake_ollama), model="test", timeout_s=5.0)
    result = t.translate("hello", "en", "pt")
    assert result.text == "olá"
    assert result.uncertain is False


def test_fallback_on_server_error(fake_ollama: httpx.URL) -> None:
    t = LLMTranslation(url=str(fake_ollama) + "/invalid", model="test", timeout_s=5.0)
    result = t.translate("hello", "en", "pt")
    assert result.text == "hello"
    assert result.uncertain is True

def test_retry_on_429(fake_ollama: httpx.URL, httpserver) -> None: # type: ignore
    httpserver.expect_ordered_request("/api/generate").respond_with_data( # type: ignore
        status=429
    )
    httpserver.expect_ordered_request("/api/generate").respond_with_json( # type: ignore
        {"response": '{"translated": "olá"}'}
    )
    t = LLMTranslation(url=str(fake_ollama), model="test", timeout_s=5.0)
    result = t.translate("hello", "en", "pt")
    assert result.text == "olá"
