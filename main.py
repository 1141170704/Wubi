# -*- coding: utf-8 -*-
"""
TianFu五笔 · Windows 桌面版

启动后：
  · 系统托盘区不占位置，只在任务栏保留一个「主控窗」（可最小化）
  · 全局热键（默认 Ctrl+Space）唤出输入面板
  · 面板上屏后自动粘贴回你正在打字的窗口

用法：
    python main.py            # 直接运行
    python main.py --noconsole  # 配合 pythonw 无控制台
"""
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import config
import sounds
import winapi
from config import backup_dir
from db import Db, backup_name
from engine import Engine, TIME_TPL
from ui_keyboard import P_CLIP

FONT_CN = 'Microsoft YaHei UI'


def asset_path(name):
    """兼容 PyInstaller 打包后的资源路径"""
    base = getattr(sys, '_MEIPASS', None)
    if base:
        p = os.path.join(base, name)
        if os.path.exists(p):
            return p
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)


class App:
    def __init__(self):
        self.cfg = config.Config()
        self.db = Db(config.db_path())
        self.engine = Engine()
        self.panel = None
        self.console = None
        self.last_clip = ''
        self.self_clip = False       # 自己刚写过剪贴板，跳过一次采集
        self.hotkey_id = 1
        self.hwnd = 0
        self._hint_cache = []
        self._hint_ts = 0.0

        self.db.ensure_time(TIME_TPL)
        sounds.clean_cache()

        # 词库较大（8.6 万条），放后台加载，界面先出来
        self.engine_ready = False
        threading.Thread(target=self._load_engine, daemon=True).start()

    def _load_engine(self):
        ok = self.engine.load(asset_path(os.path.join('assets', 'wubi86.txt')))
        self.engine_ready = ok
        self._log('词库加载%s：%d 条' % ('成功' if ok else '失败', self.engine.size()))

    # ------------------------------------------------------------ 日志
    def _log(self, msg):
        if self.console:
            try:
                self.console.after(0, lambda: self.console.log(msg))
            except tk.TclError:
                pass

    # ------------------------------------------------------------ 反馈
    def feedback(self, which=0):
        """按键音（按配置，静音档直接跳过）"""
        name = self.cfg.get('sound', '水滴')
        vol = int(self.cfg.get('vol', 30)) / 100.0
        if not name or name == '无' or vol <= 0:
            return
        try:
            sounds.play(name, which, vol)
        except OSError:
            pass

    # ------------------------------------------------------------ 面板内容
    def panel_items(self, which):
        from ui_keyboard import P_CLIP, P_QUICK, P_TIME, P_TOOLS
        try:
            if which == P_CLIP:
                return self.db.clips(60)
            if which == P_QUICK:
                return self.db.contents_of('快捷发送')
            if which == P_TIME:
                return [t for t, _ in TIME_TPL]
            if which == P_TOOLS:
                return ['%s  %s' % (g, n) for _i, g, n in config.TOOLS]
        except Exception as ex:             # 面板取数不能崩掉整个程序
            self._log('面板取数失败：%s' % ex)
        return []

    def coded_hint(self):
        """无编码时，提示带编码的常用短语（短缓存，避免每次重绘都扫库）"""
        now = time.time()
        if self._hint_ts and now - self._hint_ts < 2.0:
            return self._hint_cache
        try:
            self._hint_cache = [r.content for r in self.db.coded()][:9]
        except Exception:
            self._hint_cache = []
        self._hint_ts = now
        return self._hint_cache

    # ------------------------------------------------------------ 上屏
    def commit(self, text):
        """写剪贴板 → 焦点还给原窗口 → Ctrl+V"""
        if not text:
            return
        self.self_clip = True
        ok = winapi.set_clipboard_text(text)
        if not ok:
            self._log('写剪贴板失败')
            self.self_clip = False
            return
        self.last_clip = text
        if self.cfg.get('auto_paste', True) and self.panel:
            hwnd = self.panel.prev_hwnd
            self.panel.hide()
            if hwnd and winapi.is_window(hwnd):
                if winapi.focus_window(hwnd):
                    time.sleep(0.03)
                    winapi.send_paste()
                else:
                    self._log('切回原窗口失败，文本已在剪贴板，可手动 Ctrl+V')
            self.panel.clear_code()

    def backspace(self):
        """无编码时按退格：删掉原窗口里的一个字符"""
        if not (self.cfg.get('auto_paste', True) and self.panel):
            return
        hwnd = self.panel.prev_hwnd
        if hwnd and winapi.is_window(hwnd) and winapi.focus_window(hwnd):
            winapi.send_combo(0, 0x08)      # VK_BACK

    def _to_prev(self):
        if not self.panel:
            return False
        hwnd = self.panel.prev_hwnd
        if hwnd and winapi.is_window(hwnd):
            return winapi.focus_window(hwnd)
        return False

    def send_ctrl(self, key):
        if self._to_prev():
            winapi.send_combo(0x11, ord(key.upper()))

    def send_arrow(self, tid):
        vk = {'left': 0x25, 'right': 0x27, 'up': 0x26, 'down': 0x28}.get(tid)
        if not vk:
            return
        if self._to_prev():
            winapi._send(vk, False)
            winapi._send(vk, True)

    def star_current(self):
        """收藏当前选区（或剪贴板最新一条）到「快捷发送」"""
        text = ''
        if self._to_prev():
            winapi.send_combo(0x11, ord('C'))
            time.sleep(0.08)
            text = winapi.get_clipboard_text() or ''
        if not text:
            clips = self.db.clips(1)
            text = clips[0] if clips else ''
        if not text:
            self._log('没有可收藏的内容')
            return
        self.db.insert('', text, ['快捷发送'])
        self._log('已收藏：%s' % text[:20])

    # ------------------------------------------------------------ 子窗口
    def open_phrases(self):
        from ui_phrase import PhraseWindow
        PhraseWindow(self)

    def open_settings(self):
        from ui_settings import SettingsWindow
        SettingsWindow(self)

    # ------------------------------------------------------------ 热键
    def parse_hotkey(self):
        """'ctrl+space' → (mods, vk)"""
        s = (self.cfg.get('hotkey_mods') or 'ctrl+space').lower()
        mods = 0
        vk = 0
        for part in s.split('+'):
            part = part.strip()
            if part == 'ctrl':
                mods |= winapi.MOD_CONTROL
            elif part == 'alt':
                mods |= winapi.MOD_ALT
            elif part == 'shift':
                mods |= winapi.MOD_SHIFT
            elif part == 'win':
                mods |= winapi.MOD_WIN
            elif part == 'space':
                vk = 0x20
            else:
                vk = winapi.vk_of(part[:1]) or vk
        return mods, vk

    def register_hotkey(self):
        if not self.hwnd:
            return False
        mods, vk = self.parse_hotkey()
        if not vk:
            return False
        return bool(winapi.user32.RegisterHotKey(self.hwnd, self.hotkey_id,
                                                 mods | winapi.MOD_NOREPEAT, vk))

    def poll(self):
        """轮询热键消息（非阻塞，避免卡住 tkinter）"""
        try:
            msg = winapi.Msg()
            got = winapi.user32.PeekMessageW(winapi.ctypes.byref(msg), self.hwnd,
                                             winapi.WM_HOTKEY, winapi.WM_HOTKEY, 1)
            if got:
                winapi.user32.TranslateMessage(winapi.ctypes.byref(msg))
                winapi.user32.DispatchMessageW(winapi.ctypes.byref(msg))
                if int(msg.wParam) == self.hotkey_id and self.panel:
                    self.panel.toggle()
        except OSError:
            pass
        if self.console:
            self.console.after(60, self.poll)

    # ------------------------------------------------------------ 剪贴板
    def poll_clip(self):
        if self.cfg.get('clip_watch', True):
            try:
                t = winapi.get_clipboard_text()
                if t and t != self.last_clip:
                    self.last_clip = t
                    if not self.self_clip:
                        self.db.add_clip(t)
                    self.self_clip = False
                    if self.panel and self.panel.visible and self.panel.panel == P_CLIP:
                        self.panel.panel_items = self.panel_items(P_CLIP)
                        self.panel.redraw()
            except OSError:
                pass
        if self.console:
            self.console.after(700, self.poll_clip)

    # ------------------------------------------------------------ 启动
    def run(self):
        from ui_keyboard import Panel
        self.console = Console(self)
        self.panel = Panel(self)

        # 热键需要一个 hwnd；用主控窗的句柄
        self.console.update()
        try:
            self.hwnd = int(self.console.frame(), 16)
        except tk.TclError:
            self.hwnd = 0

        if not self.register_hotkey():
            self._log('全局热键注册失败，可能被其它程序占用。可在设置里换一个。')
        else:
            mods, _vk = self.parse_hotkey()
            self._log('已注册热键：%s' % self.cfg.get('hotkey_mods'))

        self.console.after(80, self.poll)
        self.console.after(1000, self.poll_clip)
        # 启动时最小化：否则主控窗会占用前台，面板就记不住"用户真正在打字的窗口"
        self.console.after(300, self.console.iconify)
        self.console.mainloop()


class Console(tk.Tk):
    """主控窗：任务栏常驻，提供入口与状态。可最小化。"""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.title('TianFu五笔 · 主控')
        self.geometry('420x260')
        self.configure(bg=app.cfg.theme()['bg'])
        th = app.cfg.theme()

        head = tk.Frame(self, bg=th['bar'])
        head.pack(fill=tk.X)
        tk.Label(head, text='TianFu五笔', fg=th['text'], bg=th['bar'],
                 font=(FONT_CN, 13, 'bold')).pack(side=tk.LEFT, padx=10, pady=8)

        body = tk.Frame(self, bg=th['bg'])
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        self.info = tk.Label(body, justify=tk.LEFT, fg=th['dim'], bg=th['bg'],
                             font=(FONT_CN, 10), anchor='w')
        self.info.pack(fill=tk.X)

        btns = tk.Frame(body, bg=th['bg'])
        btns.pack(fill=tk.X, pady=8)
        self._btn(btns, '呼出面板', lambda: app.panel and app.panel.show())
        self._btn(btns, '短语管理', app.open_phrases)
        self._btn(btns, '设置', app.open_settings)
        self._btn(btns, '退出', self.quit_app)

        tk.Label(body, text='运行日志', fg=th['dim'], bg=th['bg'],
                 font=(FONT_CN, 9)).pack(anchor='w')
        self.txt = tk.Text(body, height=5, bg=th['key'], fg=th['text'],
                           relief=tk.FLAT, font=('Consolas', 9),
                           insertbackground=th['text'])
        self.txt.pack(fill=tk.BOTH, expand=True)
        self.protocol('WM_DELETE_WINDOW', self.withdraw_iconic)

        self.refresh_info()
        self.after(1500, self.refresh_info)

    def _btn(self, parent, text, cmd):
        th = self.app.cfg.theme()
        b = tk.Button(parent, text=text, command=cmd, bg=th['key'], fg=th['text'],
                      relief=tk.FLAT, bd=0, padx=12, pady=6,
                      activebackground=th['key_hi'], activeforeground=th['text'],
                      font=(FONT_CN, 10))
        b.pack(side=tk.LEFT, padx=(0, 6))
        return b

    def refresh_info(self):
        app = self.app
        e = app.engine
        state = '就绪' if e.ready else '加载中…'
        try:
            n = app.db.count_all()
        except Exception:
            n = 0
        self.info.config(text='词库：%s（%d 条）    短语：%d 条    热键：%s'
                              % (state, e.size(), n, app.cfg.get('hotkey_mods')))
        self.after(1500, self.refresh_info)

    def log(self, msg):
        try:
            ts = time.strftime('%H:%M:%S')
            self.txt.insert(tk.END, '[%s] %s\n' % (ts, msg))
            self.txt.see(tk.END)
        except tk.TclError:
            pass

    def withdraw_iconic(self):
        """关闭按钮 = 最小化到任务栏，不退出"""
        self.iconify()

    def quit_app(self):
        try:
            winapi.user32.UnregisterHotKey(self.app.hwnd, self.app.hotkey_id)
        except OSError:
            pass
        try:
            self.app.db.close()
        except Exception:
            pass
        self.destroy()
        sys.exit(0)


def main():
    if not winapi.IS_WIN:
        sys.stderr.write('TianFu五笔 桌面版依赖 Win32 API（全局热键、自动粘贴），'
                         '只能在 Windows 上运行。\n')
        sys.exit(2)
    app = App()
    app.run()


if __name__ == '__main__':
    main()
