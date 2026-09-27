# -*- coding: utf-8 -*-
"""
短语管理窗口。

顶部：搜索框（原来的标题位置）
其上：批量管理栏（可横滑，勾选后批量生效）
中部：分组标签 + 条目列表（复选框在第二行，右侧三个操作按钮）
底部：新建 / 备份恢复 / 分组管理 / 回收站
"""
import os
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

import config
from config import backup_dir
from db import (TAG_ALL, TAG_DEFAULT, TAG_QUICK, TAG_TIME, SYS_TAGS, backup_name)

FONT_CN = 'Microsoft YaHei UI'


def fmt_time(ms):
    if not ms:
        return ''
    return time.strftime('%Y-%m-%d %H:%M', time.localtime(ms / 1000.0))


class PhraseWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.console)
        self.app = app
        self.db = app.db
        th = app.cfg.theme()
        self.th = th
        self.title('短语管理')
        self.geometry('780x560')
        self.configure(bg=th['bg'])

        self.cur_tag = TAG_ALL
        self.kw = ''
        self.sel = set()
        self.batch = False
        self.recycle = False
        self.data = []
        self.row_frames = []

        self._build()
        self.reload()

    # ------------------------------------------------------------ 构建
    def _build(self):
        th = self.th
        top = tk.Frame(self, bg=th['bar'])
        top.pack(fill=tk.X)

        # 搜索框（占据原来的标题位置）
        self.search_var = tk.StringVar()
        e = tk.Entry(top, textvariable=self.search_var, bg=th['key'], fg=th['text'],
                     relief=tk.FLAT, insertbackground=th['text'],
                     font=(FONT_CN, 11))
        e.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, pady=8, ipady=4)
        e.bind('<KeyRelease>', lambda ev: self.on_search())
        self.entry_search = e
        self._hint(e, '搜索编码或内容…')

        self._btn(top, '＋', self.add_new).pack(side=tk.LEFT, padx=2)
        self._btn(top, '☁', self.open_backup).pack(side=tk.LEFT, padx=2)
        self._btn(top, '⊞', self.tag_manage).pack(side=tk.LEFT, padx=2)
        self._btn(top, '⌫', self.toggle_recycle).pack(side=tk.LEFT, padx=(2, 8))

        # 批量管理栏（顶部，可横滑）
        self.batch_bar = tk.Frame(self, bg=th['bar'])
        self._build_batch()

        # 分组标签
        self.tag_bar = tk.Frame(self, bg=th['bg'])
        self.tag_bar.pack(fill=tk.X, padx=6, pady=(4, 2))

        # 列表（Canvas + Frame 实现滚动）
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

        # 底栏
        bot = tk.Frame(self, bg=th['bar'])
        bot.pack(fill=tk.X)
        self.status = tk.Label(bot, text='', fg=th['dim'], bg=th['bar'],
                               font=(FONT_CN, 9), anchor='w')
        self.status.pack(side=tk.LEFT, padx=8, pady=5)
        self._btn(bot, '批量管理', self.toggle_batch).pack(side=tk.RIGHT, padx=4)
        self._btn(bot, '显示/隐藏第二行', self.toggle_second).pack(side=tk.RIGHT, padx=4)

    def _hint(self, entry, text):
        entry.insert(0, text)
        entry.config(fg=self.th['dim'])

        def on_in(ev):
            if entry.get() == text:
                entry.delete(0, tk.END)
                entry.config(fg=self.th['text'])

        def on_out(ev):
            if not entry.get():
                entry.insert(0, text)
                entry.config(fg=self.th['dim'])

        entry.bind('<FocusIn>', on_in)
        entry.bind('<FocusOut>', on_out)

    def _btn(self, parent, text, cmd, w=None):
        th = self.th
        b = tk.Button(parent, text=text, command=cmd, bg=th['key'], fg=th['text'],
                      relief=tk.FLAT, bd=0, padx=10, pady=4, width=w,
                      activebackground=th['key_hi'], activeforeground=th['text'],
                      font=(FONT_CN, 10))
        return b

    def _build_batch(self):
        th = self.th
        for w in self.batch_bar.winfo_children():
            w.destroy()
        items = [('全选', self.sel_all), ('清空选择', self.sel_none),
                 ('批量删除', self.batch_delete),
                 ('加入分组…', self.batch_add_tag), ('移到分组…', self.batch_move_tag),
                 ('移出分组…', self.batch_remove_tag),
                 ('上移', self.batch_up), ('下移', self.batch_down)]
        for t, cmd in items:
            self._btn(self.batch_bar, t, cmd).pack(side=tk.LEFT, padx=3, pady=3)

    # ------------------------------------------------------------ 数据
    def reload(self):
        try:
            self.data = self.db.list(self.cur_tag, self.recycle, self.kw)
        except Exception as ex:
            messagebox.showerror('错误', '读取失败：%s' % ex)
            self.data = []
        self.render_tags()
        self.render_list()
        self.status.config(text='共 %d 条%s' % (len(self.data),
                                                '（回收站）' if self.recycle else ''))

    def on_search(self):
        v = self.search_var.get()
        self.kw = '' if v == '搜索编码或内容…' else v.strip()
        self.reload()

    def render_tags(self):
        th = self.th
        for w in self.tag_bar.winfo_children():
            w.destroy()
        tags = [TAG_ALL, TAG_DEFAULT] + self.db.tag_order()
        for t in tags:
            on = (t == self.cur_tag)
            b = tk.Button(self.tag_bar, text=t, bg=th['key_hi'] if on else th['key'],
                          fg=th['accent'] if on else th['text'],
                          relief=tk.FLAT, bd=0, padx=10, pady=3,
                          activebackground=th['key_hi'],
                          font=(FONT_CN, 10, 'bold' if on else 'normal'),
                          command=lambda x=t: self.select_tag(x))
            b.pack(side=tk.LEFT, padx=(0, 5))

    def select_tag(self, t):
        self.cur_tag = t
        self.render_tags()          # 只重画标签，不重建页面（标签行不会跳位）
        self.reload()

    def toggle_batch(self):
        self.batch = not self.batch
        if self.batch:
            self.batch_bar.pack(fill=tk.X, after=self.wrap, before=None)
            self.batch_bar.pack_configure(before=self.tag_bar)
        else:
            self.batch_bar.pack_forget()
            self.sel.clear()
        self.render_list()

    def toggle_recycle(self):
        self.recycle = not self.recycle
        self.reload()

    def toggle_second(self):
        self.app.cfg.set('show_second', not self.app.cfg.get('show_second', True))
        self.app.cfg.save()
        self.render_list()

    # ------------------------------------------------------------ 列表
    def render_list(self):
        for w in self.inner.winfo_children():
            w.destroy()
        th = self.th
        show2 = self.app.cfg.get('show_second', True)

        for r in self.data:
            row = tk.Frame(self.inner, bg=th['bg'])
            row.pack(fill=tk.X, padx=6, pady=1)
            on = r.pid in self.sel

            if self.batch:
                v = tk.BooleanVar(value=on)
                cb = tk.Checkbutton(row, variable=v, bg=th['bg'], fg=th['text'],
                                    selectcolor=th['key'], activebackground=th['bg'],
                                    command=lambda p=r.pid, vv=v: self.toggle_sel(p, vv.get()))
                cb.pack(side=tk.LEFT)

            txt = tk.Frame(row, bg=th['key'] if on else th['bg'])
            txt.pack(side=tk.LEFT, fill=tk.X, expand=True)

            line1 = (('[%s] ' % r.code) if r.code else '') + (r.content or '')
            tk.Label(txt, text=line1, fg=th['text'], bg=th['key'] if on else th['bg'],
                     font=(FONT_CN, 12), anchor='w', justify=tk.LEFT,
                     wraplength=520).pack(fill=tk.X, padx=6, pady=(4, 0))

            if show2:
                tags = ' '.join('#' + t for t in r.tags)
                tk.Label(txt, text='%s   %s' % (tags, fmt_time(r.mtime)),
                         fg=th['dim'], bg=th['key'] if on else th['bg'],
                         font=(FONT_CN, 9), anchor='w').pack(fill=tk.X, padx=6, pady=(0, 4))

            ops = tk.Frame(row, bg=th['bg'])
            ops.pack(side=tk.RIGHT)
            self._btn(ops, '复制', lambda c=r.content: self.copy(c)).pack(side=tk.LEFT, padx=2)
            self._btn(ops, '编辑', lambda p=r: self.edit(p)).pack(side=tk.LEFT, padx=2)
            self._btn(ops, '删除', lambda p=r.pid: self.delete(p)).pack(side=tk.LEFT, padx=2)

        self.inner.update_idletasks()
        self.cv.configure(scrollregion=self.cv.bbox('all'))

    def toggle_sel(self, pid, val):
        if val:
            self.sel.add(pid)
        else:
            self.sel.discard(pid)
        self.render_list()

    def sel_all(self):
        self.sel = {r.pid for r in self.data}
        self.render_list()

    def sel_none(self):
        self.sel.clear()
        self.render_list()

    # ------------------------------------------------------------ 单条操作
    def copy(self, content):
        import winapi
        winapi.set_clipboard_text(content)
        self.app.last_clip = content
        self.status.config(text='已复制')

    def add_new(self):
        EditDialog(self, '新建短语', None, self.db, lambda code, content, tags: (
            self.db.insert(code, content, tags), self.reload()))

    def edit(self, r):
        EditDialog(self, '编辑短语', r, self.db,
                   lambda code, content, tags: (
                       self.db.update(r.pid, code, content, tags), self.reload()))

    def delete(self, pid):
        if self.recycle:
            if messagebox.askyesno('彻底删除', '永久删除该条目？'):
                self.db.hard_delete([pid])
                self.reload()
            return
        if messagebox.askyesno('删除', '删除后进入回收站（30 天后自动清除）'):
            self.db.soft_delete([pid])
            self.reload()

    # ------------------------------------------------------------ 批量
    def _pick_tag(self, title):
        tags = [t for t in self.db.tag_order()]
        if not tags:
            messagebox.showinfo('提示', '还没有分组')
            return None
        return TagChoice(self, title, tags).result

    def batch_delete(self):
        if not self.sel:
            return messagebox.showinfo('提示', '先勾选条目')
        if self.recycle:
            if messagebox.askyesno('彻底删除', '永久删除 %d 条？' % len(self.sel)):
                self.db.hard_delete(list(self.sel))
        else:
            if messagebox.askyesno('删除', '删除 %d 条？' % len(self.sel)):
                self.db.soft_delete(list(self.sel))
        self.sel.clear()
        self.reload()

    def batch_add_tag(self):
        """追加标签（保留原有）"""
        t = self._pick_tag('加入哪个分组')
        if not t or not self.sel:
            return
        for pid in self.sel:
            row = next((r for r in self.data if r.pid == pid), None)
            tags = list(row.tags) if row else []
            if t not in tags:
                tags.append(t)
            self.db.update(pid, row.code if row else '',
                           row.content if row else '', tags)
        self.reload()

    def batch_move_tag(self):
        """替换标签（只留目标分组）"""
        t = self._pick_tag('移到哪个分组')
        if not t or not self.sel:
            return
        for pid in self.sel:
            row = next((r for r in self.data if r.pid == pid), None)
            if row:
                self.db.update(pid, row.code, row.content, [t])
        self.reload()

    def batch_remove_tag(self):
        t = self._pick_tag('移出哪个分组')
        if not t or not self.sel:
            return
        for pid in self.sel:
            row = next((r for r in self.data if r.pid == pid), None)
            if not row:
                continue
            tags = [x for x in row.tags if x != t] or [TAG_DEFAULT]
            self.db.update(pid, row.code, row.content, tags)
        self.reload()

    def batch_up(self):
        self._shift(-1)

    def batch_down(self):
        self._shift(1)

    def _shift(self, d):
        if not self.sel:
            return
        rows = self.db.list(self.cur_tag, self.recycle, self.kw)
        ids = [r.pid for r in rows]
        picked = [p for p in ids if p in self.sel]
        if not picked:
            return
        rest = [p for p in ids if p not in self.sel]
        if d < 0:
            first = ids.index(picked[0])
            if first == 0:
                return
            prev = rest[rest.index(ids[first - 1])]
            out = []
            for p in rest:
                if p == prev:
                    out.extend(picked)
                    out.append(p)
                else:
                    out.append(p)
        else:
            last = ids.index(picked[-1])
            if last >= len(ids) - 1:
                return
            nxt = ids[last + 1]
            out = []
            for p in rest:
                out.append(p)
                if p == nxt:
                    out.extend(picked)
        base = 0
        for p in out:
            self.db.conn.execute('UPDATE phrase SET ord=? WHERE pid=?', (base, p))
            base += 10
        self.db.conn.commit()
        self.reload()

    # ------------------------------------------------------------ 分组管理
    def tag_manage(self):
        TagManager(self, self.db, self.reload)

    def open_backup(self):
        BackupWindow(self, self.app, self.reload)


# ---------------------------------------------------------------- 编辑对话框
class EditDialog(tk.Toplevel):
    def __init__(self, parent, title, row, db, on_ok):
        super().__init__(parent)
        self.db = db
        self.on_ok = on_ok
        th = parent.th
        self.th = th
        self.title(title)
        self.geometry('620x300')
        self.configure(bg=th['bg'])
        self.transient(parent)

        tk.Label(self, text='编码（可空，填了就能用编码直接打出来）',
                 fg=th['dim'], bg=th['bg'], font=(FONT_CN, 9)).pack(anchor='w', padx=12, pady=(10, 2))
        self.e_code = tk.Entry(self, bg=th['key'], fg=th['text'], relief=tk.FLAT,
                               insertbackground=th['text'], font=(FONT_CN, 11))
        self.e_code.pack(fill=tk.X, padx=12, ipady=4)
        self.e_code.bind('<Return>', lambda e: self.e_content.focus())

        tk.Label(self, text='内容', fg=th['dim'], bg=th['bg'],
                 font=(FONT_CN, 9)).pack(anchor='w', padx=12, pady=(8, 2))
        self.e_content = tk.Entry(self, bg=th['key'], fg=th['text'], relief=tk.FLAT,
                                  insertbackground=th['text'], font=(FONT_CN, 11))
        self.e_content.pack(fill=tk.X, padx=12, ipady=4)

        tk.Label(self, text='分组标签（可多选）', fg=th['dim'], bg=th['bg'],
                 font=(FONT_CN, 9)).pack(anchor='w', padx=12, pady=(8, 2))
        self.tag_frame = tk.Frame(self, bg=th['bg'])
        self.tag_frame.pack(fill=tk.X, padx=12)
        self.tag_vars = {}
        self._build_tags()

        btns = tk.Frame(self, bg=th['bg'])
        btns.pack(fill=tk.X, pady=12)
        ok_text = '保存' if row else '保存'
        tk.Button(btns, text=ok_text, command=self.save, bg=th['key'], fg=th['text'],
                  relief=tk.FLAT, padx=16, pady=5, font=(FONT_CN, 10),
                  activebackground=th['key_hi']).pack(side=tk.RIGHT, padx=12)
        if not row:
            tk.Button(btns, text='保存并继续', command=lambda: self.save(keep=True),
                      bg=th['key'], fg=th['accent'], relief=tk.FLAT, padx=16, pady=5,
                      font=(FONT_CN, 10), activebackground=th['key_hi']).pack(side=tk.RIGHT)
        tk.Button(btns, text='取消', command=self.destroy, bg=th['key'], fg=th['dim'],
                  relief=tk.FLAT, padx=16, pady=5, font=(FONT_CN, 10)).pack(side=tk.RIGHT, padx=6)

        if row:
            self.e_code.insert(0, row.code or '')
            self.e_content.insert(0, row.content or '')
            for t in row.tags:
                if t in self.tag_vars:
                    self.tag_vars[t].set(True)
        self.e_content.focus()
        self.grab_set()

    def _build_tags(self):
        th = self.th
        for t in [TAG_DEFAULT] + self.db.tag_order():
            v = tk.BooleanVar()
            self.tag_vars[t] = v
            tk.Checkbutton(self.tag_frame, text=t, variable=v, bg=th['bg'],
                           fg=th['text'], selectcolor=th['key'],
                           activebackground=th['bg'], font=(FONT_CN, 10)).pack(
                side=tk.LEFT, padx=(0, 6))

    def save(self, keep=False):
        code = self.e_code.get().strip()
        content = self.e_content.get().strip()
        tags = [t for t, v in self.tag_vars.items() if v.get()]
        if not content:
            messagebox.showinfo('提示', '内容不能为空')
            return
        if not tags:
            tags = [TAG_DEFAULT]
        self.on_ok(code, content, tags)
        if keep:
            self.e_code.delete(0, tk.END)
            self.e_content.delete(0, tk.END)
            self.e_code.focus()
        else:
            self.destroy()


# ---------------------------------------------------------------- 分组选择
class TagChoice(tk.Toplevel):
    def __init__(self, parent, title, tags):
        super().__init__(parent)
        self.result = None
        th = parent.th
        self.title(title)
        self.configure(bg=th['bg'])
        self.transient(parent)
        for t in tags:
            tk.Button(self, text=t, bg=th['key'], fg=th['text'], relief=tk.FLAT,
                      padx=14, pady=6, font=(FONT_CN, 10), activebackground=th['key_hi'],
                      command=lambda x=t: self.pick(x)).pack(fill=tk.X, padx=10, pady=2)
        self.grab_set()
        self.wait_window()

    def pick(self, t):
        self.result = t
        self.destroy()


# ---------------------------------------------------------------- 分组管理
class TagManager(tk.Toplevel):
    """分组管理：新建 / 改名 / 删除 / 排序"""

    def __init__(self, parent, db, on_change):
        super().__init__(parent)
        self.db = db
        self.on_change = on_change
        th = parent.th
        self.th = th
        self.title('分组管理')
        self.geometry('520x420')
        self.configure(bg=th['bg'])
        self.transient(parent)
        self.sel = set()

        bar = tk.Frame(self, bg=th['bar'])
        bar.pack(fill=tk.X)
        for t, cmd in (('＋新建', self.new_tag), ('✎改名', self.rename),
                       ('✕删除', self.remove), ('↑上移', self.up), ('↓下移', self.down)):
            tk.Button(bar, text=t, command=cmd, bg=th['key'], fg=th['text'],
                      relief=tk.FLAT, padx=10, pady=4, font=(FONT_CN, 10),
                      activebackground=th['key_hi']).pack(side=tk.LEFT, padx=3, pady=4)

        self.box = tk.Frame(self, bg=th['bg'])
        self.box.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        self.render()

    def render(self):
        for w in self.box.winfo_children():
            w.destroy()
        th = self.th
        for t in [TAG_DEFAULT] + self.db.tag_order():
            row = tk.Frame(self.box, bg=th['key'] if t in self.sel else th['bg'])
            row.pack(fill=tk.X, pady=1)
            v = tk.BooleanVar(value=(t in self.sel))
            tk.Checkbutton(row, variable=v, bg=th['bg'], selectcolor=th['key'],
                           activebackground=th['bg'],
                           command=lambda x=t, vv=v: self.toggle(x, vv.get())).pack(side=tk.LEFT)
            sys = t in SYS_TAGS
            tk.Label(row, text='%s（%d）%s' % (t, self.db.count_of_tag(t),
                                              '· 内置' if sys else ''),
                     fg=th['text'] if not sys else '#8AB4DC', bg=row['bg'],
                     font=(FONT_CN, 11), anchor='w').pack(side=tk.LEFT, padx=4)

    def toggle(self, t, v):
        if v:
            self.sel.add(t)
        else:
            self.sel.discard(t)
        self.render()

    def new_tag(self):
        t = simpledialog.askstring('新建分组', '分组名', parent=self)
        if t and t.strip():
            self.db.add_empty_tag(t.strip())
            self.on_change()
            self.render()

    def rename(self):
        if len(self.sel) != 1:
            return messagebox.showinfo('提示', '请只勾选一个')
        old = list(self.sel)[0]
        if old in SYS_TAGS:
            return messagebox.showinfo('提示', '内置分组不可改名')
        new = simpledialog.askstring('改名', '新名称', initialvalue=old, parent=self)
        if new and new.strip():
            self.db.rename_tag(old, new.strip())
            self.sel.clear()
            self.on_change()
            self.render()

    def remove(self):
        if not self.sel:
            return messagebox.showinfo('提示', '先勾选分组')
        delable = [t for t in self.sel if t not in SYS_TAGS]
        if not delable:
            return messagebox.showinfo('提示', '内置分组不可删除')
        if not messagebox.askyesno('删除分组', '将删除 %d 个分组（只摘掉标签，短语本身不删除）'
                                    % len(delable)):
            return
        order = self.db.tag_order()
        for t in delable:
            self.db.drop_tag(t)
        self.db.set_tag_order([x for x in order if x not in self.sel])
        self.sel.clear()
        self.on_change()
        self.render()

    def up(self):
        self._move(-1)

    def down(self):
        self._move(1)

    def _move(self, d):
        if not self.sel:
            return messagebox.showinfo('提示', '先勾选分组')
        order = self.db.tag_order()
        picked = [t for t in order if t in self.sel]
        rest = [t for t in order if t not in self.sel]
        if d < 0:
            first = order.index(picked[0])
            if first == 0:
                return
            prev = order[first - 1]
            out = []
            for t in rest:
                if t == prev:
                    out.extend(picked)
                    out.append(t)
                else:
                    out.append(t)
        else:
            last = order.index(picked[-1])
            if last >= len(order) - 1:
                return
            nxt = order[last + 1]
            out = []
            for t in rest:
                out.append(t)
                if t == nxt:
                    out.extend(picked)
        self.db.set_tag_order(out)
        self.on_change()
        self.render()


# ---------------------------------------------------------------- 备份与恢复
class BackupWindow(tk.Toplevel):
    """本地历史 + 导入导出文件"""

    def __init__(self, parent, app, on_change):
        super().__init__(parent)
        self.app = app
        self.db = app.db
        self.on_change = on_change
        th = parent.th
        self.th = th
        self.title('备份与恢复')
        self.geometry('600x440')
        self.configure(bg=th['bg'])
        self.transient(parent)

        bar = tk.Frame(self, bg=th['bar'])
        bar.pack(fill=tk.X)
        for t, cmd in (('立即备份', self.do_backup), ('导入文件…', self.do_import),
                       ('导出 txt', lambda: self.do_export('txt')),
                       ('导出 JSON', lambda: self.do_export('json'))):
            tk.Button(bar, text=t, command=cmd, bg=th['key'], fg=th['text'],
                      relief=tk.FLAT, padx=10, pady=5, font=(FONT_CN, 10),
                      activebackground=th['key_hi']).pack(side=tk.LEFT, padx=3, pady=5)

        tk.Label(self, text='本地历史（最近 15 份，点「恢复」覆盖当前库）',
                 fg=th['dim'], bg=th['bg'], font=(FONT_CN, 9)).pack(anchor='w', padx=10, pady=(8, 2))
        self.box = tk.Frame(self, bg=th['bg'])
        self.box.pack(fill=tk.BOTH, expand=True, padx=8)
        self.render()

    def render(self):
        for w in self.box.winfo_children():
            w.destroy()
        th = self.th
        d = backup_dir()
        try:
            files = sorted([f for f in os.listdir(d) if f.endswith('.json')], reverse=True)
        except OSError:
            files = []
        if not files:
            tk.Label(self.box, text='（还没有备份）', fg=th['dim'], bg=th['bg'],
                     font=(FONT_CN, 10)).pack(anchor='w', padx=4, pady=6)
            return
        for fn in files[:15]:
            row = tk.Frame(self.box, bg=th['bg'])
            row.pack(fill=tk.X, pady=1)
            path = os.path.join(d, fn)
            n = self._count(path)
            tk.Label(row, text='%s    %d 条' % (fn, n), fg=th['text'], bg=th['bg'],
                     font=(FONT_CN, 10), anchor='w').pack(side=tk.LEFT)
            tk.Button(row, text='恢复', bg=th['key'], fg=th['accent'], relief=tk.FLAT,
                      padx=10, font=(FONT_CN, 9), activebackground=th['key_hi'],
                      command=lambda p=path: self.do_restore(p)).pack(side=tk.RIGHT)

    def _count(self, path):
        try:
            import json
            with open(path, 'r', encoding='utf-8') as f:
                return len(json.load(f).get('phrases') or [])
        except Exception:
            return 0

    def do_backup(self):
        d = backup_dir()
        fn = backup_name() + '.json'
        try:
            self.db.export_json(os.path.join(d, fn))
            self._trim()
            self.render()
            messagebox.showinfo('完成', '已备份：%s' % fn)
        except OSError as ex:
            messagebox.showerror('失败', str(ex))

    def _trim(self):
        d = backup_dir()
        try:
            files = sorted([f for f in os.listdir(d) if f.endswith('.json')], reverse=True)
            for fn in files[15:]:
                try:
                    os.remove(os.path.join(d, fn))
                except OSError:
                    pass
        except OSError:
            pass

    def do_restore(self, path):
        if not messagebox.askyesno('恢复', '将用该备份覆盖当前短语库，确定？'):
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                n = self.db.import_text(f.read())
            self.on_change()
            messagebox.showinfo('完成', '已恢复 %d 条' % n)
        except OSError as ex:
            messagebox.showerror('失败', str(ex))

    def do_import(self):
        p = filedialog.askopenfilename(filetypes=[('文本/JSON', '*.txt *.json'),
                                                  ('所有文件', '*.*')])
        if not p:
            return
        try:
            with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                n = self.db.import_text(f.read())
            self.on_change()
            messagebox.showinfo('完成', '已导入 %d 条' % n)
        except OSError as ex:
            messagebox.showerror('失败', str(ex))

    def do_export(self, kind):
        p = filedialog.asksaveasfilename(defaultextension='.' + kind,
                                         initialfile=backup_name() + '.' + kind,
                                         filetypes=[(kind.upper(), '*.' + kind)])
        if not p:
            return
        try:
            if kind == 'json':
                self.db.export_json(p)
            else:
                self.db.export_txt(p)
            messagebox.showinfo('完成', '已导出：%s' % p)
        except OSError as ex:
            messagebox.showerror('失败', str(ex))
