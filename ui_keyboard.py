# -*- coding: utf-8 -*-
"""
输入法面板（Canvas 自绘，纯色平涂无阴影，视觉与移动端一致）。

布局从上到下：
    工具栏（多组，可横滑） → 候选栏 → 键盘区 / 展开面板

两种输入方式：
    · 点虚拟键盘
    · 直接用物理键盘（推荐，a-z 即编码，数字选候选，空格选首个）
上屏后自动粘贴回唤出前的窗口（可关闭）。
"""
import os
import time

import tkinter as tk
from tkinter import font as tkfont

import config
import sounds
import winapi
from engine import expand

# 面板模式
P_NONE = 0
P_CLIP = 1
P_QUICK = 2
P_TIME = 3
P_TOOLS = 4

FONT_CN = 'Microsoft YaHei UI'


class Panel(tk.Toplevel):
    """必须用 Toplevel 而非 Tk：一个进程只能有一个 Tcl 解释器，
    若面板另开 Tk()，它的事件循环不会被主控窗 mainloop 驱动，点了没反应。"""

    def __init__(self, app):
        super().__init__(app.console)
        self.app = app                 # App 主控，持有 db/engine/config
        self.console_hwnd = 0
        self.cfg = app.cfg
        self.th = self.cfg.theme()

        self.code = ''
        self.cands = []
        self.page = 'main'             # main / num / sym
        self.panel = P_NONE
        self.panel_items = []
        self.panel_scroll = 0
        self.tool_group = 0
        self.caps = False              # False=五笔模式 True=大写英文

        self.prev_hwnd = 0             # 唤出面板前的前台窗口
        self.visible = False
        self.pressed = None

        self._build_window()
        self._build_canvas()
        self._bind_events()
        self.redraw()

    # ------------------------------------------------------------ 窗口
    def _build_window(self):
        self.title('TianFu五笔')
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.configure(bg=self.th['bg'])
        w, h = self._size()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = (sw - w) // 2
        y = sh - h - 60
        self.geometry('%dx%d+%d+%d' % (w, h, x, max(0, y)))
        self.withdraw()

    def _size(self):
        w = min(760, max(420, int(self.winfo_screenwidth() * 0.5)))
        h = int(self.cfg.get('kb_height', 250)) + 96
        return w, h

    def _build_canvas(self):
        self.cv = tk.Canvas(self, bg=self.th['bg'], highlightthickness=0, bd=0)
        self.cv.pack(fill=tk.BOTH, expand=True)

    def _bind_events(self):
        self.cv.bind('<Button-1>', self.on_click)
        self.cv.bind('<ButtonRelease-1>', self.on_release)
        self.cv.bind('<B1-Motion>', self.on_motion)
        self.cv.bind('<MouseWheel>', self.on_wheel)
        self.cv.bind('<Button-3>', self.on_right)
        self.bind('<Key>', self.on_key)
        self.bind('<Escape>', lambda e: self.hide())
        self.bind('<FocusOut>', self.on_focus_out)
        self.protocol('WM_DELETE_WINDOW', self.hide)

    # ------------------------------------------------------------ 显隐
    def show(self):
        # 必须在自己抢焦点之前记下「用户真正打字的地方」
        self.update_idletasks()
        try:
            self_hwnd = int(self.frame(), 16)
        except tk.TclError:
            self_hwnd = 0
        if not self.console_hwnd:
            try:
                self.console_hwnd = int(self.app.console.frame(), 16)
            except (tk.TclError, AttributeError):
                self.console_hwnd = 0
        hwnd = winapi.foreground_hwnd()
        if hwnd and hwnd != self_hwnd and hwnd != self.console_hwnd:
            self.prev_hwnd = hwnd

        self.visible = True
        self.deiconify()
        self.lift()
        self.focus_force()
        try:
            winapi.focus_window(int(self.frame(), 16))
        except (tk.TclError, OSError):
            pass
        self.focus_force()
        self.redraw()

    def hide(self):
        self.visible = False
        self.clear_code()
        self.panel = P_NONE
        self.withdraw()

    def toggle(self):
        if self.visible:
            self.hide()
        else:
            self.show()

    def on_focus_out(self, event=None):
        """失焦时收起（避免挡住用户）"""
        if self.visible:
            self.after(120, self._check_focus)

    def _check_focus(self):
        try:
            if self.visible and winapi.foreground_hwnd() != int(self.frame(), 16):
                pass    # 焦点可能被调试器/菜单拿走，这里不强制收起
        except (tk.TclError, OSError):
            pass

    def apply_theme(self):
        self.th = self.cfg.theme()
        self.configure(bg=self.th['bg'])
        self.cv.configure(bg=self.th['bg'])
        w, h = self._size()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry('%dx%d+%d+%d' % (w, h, (sw - w) // 2, max(0, sh - h - 60)))
        self.redraw()

    # ------------------------------------------------------------ 绘制
    def redraw(self):
        self.cv.delete('all')
        w = self.cv.winfo_width() or self._size()[0]
        h = self.cv.winfo_height() or self._size()[1]
        self.rects = []                 # 命中区域
        th = self.th

        tool_h = 34
        cand_h = 40
        self.tool_h, self.cand_h = tool_h, cand_h

        self.cv.create_rectangle(0, 0, w, h, fill=th['bg'], outline='')

        self.draw_tools(0, w, tool_h)
        self.draw_cand(0, tool_h, w, cand_h)

        top = tool_h + cand_h
        if self.panel != P_NONE:
            self.draw_panel(0, top, w, h - top)
        else:
            self.draw_keys(0, top, w, h - top)

    # ------------------------------------------------------------ 工具栏
    def draw_tools(self, x, w, h):
        th = self.th
        self.cv.create_rectangle(x, 0, x + w, h, fill=th['bar'], outline='')
        groups = self.cfg.get('tools') or config.DEFAULT_TOOLS
        gi = min(self.tool_group, len(groups) - 1)
        items = groups[gi] if gi >= 0 else []

        sp = int(self.cfg.get('tool_icon_sp', 13))
        btn = max(26, min(46, sp * 2 + 12))
        pad = 5
        # 放不下就允许横滑（记录偏移）
        total = len(items) * (btn + pad)
        avail = w - 90
        self.tool_off = min(0, avail - total) if total > avail else 0
        self.tool_off = min(self.tool_off, 0)

        cx = 6 + self.tool_off
        for tid in items:
            if cx + btn > w - 84:
                break
            # 只有「能展开面板」的工具才有选中态，否则所有工具都会常亮
            on = tid in self._PANEL_TOOLS and self.panel == self._tool_panel(tid)
            self._box(cx, 4, btn, h - 8, config.TOOL_ICON.get(tid, '?'),
                      ('tool', tid), size=sp,
                      bg=th['key_hi'] if on else th['key'],
                      fg=th['accent'] if on else th['text'])
            cx += btn + pad

        # 右侧：组切换
        gx = w - 82
        self._box(gx, 4, 34, h - 8, '%d/%d' % (gi + 1, len(groups)),
                  ('group', -1), size=10, bg=th['key'], fg=th['dim'])
        self._box(w - 44, 4, 18, h - 8, '‹', ('gprev', -1), size=11,
                  bg=th['key'], fg=th['text'])
        self._box(w - 24, 4, 18, h - 8, '›', ('gnext', -1), size=11,
                  bg=th['key'], fg=th['text'])

    _PANEL_TOOLS = ('clip', 'quick', 'time')

    @staticmethod
    def _tool_panel(tid):
        return {'clip': P_CLIP, 'quick': P_QUICK, 'time': P_TIME}.get(tid, P_NONE)

    # ------------------------------------------------------------ 候选栏
    def draw_cand(self, x, y, w, h):
        th = self.th
        self.cv.create_rectangle(x, y, x + w, y + h, fill=th['bar'], outline='')
        sp = int(self.cfg.get('cand_sp', 15))

        label = self.code if self.code else ('选词' if self.cands else '五笔')
        self.cv.create_text(x + 8, y + h // 2, anchor='w', text=label,
                            fill=th['accent'], font=(FONT_CN, sp, 'bold'))

        cands = self.cands if self.cands else (self.app.coded_hint() if not self.code else [])
        cx = x + 78
        self.cand_rects = []
        for i, c in enumerate(cands[:9]):
            tw = self._text_w(c, sp)
            bw = tw + 16
            if cx + bw > w - 8:
                break
            self._box(cx, y + 5, bw, h - 10, c, ('cand', i), size=sp,
                      bg=th['key'], fg=th['text'])
            cx += bw + 4

        if not cands and self.code:
            self.cv.create_text(cx + 8, y + h // 2, anchor='w', text='（无候选）',
                                fill=th['dim'], font=(FONT_CN, 11))

    # ------------------------------------------------------------ 键盘
    def draw_keys(self, x, y, w, h):
        th = self.th
        sp = int(self.cfg.get('letter_sp', 16))
        rows = self._rows()
        gap = 3
        rh = (h - gap) / max(1, len(rows))

        for ri, row in enumerate(rows):
            total = sum(k[2] for k in row) or 1
            usable = w - gap * (len(row) + 1)
            cx = x + gap
            ry = y + gap + ri * rh
            for label, act, wgt in row:
                kw = usable * (wgt / total)
                size = sp * 0.9
                bold = False
                if act == 'enter':
                    size = sp * 1.75
                    bold = True
                elif act == 'del':
                    size = sp * 1.2
                elif act in ('caps', 'page_num', 'page_sym', 'page_main'):
                    size = sp * 0.8
                show = label
                if act == 'caps':
                    show = 'ABC' if self.caps else '五笔'
                self._box(cx, ry, max(8, kw - 1), rh - gap, show, ('key', (label, act)),
                          size=size, bold=bold,
                          bg=th['key'], fg=th['dim'] if act in
                          ('caps', 'page_num', 'page_sym', 'page_main') else th['text'])
                cx += kw + gap

    def _rows(self):
        classic = self.cfg.get('style') == '经典'
        if self.page == 'num':
            return config.num_rows()
        if self.page == 'sym':
            return config.sym_rows()
        return config.main_rows(classic)

    # ------------------------------------------------------------ 展开面板
    def draw_panel(self, x, y, w, h):
        th = self.th
        self.cv.create_rectangle(x, y, x + w, y + h, fill=th['bg'], outline='')
        items = self.panel_items
        if not items:
            self.cv.create_text(w // 2, y + h // 2, text='（暂无内容）',
                                fill=th['dim'], font=(FONT_CN, 12))
            return
        sp = int(self.cfg.get('cand_sp', 15))
        line_h = 30
        per = max(1, h // line_h)
        max_off = max(0, len(items) - per)
        self.panel_scroll = max(0, min(self.panel_scroll, max_off))

        for i in range(self.panel_scroll, min(len(items), self.panel_scroll + per)):
            ry = y + (i - self.panel_scroll) * line_h
            txt = items[i]
            if len(txt) > 60:
                txt = txt[:60] + '…'
            self._box(x + 4, ry + 2, w - 20, line_h - 4, txt, ('item', i),
                      size=sp - 2, bg=th['key'], fg=th['text'], anchor='w', pad=10)
        # 滚动条
        if len(items) > per:
            sw = 6
            track_h = h - 8
            th_h = max(20, track_h * per / len(items))
            ty = y + 4 + (track_h - th_h) * (self.panel_scroll / max(1, max_off))
            self.cv.create_rectangle(w - sw - 4, y + 4, w - 4, y + 4 + track_h,
                                     fill=th['key'], outline='')
            self.cv.create_rectangle(w - sw - 4, ty, w - 4, ty + th_h,
                                     fill=th['dim'], outline='')

    # ------------------------------------------------------------ 基元
    def _text_w(self, s, sp):
        try:
            f = tkfont.Font(family=FONT_CN, size=int(sp))
            return f.measure(s)
        except tk.TclError:
            return len(s) * int(sp)

    def _box(self, x, y, w, h, text, tag, size=13, bold=False,
             bg='#101010', fg='#FFFFFF', anchor='center', pad=0):
        """画一个纯色圆角/直角按钮，并记录命中矩形"""
        th = self.th
        r = 4 if self.cfg.get('style') == '经典' else 3
        self.cv.create_rectangle(x, y, x + w, y + h, fill=bg, outline='')
        # 纯色平涂：不做阴影/渐变，仅用 1px 同色调描边区分边界
        self.cv.create_rectangle(x, y, x + w, y + h, outline=th['bg'], width=1)
        if text:
            if anchor == 'w':
                tx, ay = x + pad, y + h / 2
            else:
                tx, ay = x + w / 2, y + h / 2
            self.cv.create_text(tx, ay, anchor=anchor, text=text, fill=fg,
                                font=(FONT_CN, int(size), 'bold' if bold else 'normal'))
        self.rects.append((x, y, x + w, y + h, tag))

    # ------------------------------------------------------------ 事件
    def _hit(self, px, py):
        for (x0, y0, x1, y1, tag) in self.rects:
            if x0 <= px < x1 and y0 <= py < y1:
                return tag
        return None

    def on_click(self, e):
        tag = self._hit(e.x, e.y)
        if not tag:
            return
        self.pressed = tag
        kind, val = tag
        self.app.feedback(0)
        if kind == 'tool':
            self.do_tool(val)
        elif kind == 'cand':
            self.pick(val)
        elif kind == 'key':
            self.do_key(val)
        elif kind == 'item':
            self.pick_item(val)
        elif kind == 'group':
            pass
        elif kind == 'gprev':
            gs = self.cfg.get('tools') or config.DEFAULT_TOOLS
            self.tool_group = (self.tool_group - 1) % len(gs)
            self.redraw()
        elif kind == 'gnext':
            gs = self.cfg.get('tools') or config.DEFAULT_TOOLS
            self.tool_group = (self.tool_group + 1) % len(gs)
            self.redraw()

    def on_release(self, e):
        self.pressed = None

    def on_motion(self, e):
        pass

    def on_wheel(self, e):
        if self.panel != P_NONE and self.panel_items:
            d = -1 if e.delta > 0 else 1
            self.panel_scroll = max(0, self.panel_scroll + d * 2)
            self.redraw()

    def on_right(self, e):
        pass

    def on_key(self, e):
        """物理键盘直接打字（桌面版的主要输入方式）"""
        if not self.visible:
            return
        ks = e.keysym
        ch = e.char
        if ks == 'Escape':
            self.hide()
            return
        if ks == 'BackSpace':
            self.do_key(('⌫', 'del'))
            return
        if ks in ('Return', 'KP_Enter'):
            self.do_key(('↵', 'enter'))
            return
        if ks == 'space':
            if self.cands:
                self.pick(0)
            else:
                self.do_key(('空格', 'space'))
            return
        if ch and ch.isdigit() and self.cands and '1' <= ch <= '9':
            i = int(ch) - 1
            if i < len(self.cands):
                self.pick(i)
                return
        if ch and ('a' <= ch.lower() <= 'z'):
            self.type_letter(ch.lower())
            return
        if ch and ch in '，。':
            self.commit(ch)
            return

    # ------------------------------------------------------------ 逻辑
    def do_key(self, val):
        label, act = val
        if act is None:
            self.type_letter(label)
            return
        if act == 'del':
            if self.code:
                self.code = self.code[:-1]
                self.refresh_cands()
            else:
                self.app.backspace()
            return
        if act == 'enter':
            if self.code:
                self.commit(self.code)      # 上屏编码原文
            else:
                self.commit('\n')
            return
        if act == 'space':
            if self.cands:
                self.pick(0)
            else:
                self.commit(' ')
            return
        if act == 'caps':
            self.caps = not self.caps
            self.clear_code()
            self.redraw()
            return
        if act == 'page_num':
            self.page = 'num'
            self.redraw()
            return
        if act == 'page_sym':
            self.page = 'sym'
            self.redraw()
            return
        if act == 'page_main':
            self.page = 'main'
            self.redraw()
            return

    def type_letter(self, ch):
        if self.caps:
            self.commit(ch.upper())
            return
        if len(self.code) >= 4:
            self.code = ''
        self.code += ch
        self.refresh_cands()

    def clear_code(self):
        self.code = ''
        self.cands = []
        if self.winfo_exists():
            self.redraw()

    def refresh_cands(self):
        if self.code:
            self.cands = self.app.engine.query(self.code, 30)
        else:
            self.cands = []
        self.redraw()

    def pick(self, i):
        if 0 <= i < len(self.cands):
            self.commit(self.cands[i])

    def pick_item(self, i):
        if 0 <= i < len(self.panel_items):
            self.commit(self.panel_items[i])

    def commit(self, text):
        """上屏：展开时间模板 → 写剪贴板 → 粘回原窗口"""
        out = expand(text)
        self.app.commit(out)
        self.clear_code()

    # ------------------------------------------------------------ 工具
    def do_tool(self, tid):
        if tid == 'phrases':
            self.app.open_phrases()
            return
        if tid == 'set':
            self.app.open_settings()
            return
        if tid == 'hide':
            self.hide()
            return
        if tid == 'candminus':
            self.cfg.set('cand_sp', max(8, int(self.cfg.get('cand_sp', 15)) - 1))
            self.cfg.save()
            self.redraw()
            return
        if tid == 'candplus':
            self.cfg.set('cand_sp', min(40, int(self.cfg.get('cand_sp', 15)) + 1))
            self.cfg.save()
            self.redraw()
            return

        p = self._tool_panel(tid)
        if p != P_NONE:
            if self.panel == p:
                self.panel = P_NONE            # 再点一次收起
            else:
                self.panel = p
                self.panel_scroll = 0
                self.panel_items = self.app.panel_items(p)
            self.redraw()
            return

        if tid == 'star':
            self.app.star_current()
            return
        if tid == 'copy':
            self.app.send_ctrl('c')
            return
        if tid == 'cut':
            self.app.send_ctrl('x')
            return
        if tid == 'paste':
            self.app.send_ctrl('v')
            return
        if tid == 'selectall':
            self.app.send_ctrl('a')
            return
        # 光标移动类：切回原窗口后发方向键
        self.app.send_arrow(tid)
