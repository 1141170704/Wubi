# -*- coding: utf-8 -*-
"""
Win32 API 封装（纯 ctypes，零第三方依赖）。

提供四组能力：
  · 全局热键      RegisterHotKey / 消息循环
  · 窗口焦点      记住唤出面板前的窗口，上屏后切回去
  · 模拟按键      发送 Ctrl+V 完成自动粘贴
  · 剪贴板        读写文本

自动粘贴的原理：
  1) 热键触发时，先记下当前前台窗口 HWND（那才是用户真正在打字的地方）；
  2) 面板弹出（自己变成前台）；
  3) 用户选词 → 文本写入剪贴板 → 把焦点还给步骤 1 的窗口 → 发 Ctrl+V。
"""
import ctypes
import sys
import time

IS_WIN = (sys.platform == 'win32')

if IS_WIN:
    import ctypes.wintypes as wt

    user32 = ctypes.WinDLL('user32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
else:
    # 非 Windows：给出空壳，让模块仍可被导入（程序会在入口处提示并退出），
    # 也便于在其它平台上做纯逻辑自测。
    class _Stub:
        """接受任意属性读写与调用，一律返回 0/None"""

        def __init__(self, *a, **k):
            pass

        def __getattr__(self, n):
            return _Stub()

        def __setattr__(self, n, v):
            pass

        def __call__(self, *a, **k):
            return 0

    class _StubModule:
        def __getattr__(self, n):
            return _Stub()

    user32 = _StubModule()
    kernel32 = _StubModule()

    class _FakeWintypes:
        def __getattr__(self, n):
            return _Stub

    wt = _FakeWintypes()

    def _unsupported(*a, **k):
        return False

    globals()['_stub_call'] = _unsupported

# ---------------------------------------------------------------- 常量
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_CONTROL = 0x11
VK_MENU = 0x12          # Alt
VK_SHIFT = 0x10
VK_LWIN = 0x5B

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

# 虚拟键码：0-9 A-Z
def vk_of(ch):
    ch = ch.upper()
    if len(ch) == 1 and ch.isdigit():
        return ord(ch)
    if len(ch) == 1 and 'A' <= ch <= 'Z':
        return ord(ch)
    return 0


if IS_WIN:
    class KbdInput(ctypes.Structure):
        _fields_ = [('wVk', wt.WORD),
                    ('wScan', wt.WORD),
                    ('dwFlags', wt.DWORD),
                    ('time', wt.DWORD),
                    ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))]


    class MouseInput(ctypes.Structure):
        _fields_ = [('dx', wt.LONG), ('dy', wt.LONG),
                    ('mouseData', wt.DWORD), ('dwFlags', wt.DWORD),
                    ('time', wt.DWORD), ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))]


    class HardwareInput(ctypes.Structure):
        _fields_ = [('uMsg', wt.DWORD), ('wParamL', wt.WORD), ('wParamH', wt.WORD)]


    class _InputUnion(ctypes.Union):
        _fields_ = [('ki', KbdInput), ('mi', MouseInput), ('hi', HardwareInput)]


    class Input(ctypes.Structure):
        _anonymous_ = ('u',)
        _fields_ = [('type', wt.DWORD), ('u', _InputUnion)]


    class Msg(ctypes.Structure):
        _fields_ = [('hwnd', wt.HWND), ('message', wt.UINT),
                    ('wParam', wt.WPARAM), ('lParam', wt.LPARAM),
                    ('time', wt.DWORD), ('pt', wt.POINT),
                    ('lPrivate', wt.DWORD)]



else:
    # 非 Windows：占位类，保证模块可导入、函数可调用（一律无效果）
    class _Nested:
        """占位：接受任意属性赋值，模拟 ctypes 的 ki/mi/hi 联合体成员"""

        def __setattr__(self, n, v):
            object.__setattr__(self, n, v)

        def __getattr__(self, n):
            return _Nested()

    class Input:
        def __init__(self, *a, **k):
            self.type = 0
            self.ki = _Nested()
            self.mi = _Nested()
            self.hi = _Nested()

    class Msg:
        def __init__(self, *a, **k):
            self.wParam = 0

if IS_WIN:
    SendInput = user32.SendInput
    SendInput.argtypes = (wt.UINT, ctypes.POINTER(Input), ctypes.c_int)
    SendInput.restype = wt.UINT

    user32.RegisterHotKey.argtypes = [wt.HWND, ctypes.c_int, wt.UINT, wt.UINT]
    user32.RegisterHotKey.restype = wt.BOOL
    user32.UnregisterHotKey.argtypes = [wt.HWND, ctypes.c_int]
    user32.UnregisterHotKey.restype = wt.BOOL
    user32.GetForegroundWindow.restype = wt.HWND
    user32.SetForegroundWindow.argtypes = [wt.HWND]
    user32.SetForegroundWindow.restype = wt.BOOL
    user32.GetWindowTextLengthW.argtypes = [wt.HWND]
    user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
    user32.IsWindow.argtypes = [wt.HWND]
    user32.IsWindow.restype = wt.BOOL
    user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
    user32.GetWindowThreadProcessId.restype = wt.DWORD
    user32.AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]
    user32.AttachThreadInput.restype = wt.BOOL
    user32.GetMessageW.argtypes = [ctypes.POINTER(Msg), wt.HWND, wt.UINT, wt.UINT]
    user32.GetMessageW.restype = wt.BOOL
    user32.PeekMessageW.argtypes = [ctypes.POINTER(Msg), wt.HWND, wt.UINT, wt.UINT, wt.UINT]
    user32.PeekMessageW.restype = wt.BOOL
    user32.TranslateMessage.argtypes = [ctypes.POINTER(Msg)]
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(Msg)]
    user32.BringWindowToTop.argtypes = [wt.HWND]
    user32.BringWindowToTop.restype = wt.BOOL
    user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wt.BOOL

    kernel32.GetCurrentThreadId.restype = wt.DWORD

    SW_SHOW = 5
    SW_RESTORE = 9




else:
    def SendInput(*a, **k):
        return 0

# ---------------------------------------------------------------- 热键
class HotKey:
    """全局热键。mods 用 MOD_* 组合，key 用虚拟键码。"""

    def __init__(self, hwnd, hid, mods, vk):
        self.hwnd = hwnd
        self.hid = hid
        self.mods = mods
        self.vk = vk
        self.ok = False

    def register(self):
        if not IS_WIN or not self.hwnd or not self.vk:
            return False
        # 先注销，避免重复注册失败
        try:
            user32.UnregisterHotKey(self.hwnd, self.hid)
        except OSError:
            pass
        self.ok = bool(user32.RegisterHotKey(self.hwnd, self.hid,
                                             self.mods | MOD_NOREPEAT, self.vk))
        return self.ok

    def unregister(self):
        try:
            user32.UnregisterHotKey(self.hwnd, self.hid)
        except OSError:
            pass
        self.ok = False


def wait_hotkey(hwnd, predicate=None, timeout_ms=200):
    if not IS_WIN:
        return None
    """
    从消息队列里取一次 WM_HOTKEY。
    predicate(hid) → True 表示消费掉，False 表示继续等。
    返回命中的 hotkey id，超时返回 None。
    """
    msg = Msg()
    got = user32.PeekMessageW(ctypes.byref(msg), hwnd, WM_HOTKEY, WM_HOTKEY, 1)
    if not got:
        return None
    user32.TranslateMessage(ctypes.byref(msg))
    user32.DispatchMessageW(ctypes.byref(msg))
    return int(msg.wParam)


# ---------------------------------------------------------------- 焦点
def foreground_hwnd():
    if not IS_WIN:
        return 0
    try:
        return int(user32.GetForegroundWindow() or 0)
    except OSError:
        return 0


def window_title(hwnd):
    if not hwnd:
        return ''
    try:
        n = user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return ''
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value
    except OSError:
        return ''


def is_window(hwnd):
    try:
        return bool(user32.IsWindow(hwnd))
    except OSError:
        return False


def _force_foreground(hwnd):
    """绕过 Windows「不允许随意抢焦点」的限制：挂上目标线程输入队列再激活"""
    if not IS_WIN or not hwnd:
        return False
    try:
        if not user32.IsWindow(hwnd):
            return False
        cur = kernel32.GetCurrentThreadId()
        pid = wt.DWORD()
        tgt = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if tgt and tgt != cur:
            user32.AttachThreadInput(tgt, cur, True)
        try:
            user32.BringWindowToTop(hwnd)
            user32.ShowWindow(hwnd, SW_SHOW)
            user32.SetForegroundWindow(hwnd)
        finally:
            if tgt and tgt != cur:
                user32.AttachThreadInput(tgt, cur, False)
        return True
    except OSError:
        return False


# Windows 抢焦点后常需一点时间才真正生效
def focus_window(hwnd, settle=0.05):
    if not hwnd:
        return False
    for _ in range(3):
        _force_foreground(hwnd)
        time.sleep(settle)
        if foreground_hwnd() == hwnd:
            return True
    return False


# ---------------------------------------------------------------- 模拟按键
def _send(vk, up):
    if not IS_WIN:
        return                        # 非 Windows 无需模拟按键
    inp = Input()
    inp.type = INPUT_KEYBOARD
    inp.ki.wVk = vk
    inp.ki.wScan = 0
    inp.ki.dwFlags = KEYEVENTF_KEYUP if up else 0
    inp.ki.time = 0
    inp.ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
    SendInput(1, ctypes.byref(inp), ctypes.sizeof(Input))


def send_combo(vk_mod, vk_key, hold=0.02, gap=0.03):
    """按下组合键后松开，例如 send_combo(VK_CONTROL, ord('V'))"""
    _send(vk_mod, False)
    time.sleep(hold)
    _send(vk_key, False)
    time.sleep(hold)
    _send(vk_key, True)
    time.sleep(hold)
    _send(vk_mod, True)
    time.sleep(gap)


def send_paste():
    send_combo(VK_CONTROL, ord('V'))


# ---------------------------------------------------------------- 剪贴板
def get_clipboard_text():
    """读剪贴板文本；失败返回 None（occupied 属正常现象，不抛异常）"""
    if not IS_WIN:
        return None
    if not user32.OpenClipboard(0):
        return None
    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return None
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        p = kernel32.GlobalLock(ctypes.c_void_p(h))
        if not p:
            return None
        try:
            return ctypes.wstring_at(p)
        finally:
            kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
            kernel32.GlobalUnlock(ctypes.c_void_p(h))
    except OSError:
        return None
    finally:
        user32.CloseClipboard()


def set_clipboard_text(text):
    """写剪贴板文本。返回是否成功"""
    if not IS_WIN:
        return False
    text = text or ''
    if not user32.OpenClipboard(0):
        return False
    try:
        if not user32.EmptyClipboard():
            return False
        kernel32.GlobalAlloc.argtypes = [wt.UINT, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        size = (len(text) + 1) * 2
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
        if not h:
            return False
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        p = kernel32.GlobalLock(ctypes.c_void_p(h))
        if not p:
            return False
        try:
            ctypes.memmove(p, text.encode('utf-16-le'), len(text) * 2)
        finally:
            kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
            kernel32.GlobalUnlock(ctypes.c_void_p(h))
        user32.SetClipboardData.argtypes = [wt.UINT, ctypes.c_void_p]
        user32.SetClipboardData.restype = ctypes.c_void_p
        return bool(user32.SetClipboardData(CF_UNICODETEXT, ctypes.c_void_p(h)))
    except OSError:
        return False
    finally:
        user32.CloseClipboard()
