# -*- coding: utf-8 -*-
"""设置窗口：外观 / 键盘 / 声音 / 热键 / 行为。改动立即生效。"""
import os
import tkinter as tk
from tkinter import filedialog, messagebox

import config
import sounds
import winapi

FONT_CN = 'Microsoft YaHei UI'


class SettingsWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.console)
        self.app = app
        self.cfg = app.cfg
        th = app.cfg.theme()
        self.th = th
        self.title('设置')
        self.geometry('560x520')
        self.configure(bg=th['bg'])
        self.transient(app.console)

        self.wrap = tk.Frame(self, bg=th['bg'])
        self.wrap.pack(fill=tk.BOTH, expand=True)
        self.cv = tk.Canvas(self.wrap, bg=th['bg'], highlightthickness=0, bd=0)
        self.sb = tk.Scrollbar(self.wrap, orient=tk.VERTICAL, command=self.cv.yview)
        self.inner = tk.Frame(self.cv, bg=th['bg'])
        self.inner.bind('<Configure>',
                        lambda e: self.cv.configure(scrollregion=self.cv.bbox('all')))
        self.cv.create_window((0, 0), window=self.inner, anchor='nw')
        self.cv.configure(yscrollcommand=self.sb.set)
        self.cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.cv.bind('<MouseWheel>',
                     lambda e: self.cv.yview_scroll(int(-1 * (e.delta / 120)), 'units'))

        self._build()
        self.refresh_all()

    # ------------------------------------------------------------ 构建
    def _sec(self, text):
        tk.Label(self.inner, text=text, fg=self.th['dim'], bg=self.th['bg'],
                 font=(FONT_CN, 10, 'bold'), anchor='w').pack(fill=tk.X, padx=12, pady=(12, 4))

    def _row(self, label):
        r = tk.Frame(self.inner, bg=self.th['bg'])
        r.pack(fill=tk.X, padx=12, pady=2)
        tk.Label(r, text=label, fg=self.th['text'], bg=self.th['bg'],
                 font=(FONT_CN, 10), width=14, anchor='w').pack(side=tk.LEFT)
        return r

    def _chips(self, parent, options, getter, setter):
        th = self.th
        btns = {}

        def paint():
            cur = getter()
            for k, b in btns.items():
                on = (k == cur)
                b.config(bg=th['key_hi'] if on else th['key'],
                         fg=th['accent'] if on else th['text'],
                         font=(FONT_CN, 10, 'bold' if on else 'normal'))

        for o in options:
            b = tk.Button(parent, text=o, bg=th['key'], fg=th['text'], relief=tk.FLAT,
                          padx=8, pady=3, font=(FONT_CN, 10),
                          activebackground=th['key_hi'],
                          command=lambda x=o: (setter(x), paint(), self.apply()))
            b.pack(side=tk.LEFT, padx=(0, 4))
            btns[o] = b
        paint()
        return paint

    def _stepper(self, parent, label, getter, setter, lo, hi, step=1):
        th = self.th
        r = self._row(label)
        val = tk.Label(r, text=str(getter()), fg=th['accent'], bg=th['bg'],
                       font=(FONT_CN, 10), width=6)

        def paint():
            val.config(text=str(getter()))

        def dec():
            setter(max(lo, getter() - step))
            paint()
            self.apply()

        def inc():
            setter(min(hi, getter() + step))
            paint()
            self.apply()

        tk.Button(r, text='−', command=dec, bg=th['key'], fg=th['text'], relief=tk.FLAT,
                  width=3, activebackground=th['key_hi']).pack(side=tk.LEFT)
        val.pack(side=tk.LEFT)
        tk.Button(r, text='＋', command=inc, bg=th['key'], fg=th['text'], relief=tk.FLAT,
                  width=3, activebackground=th['key_hi']).pack(side=tk.LEFT)
        self.refreshers.append(paint)
        return paint

    def _check(self, label, getter, setter):
        th = self.th
        r = self._row(label)
        v = tk.BooleanVar(value=getter())
        cb = tk.Checkbutton(r, variable=v, bg=th['bg'], fg=th['text'],
                            selectcolor=th['key'], activebackground=th['bg'],
                            command=lambda: (setter(v.get()), self.cfg.save()))
        cb.pack(side=tk.LEFT)

        def paint():
            v.set(getter())

        self.refreshers.append(paint)
        return paint

    def _btn(self, parent, text, cmd):
        th = self.th
        return tk.Button(parent, text=text, command=cmd, bg=th['key'], fg=th['text'],
                         relief=tk.FLAT, padx=10, pady=4, font=(FONT_CN, 10),
                         activebackground=th['key_hi'])

    def _build(self):
        self.refreshers = []

        # ---- 外观
        self._sec('外观')
        r = self._row('键盘配色')
        self._chips(r, config.THEME_NAMES,
                    lambda: self.cfg.get('theme'),
                    lambda v: self.cfg.set('theme', v))
        r = self._row('布局方案')
        self._chips(r, ['纯净', '经典'],
                    lambda: self.cfg.get('style'),
                    lambda v: self.cfg.set('style', v))
        self._check('显示第二行信息',
                    lambda: self.cfg.get('show_second', True),
                    lambda v: self.cfg.set('show_second', v))

        # ---- 键盘
        self._sec('键盘')
        self._stepper(self.inner, '键盘高度',
                      lambda: int(self.cfg.get('kb_height', 250)),
                      lambda v: self.cfg.set('kb_height', v), 150, 600, 10)
        self._stepper(self.inner, '字母字号',
                      lambda: int(self.cfg.get('letter_sp', 16)),
                      lambda v: self.cfg.set('letter_sp', v), 8, 40)
        self._stepper(self.inner, '候选字号',
                      lambda: int(self.cfg.get('cand_sp', 15)),
                      lambda v: self.cfg.set('cand_sp', v), 8, 40)
        self._stepper(self.inner, '工具栏图标',
                      lambda: int(self.cfg.get('tool_icon_sp', 13)),
                      lambda v: self.cfg.set('tool_icon_sp', v), 8, 24)

        # ---- 声音
        self._sec('按键音')
        r = self._row('当前音色')
        self.snd_label = tk.Label(r, text='', fg=self.th['accent'], bg=self.th['bg'],
                                  font=(FONT_CN, 10))
        self.snd_label.pack(side=tk.LEFT)
        self._btn(r, '管理/导入/导出', self.open_sounds).pack(side=tk.LEFT, padx=8)
        self._stepper(self.inner, '音量',
                      lambda: int(self.cfg.get('vol', 30)),
                      lambda v: self.cfg.set('vol', v), 0, 100, 10)

        # ---- 热键
        self._sec('热键')
        r = self._row('呼出面板')
        self.hk_label = tk.Label(r, text=self.cfg.get('hotkey_mods'),
                                 fg=self.th['accent'], bg=self.th['bg'], font=(FONT_CN, 10))
        self.hk_label.pack(side=tk.LEFT)
        self._btn(r, '修改', self.change_hotkey).pack(side=tk.LEFT, padx=8)

        # ---- 行为
        self._sec('行为')
        self._check('上屏后自动粘贴回原窗口',
                    lambda: self.cfg.get('auto_paste', True),
                    lambda v: self.cfg.set('auto_paste', v))
        self._check('监视剪贴板（自动收录）',
                    lambda: self.cfg.get('clip_watch', True),
                    lambda v: self.cfg.set('clip_watch', v))

        self._sec('')
        r = tk.Frame(self.inner, bg=self.th['bg'])
        r.pack(fill=tk.X, padx=12, pady=6)
        self._btn(r, '恢复默认设置', self.reset_all).pack(side=tk.LEFT)
        self._btn(r, '打开数据目录', self.open_dir).pack(side=tk.LEFT, padx=8)

    # ------------------------------------------------------------ 刷新 / 应用
    def refresh_all(self):
        for f in self.refreshers:
            try:
                f()
            except Exception:
                pass
        self.snd_label.config(text=self.cfg.get('sound'))
        self.hk_label.config(text=self.cfg.get('hotkey_mods'))

    def apply(self):
        self.cfg.save()
        if self.app.panel:
            self.app.panel.apply_theme()

    # ------------------------------------------------------------ 子功能
    def open_sounds(self):
        SoundManager(self, self.app, self.refresh_all)

    def change_hotkey(self):
        HotkeyDialog(self, self.app, self.refresh_all)

    def reset_all(self):
        if not messagebox.askyesno('恢复默认', '将恢复所有设置为默认值（短语数据不受影响）'):
            return
        self.cfg.data = dict(config.DEFAULTS)
        self.cfg.save()
        if self.app.panel:
            self.app.panel.apply_theme()
        self.refresh_all()
        self.rebuild_hotkey()

    def rebuild_hotkey(self):
        try:
            winapi.user32.UnregisterHotKey(self.app.hwnd, self.app.hotkey_id)
        except OSError:
            pass
        ok = self.app.register_hotkey()
        if not ok:
            messagebox.showwarning('提示', '热键注册失败，可能被其它程序占用')

    def open_dir(self):
        try:
            os.startfile(config.APP_DIR)
        except (OSError, AttributeError):
            messagebox.showinfo('数据目录', config.APP_DIR)


# ---------------------------------------------------------------- 声音管理
class SoundManager(tk.Toplevel):
    """按键音管理：内置水滴 + 导入 / 导出 / 删除 / 试听"""

    def __init__(self, parent, app, on_change):
        super().__init__(parent)
        self.app = app
        self.cfg = app.cfg
        th = parent.th
        self.th = th
        self.title('按键音管理')
        self.geometry('560x460')
        self.configure(bg=th['bg'])
        self.transient(parent)
        self.on_change = on_change
        self.sel = set()

        sounds.clean_cache()

        bar = tk.Frame(self, bg=th['bar'])
        bar.pack(fill=tk.X)
        for t, cmd in (('全选', self.all), ('清空选择', self.none),
                       ('▶试听', self.audition), ('✔设为当前', self.set_current),
                       ('↓导入', self.do_import), ('↑导出所选', self.do_export),
                       ('✕删除所选', self.do_delete)):
            tk.Button(bar, text=t, command=cmd, bg=th['key'], fg=th['text'],
                      relief=tk.FLAT, padx=8, pady=4, font=(FONT_CN, 10),
                      activebackground=th['key_hi']).pack(side=tk.LEFT, padx=3, pady=5)

        self.box = tk.Frame(self, bg=th['bg'])
        self.box.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        self.render()

    def render(self):
        for w in self.box.winfo_children():
            w.destroy()
        th = self.th
        cur = self.cfg.get('sound')
        for name in ['无'] + sounds.list_sounds():
            bgv = th['key'] if name in self.sel else th['bg']
            row = tk.Frame(self.box, bg=bgv)
            row.pack(fill=tk.X, pady=1)
            v = tk.BooleanVar(value=(name in self.sel))
            tk.Checkbutton(row, variable=v, bg=th['bg'], selectcolor=th['key'],
                           activebackground=th['bg'],
                           command=lambda x=name, vv=v: self.toggle(x, vv.get())).pack(side=tk.LEFT)
            builtin = sounds.is_builtin(name)
            label = name + ('  ●当前' if name == cur else '')
            sub = '' if name == '无' else (sounds.desc(name) or '自定义音色')
            if builtin:
                sub = '内置 · ' + sub
            f = tk.Frame(row, bg=bgv)
            f.pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Label(f, text=label, fg=th['accent'] if name == cur else th['text'],
                     bg=bgv, font=(FONT_CN, 11), anchor='w').pack(fill=tk.X)
            if sub:
                tk.Label(f, text=sub, fg=th['dim'], bg=bgv,
                         font=(FONT_CN, 9), anchor='w').pack(fill=tk.X)
            if name != '无':
                tk.Button(row, text='▶', bg=th['key'], fg=th['text'], relief=tk.FLAT,
                          padx=8, font=(FONT_CN, 9), activebackground=th['key_hi'],
                          command=lambda x=name: self.play(x)).pack(side=tk.RIGHT)

    def toggle(self, n, v):
        if v:
            self.sel.add(n)
        else:
            self.sel.discard(n)
        self.render()

    def all(self):
        self.sel = set(sounds.list_sounds())
        self.render()

    def none(self):
        self.sel.clear()
        self.render()

    def play(self, name):
        vol = int(self.cfg.get('vol', 30)) / 100.0
        if vol <= 0:
            vol = 0.3
        sounds.play(name, 0, vol)

    def audition(self):
        if not self.sel:
            return messagebox.showinfo('提示', '先勾选音色')
        self.play(sorted(self.sel)[0])

    def set_current(self):
        if len(self.sel) != 1:
            return messagebox.showinfo('提示', '请只勾选一个')
        self.cfg.set('sound', sorted(self.sel)[0])
        self.cfg.save()
        self.on_change()
        self.render()

    def do_import(self):
        ps = filedialog.askopenfilenames(filetypes=[('WAV 音频', '*.wav'),
                                                    ('所有文件', '*.*')])
        if not ps:
            return
        ok = 0
        for p in ps:
            if sounds.import_wav(p):
                ok += 1
        messagebox.showinfo('导入', '成功 %d 个，失败 %d 个（仅支持 16bit PCM 的 WAV）'
                            % (ok, len(ps) - ok))
        self.on_change()
        self.render()

    def do_export(self):
        if not self.sel:
            return messagebox.showinfo('提示', '先勾选要导出的音色')
        d = filedialog.askdirectory()
        if not d:
            return
        n = sounds.export(sorted(self.sel), d)
        messagebox.showinfo('导出', '已导出 %d 个到 %s' % (n, d))

    def do_delete(self):
        can = [s for s in self.sel if not sounds.is_builtin(s)]
        if not can:
            return messagebox.showinfo('提示', '内置音色「%s」不可删除（可勾选后导出）'
                                       % sounds.DEFAULT)
        if not messagebox.askyesno('删除', '将删除 %d 个导入的音色' % len(can)):
            return
        sounds.delete(can)
        cur = self.cfg.get('sound')
        if cur not in ['无'] + sounds.list_sounds():
            self.cfg.set('sound', sounds.DEFAULT)
            self.cfg.save()
        self.sel.clear()
        self.on_change()
        self.render()


# ---------------------------------------------------------------- 热键设置
class HotkeyDialog(tk.Toplevel):
    def __init__(self, parent, app, on_change):
        super().__init__(parent)
        self.app = app
        self.cfg = app.cfg
        th = parent.th
        self.title('修改热键')
        self.geometry('420x220')
        self.configure(bg=th['bg'])
        self.transient(parent)
        self.on_change = on_change

        tk.Label(self, text='选择一个修饰键和一个按键（建议避开系统快捷键）',
                 fg=th['dim'], bg=th['bg'], font=(FONT_CN, 9)).pack(anchor='w', padx=12, pady=(10, 4))

        r1 = tk.Frame(self, bg=th['bg'])
        r1.pack(fill=tk.X, padx=12, pady=4)
        self.mod = tk.StringVar(value='ctrl')
        for t, v in (('Ctrl', 'ctrl'), ('Alt', 'alt'), ('Win', 'win')):
            tk.Radiobutton(r1, text=t, variable=self.mod, value=v, bg=th['bg'],
                           fg=th['text'], selectcolor=th['key'],
                           activebackground=th['bg'], font=(FONT_CN, 10)).pack(side=tk.LEFT, padx=6)

        r2 = tk.Frame(self, bg=th['bg'])
        r2.pack(fill=tk.X, padx=12, pady=4)
        tk.Label(r2, text='按键：', fg=th['text'], bg=th['bg'],
                 font=(FONT_CN, 10)).pack(side=tk.LEFT)
        self.key = tk.StringVar(value='space')
        opts = ['space'] + list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')[:6] + ['`']
        for o in opts:
            tk.Radiobutton(r2, text=o.upper() if o != '`' else '`', variable=self.key,
                           value=o, bg=th['bg'], fg=th['text'], selectcolor=th['key'],
                           activebackground=th['bg'], font=(FONT_CN, 10)).pack(side=tk.LEFT, padx=3)

        btns = tk.Frame(self, bg=th['bg'])
        btns.pack(fill=tk.X, pady=14)
        tk.Button(btns, text='确定', command=self.ok, bg=th['key'], fg=th['text'],
                  relief=tk.FLAT, padx=16, pady=5, font=(FONT_CN, 10)).pack(side=tk.RIGHT, padx=12)
        tk.Button(btns, text='取消', command=self.destroy, bg=th['key'], fg=th['dim'],
                  relief=tk.FLAT, padx=16, pady=5, font=(FONT_CN, 10)).pack(side=tk.RIGHT)
        self.grab_set()

    def ok(self):
        combo = '%s+%s' % (self.mod.get(), self.key.get())
        self.cfg.set('hotkey_mods', combo)
        self.cfg.save()
        try:
            winapi.user32.UnregisterHotKey(self.app.hwnd, self.app.hotkey_id)
        except OSError:
            pass
        if not self.app.register_hotkey():
            messagebox.showwarning('提示', '热键 %s 注册失败，可能被占用，换一个试试' % combo)
        self.on_change()
        self.destroy()
