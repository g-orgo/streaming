from live_caption_bridge.infrastructure.settings import Settings


def test_default_values() -> None:
    s = Settings()
    assert s.sample_rate == 16000
    assert s.replay_seconds == 120
    assert s.channels == 1


def test_rejects_invalid_sample_rate() -> None:
    s = Settings(sample_rate=12345)
    import pytest
    with pytest.raises(ValueError):
        s.validate_settings()
