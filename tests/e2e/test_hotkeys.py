import pytest

pytestmark = pytest.mark.hotkey


def test_register_and_unregister_does_not_raise() -> None:
    from live_caption_bridge.adapters.windows_hotkeys import WindowsHotKey
    hk = WindowsHotKey()
    fid = hk.register(0, 0x70)  # F1 sem mod
    hk.unregister(fid)
