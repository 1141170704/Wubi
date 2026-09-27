# -*- coding: utf-8 -*-
"""
把各种来源的短语文件 → 转换成 APK（手机端 TianFu五笔）能直接导入的 JSON，
并且**完整保留分组**。

用法一（推荐，图形界面）：
    双击运行，点「选择文件」，选好就转。

用法二（命令行）：
    python 转APK导入.py 输入.txt [输出.json]
    python 转APK导入.py phrases.db
    python 转APK导入.py 词库.txt --dict --max 8000

支持的输入：
    · PC 版 phrases.db（SQLite，最完整：连分组顺序、空分组都在）
    · PC 版 / 手机端导出的 JSON 备份
    · txt：`#分组名` 分节，下面每行 `编码<TAB>内容`
    · CSV：表头含 分组/标签/编码/内容 等列名，自动识别
    · 五笔词库：编码<TAB>内容<TAB>权重，可自动按首字母或码长分组

输  出：
    <原名>_apk.json —— UTF-8 无 BOM，手机端「导入 txt/JSON」直接选它
"""
import csv
import json
import os
import re
import sqlite3
import sys

# ---------------------------------------------------------------- 常量
SYS_TAGS = ('默认', '快捷发送', '时间', '剪贴板')
# CSV 表头的常见写法（小写比较）
COL_TAG = ('分组', '标签', '分类', 'tag', 'tags', 'group', 'category', '类型')
COL_CODE = ('编码', '码', '简码', 'code', 'key', '五笔')
COL_CONTENT = ('内容', '短语', '文本', '词条', 'content', 'text', 'value', '正文', '句子')
COL_WEIGHT = ('权重', '频度', 'weight', 'freq', '排序')

# 词库自动分组策略
DICT_BY_INITIAL = 'initial'   # 按编码首字母 a-y 分 25 组
DICT_BY_LEN = 'len'           # 按码长：一级简码/二级简码/三级简码/全码
DICT_BY_FREQ = 'freq'         # 按权重：常用/次常用/生僻
DICT_NONE = 'none'            # 不分组，全部进「默认」


# ---------------------------------------------------------------- 工具
def norm(s):
    return (s or '').strip()


def guess_cols(header):
    """把 CSV 表头映射到 标准字段名"""
    low = [norm(h).lower() for h in header]
    m = {}
    for i, h in enumerate(low):
        if i in m.values():
            continue
        if h in COL_TAG or any(h == x for x in COL_TAG):
            m.setdefault('tag', i)
        elif h in COL_CODE or any(h == x for x in COL_CODE):
            m.setdefault('code', i)
        elif h in COL_CONTENT or any(h == x for x in COL_CONTENT):
            m.setdefault('content', i)
        elif h in COL_WEIGHT or any(h == x for x in COL_WEIGHT):
            m.setdefault('weight', i)
    return m


def split_multi(v):
    """一个单元格里可能有多个分组：「工作;常用」或「工作/常用」"""
    v = norm(v)
    if not v:
        return []
    parts = re.split(r'[;；、,，/|]+', v)
    return [p.strip() for p in parts if p.strip()]


class Item:
    __slots__ = ('code', 'content', 'weight', 'tags', 'ord')

    def __init__(self, code='', content='', weight=0, tags=None, ord_=0):
        self.code = norm(code)
        self.content = norm(content)
        self.weight = weight
        self.tags = tags or []
        self.ord = ord_

    def to_json(self):
        return {
            'code': self.code,
            'content': self.content,
            'weight': int(self.weight or 0),
            'tags': self.tags,
        }


# ---------------------------------------------------------------- 各种解析
CODE_RE = re.compile(r'^[a-y]{1,4}$')


def _looks_like_dict_row(s):
    """码表行：编码<TAB>内容[\t权重]，首列是 1~4 位小写字母"""
    p = s.split('\t')
    if len(p) < 2:
        return False
    if not CODE_RE.match(p[0].strip().lower()):
        return False
    if not p[1].strip():
        return False
    if len(p) >= 3:
        try:
            float(p[2].strip())
        except ValueError:
            return False
    return True


def _parse_plain(src, dict_mode, limit):
    """
    纯文本可能是两种东西，必须分开：
      · 码表：编码<TAB>内容<TAB>权重（8.6 万行，开头也有 # 注释）
      · 分节文本：#分组名 下面挂短语
    之前只看"有没有 # 行"就判成分节文本，
    结果整份码表被塞进一个叫「可整体替换…」的分组里。
    改成统计码表行占比来判断。
    """
    with open(src, 'r', encoding='utf-8-sig', errors='ignore') as f:
        lines = [h for h in (ln.rstrip('\n') for ln in f) if h.strip()]
    total = 0
    hit = 0
    for s in lines[:400]:
        if s.strip().startswith('#'):
            continue
        total += 1
        if _looks_like_dict_row(s):
            hit += 1
    ratio = (hit / total) if total else 0

    if total and ratio >= 0.6:
        items, extra = from_dict(src, dict_mode, limit)
        return items, extra, '码表'
    items, extra = from_txt(src)
    if items:
        return items, extra, '分节文本'
    items, extra = from_dict(src, dict_mode, limit)
    return items, extra, '码表'



def from_db(path):
    """PC 版 phrases.db：最完整，连分组顺序和空分组都能带出来"""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT pid,code,content,weight,ord FROM phrase '
              'WHERE deleted=0 ORDER BY ord ASC, pid ASC')
    rows = c.fetchall()                 # 先取出来：下面还要复用同一个游标
    tm = {}
    c.execute('SELECT pid,tag FROM phrase_tag')
    for r in c.fetchall():
        tm.setdefault(r['pid'], []).append(r['tag'])

    items = []
    for i, r in enumerate(rows):
        tags = tm.get(r['pid']) or ['默认']
        items.append(Item(r['code'] or '', r['content'] or '',
                          r['weight'] or 0, tags, i))

    meta = {}
    try:
        c.execute('SELECT k,v FROM meta')
        for r in c.fetchall():
            meta[r['k']] = r['v']
    except sqlite3.Error:
        pass
    conn.close()

    extra = {}
    for k in ('tagOrder', 'emptyTags'):
        v = meta.get(k)
        if v:
            try:
                extra[k] = json.loads(v)
            except ValueError:
                pass
    return items, extra


def from_json(path):
    """PC 版 / 手机端导出的 JSON 备份"""
    with open(path, 'r', encoding='utf-8-sig', errors='ignore') as f:
        root = json.load(f)
    arr = root.get('phrases') or []
    items = []
    for i, o in enumerate(arr):
        if not isinstance(o, dict):
            continue
        tags = o.get('tags') or ['默认']
        if isinstance(tags, str):
            tags = split_multi(tags)
        items.append(Item(o.get('code', ''), o.get('content', ''),
                          o.get('weight', 0), tags, i))
    extra = {k: root[k] for k in ('tagOrder', 'emptyTags') if k in root}
    return items, extra


def from_txt(path):
    """#分组名 分节；每行 编码<TAB>内容 或 编码 空格 内容 或 只有内容"""
    with open(path, 'r', encoding='utf-8-sig', errors='ignore') as f:
        lines = f.read().split('\n')
    items = []
    tag = '默认'
    n = 0
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if s.startswith('#'):
            name = s[1:].strip()
            # 分组名一般很短；长句子（词库头的说明、导出注释）不能当分组
            if (name and len(name) <= 16 and ' ' not in name
                    and not name.startswith('TianFu')
                    and not any(ch in name for ch in '，。：:、；;')):
                tag = name
            continue
        code, content = '', s
        if '\t' in s:
            a, b = s.split('\t', 1)
            code, content = a.strip(), b.strip()
        elif ' ' in s:
            a, b = s.split(' ', 1)
            # 只有前半段像编码（纯字母且不长）才当成编码
            if a and len(a) <= 4 and a.isalpha():
                code, content = a.strip(), b.strip()
        if not content:
            continue
        items.append(Item(code, content, 0, [tag], n))
        n += 1
    return items, {}


def from_csv(path):
    with open(path, 'r', encoding='utf-8-sig', errors='ignore', newline='') as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            delim = csv.Sniffer().sniff(sample, delimiters=',;\t|').delimiter
        except csv.Error:
            delim = ','
        rows = list(csv.reader(f, delimiter=delim))
    if not rows:
        return [], {}
    header = rows[0]
    m = guess_cols(header)
    if 'content' not in m:
        # 没表头，退化成 txt 解析
        return from_txt(path)

    items = []
    n = 0
    for r in rows[1:]:
        if not r or not any(norm(x) for x in r):
            continue

        def g(k):
            i = m.get(k)
            return r[i] if (i is not None and i < len(r)) else ''

        content = norm(g('content'))
        if not content:
            continue
        tags = split_multi(g('tag')) or ['默认']
        try:
            w = int(float(norm(g('weight')) or 0))
        except ValueError:
            w = 0
        items.append(Item(g('code'), content, w, tags, n))
        n += 1
    return items, {}


def _dict_tag(code, weight, mode):
    if mode == DICT_NONE:
        return '默认'
    if mode == DICT_BY_INITIAL:
        return (code[:1].upper() + '部') if code else '默认'
    if mode == DICT_BY_LEN:
        return {1: '一级简码', 2: '二级简码', 3: '三级简码'}.get(len(code), '全码')
    if mode == DICT_BY_FREQ:
        if weight >= 100000000:
            return '常用'
        if weight >= 1000000:
            return '次常用'
        return '生僻'
    return '默认'


def from_dict(path, mode=DICT_BY_INITIAL, limit=0):
    """五笔码表：编码<TAB>内容[\\t权重]"""
    rows = []
    with open(path, 'r', encoding='utf-8-sig', errors='ignore') as f:
        for ln in f:
            s = ln.strip()
            if not s or s.startswith('#'):
                continue
            p = s.split('\t')
            if len(p) < 2:
                continue
            code = p[0].strip().lower()
            content = p[1].strip()
            if not code or not content:
                continue
            try:
                w = int(float(p[2].strip())) if len(p) > 2 else 0
            except (ValueError, IndexError):
                w = 0
            rows.append((code, content, w))
    # 权重高的排前面，limit 时优先保留常用的
    rows.sort(key=lambda r: -r[2])
    if limit and len(rows) > limit:
        rows = rows[:limit]
    items = []
    for i, (code, content, w) in enumerate(rows):
        items.append(Item(code, content, w, [_dict_tag(code, w, mode)], i))
    return items, {}


# ---------------------------------------------------------------- 输出
def build_json(items, extra=None):
    root = {'v': 1, 'phrases': [it.to_json() for it in items]}
    if extra:
        root.update(extra)
    return root


def write_json(path, root):
    """关键：UTF-8 **不带 BOM**。
    手机端靠 text.startsWith("{") 判断是不是 JSON，
    带 BOM 的话首字符是 \\ufeff，会被误判成 txt，导入就废了。"""
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(root, f, ensure_ascii=False, indent=1)


def report(items, extra):
    """转换报告"""
    cnt = {}
    for it in items:
        for t in it.tags:
            cnt[t] = cnt.get(t, 0) + 1
    lines = []
    lines.append('总条数：%d' % len(items))
    lines.append('分组数：%d' % len(cnt))
    lines.append('')
    order = (extra or {}).get('tagOrder')
    names = [t for t in order if t in cnt] if order else \
        sorted(cnt, key=lambda x: -cnt[x])
    for t in names:
        lines.append('   %-16s %d 条' % (t, cnt[t]))
    for t in sorted(cnt):
        if t not in names:
            lines.append('   %-16s %d 条' % (t, cnt[t]))
    empty = (extra or {}).get('emptyTags') or []
    empty = [t for t in empty if t not in cnt]
    if empty:
        lines.append('')
        lines.append('空分组（无词条，手机端不会显示）：%s' % '、'.join(empty))
    return '\n'.join(lines)


# ---------------------------------------------------------------- 主流程
def convert(src, out=None, dict_mode=DICT_BY_INITIAL, limit=0):
    ext = os.path.splitext(src)[1].lower()
    extra = {}
    if ext in ('.db', '.sqlite', '.sqlite3'):
        items, extra = from_db(src)
        kind = 'PC版数据库'
    elif ext == '.json':
        items, extra = from_json(src)
        kind = 'JSON 备份'
    elif ext == '.csv':
        items, extra = from_csv(src)
        kind = 'CSV 表格'
    else:
        items, extra, kind = _parse_plain(src, dict_mode, limit)

    if not items:
        return None, '没解析出任何条目，检查一下文件格式'

    if not out:
        base = os.path.splitext(src)[0]
        out = base + '_apk.json'
    root = build_json(items, extra)
    write_json(out, root)
    return out, '来源：%s\n%s' % (kind, report(items, extra))


# ---------------------------------------------------------------- 图形界面
def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext

    root = tk.Tk()
    root.title('转成 APK 可导入的 JSON')
    root.geometry('640x480')
    root.configure(bg='#161616')

    state = {'src': None}

    def pick():
        p = filedialog.askopenfilename(
            title='选择要转换的文件',
            filetypes=[('所有支持', '*.db *.json *.txt *.csv *.tsv'),
                       ('数据库', '*.db'), ('JSON', '*.json'),
                       ('文本', '*.txt'), ('CSV', '*.csv'), ('全部', '*.*')])
        if not p:
            return
        state['src'] = p
        lab.config(text=os.path.basename(p), fg='#FFFFFF')
        btn_go.config(state=tk.NORMAL)

    def go():
        try:
            out, msg = convert(state['src'], None, mode.get(), 0)
        except Exception as e:
            messagebox.showerror('失败', '%s: %s' % (type(e).__name__, e))
            return
        if not out:
            messagebox.showwarning('没结果', msg)
            return
        txt.delete('1.0', tk.END)
        txt.insert(tk.END, '已生成：%s\n\n%s' % (out, msg))
        messagebox.showinfo('完成', '已生成：\n%s\n\n把这个 json 传到手机，'
                                    '在短语管理里「导入 txt/JSON」选它即可。' % out)

    top = tk.Frame(root, bg='#1C1C1C')
    top.pack(fill=tk.X)
    tk.Label(top, text='把短语文件转成手机能导入的 JSON（保留分组）',
             fg='#FFFFFF', bg='#1C1C1C', font=('Microsoft YaHei UI', 12, 'bold')
             ).pack(padx=10, pady=8, anchor='w')

    bar = tk.Frame(root, bg='#161616')
    bar.pack(fill=tk.X, padx=10, pady=6)
    tk.Button(bar, text='选择文件', command=pick, bg='#262626', fg='#FFFFFF',
              relief=tk.FLAT, padx=14, pady=6, font=('Microsoft YaHei UI', 10),
              activebackground='#333333').pack(side=tk.LEFT)
    lab = tk.Label(bar, text='（还没选）', fg='#9A9A9A', bg='#161616',
                   font=('Microsoft YaHei UI', 10))
    lab.pack(side=tk.LEFT, padx=10)

    btn_go = tk.Button(bar, text='开始转换', command=go, bg='#262626',
                       fg='#E0A070', relief=tk.FLAT, padx=14, pady=6,
                       font=('Microsoft YaHei UI', 10), state=tk.DISABLED,
                       activebackground='#333333')
    btn_go.pack(side=tk.LEFT)

    tk.Label(root, text='纯码表（无分组）时按什么分组：', fg='#9A9A9A',
             bg='#161616', font=('Microsoft YaHei UI', 9)).pack(anchor='w', padx=10)
    mode = tk.StringVar(value=DICT_BY_INITIAL)
    fr = tk.Frame(root, bg='#161616')
    fr.pack(fill=tk.X, padx=10)
    for t, v in (('编码首字母', DICT_BY_INITIAL), ('码长（简码/全码）', DICT_BY_LEN),
                 ('常用程度', DICT_BY_FREQ), ('不分（全部默认）', DICT_NONE)):
        tk.Radiobutton(fr, text=t, variable=mode, value=v, bg='#161616',
                       fg='#FFFFFF', selectcolor='#262626',
                       activebackground='#161616',
                       font=('Microsoft YaHei UI', 9)).pack(side=tk.LEFT, padx=4)

    txt = scrolledtext.ScrolledText(root, bg='#101010', fg='#FFFFFF',
                                    relief=tk.FLAT, font=('Consolas', 10),
                                    insertbackground='#FFFFFF')
    txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

    root.mainloop()


def main():
    args = [a for a in sys.argv[1:]]
    if not args:
        try:
            gui()
        except ImportError:
            print('没有 tkinter，请用命令行方式：')
            print('   python 转APK导入.py 输入文件')
        return
    src = args[0]
    out = None
    mode = DICT_BY_INITIAL
    limit = 0
    i = 1
    while i < len(args):
        a = args[i]
        if a == '--dict':
            mode = DICT_BY_INITIAL
        elif a.startswith('--mode='):
            mode = a.split('=', 1)[1]
        elif a == '--max' and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 1
        elif not a.startswith('-'):
            out = a
        i += 1
    try:
        o, msg = convert(src, out, mode, limit)
    except Exception as e:
        print('失败：%s: %s' % (type(e).__name__, e))
        return
    if not o:
        print(msg)
        return
    print('已生成：%s' % o)
    print(msg)


if __name__ == '__main__':
    main()
