from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "LCB_"}

    llm_url: str = "http://localhost:11434/api/generate"
    llm_model: str = "qwen3:4b"
    sample_rate: int = 16000
    channels: int = 1
    replay_seconds: int = 120
    data_dir: Path = Path.home() / ".live_caption_bridge"

    def validate_settings(self) -> None:
        if self.sample_rate not in (8000, 16000, 44100, 48000):
            raise ValueError(f"sample_rate inválido: {self.sample_rate}")
        if self.channels < 1 or self.channels > 2:
            raise ValueError(f"channels inválido: {self.channels}")
        if self.replay_seconds < 10 or self.replay_seconds > 600:
            raise ValueError(f"replay_seconds deve estar entre 10 e 600")