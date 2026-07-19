import ctypes
from ctypes import wintypes

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000

_user32 = ctypes.windll.user32


class WindowsHotKey:
    def __init__(self) -> None:
        self._next_id = 1

    def register(self, mod: int, vk: int) -> int:
        hwnd = None
        fid = self._next_id
        if not _user32.RegisterHotKey(hwnd, fid, mod, vk):
            raise RuntimeError(f"RegisterHotKey falhou para id {fid}")
        self._next_id += 1
        return fid

    def unregister(self, id: int) -> None:
        hwnd = None
        _user32.UnregisterHotKey(hwnd, id)

    @staticmethod
    def listen(timeout_ms: int = 100) -> int | None:
        msg = wintypes.MSG()
        result = _user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if result == 0:
            return None
        if msg.message == WM_HOTKEY:
            return msg.wParam
        _user32.TranslateMessage(ctypes.byref(msg))
        _user32.DispatchMessageW(ctypes.byref(msg))
        return None
