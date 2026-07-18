from live_caption_bridge.adapters.llm_translation import LLMTranslation

t = LLMTranslation()
result = t.translate("Hello, how are you?", "en", "pt")
print(f"Tradução: {result.text}")
print(f"Incerteza: {result.uncertain}")
