# -*- coding: utf-8 -*-
"""
短语库（SQLite）。表结构与 Android 端一致，方便两边备份互导。

    phrase(pid, code, content, weight, ord, mtime, deleted, deltime)
    phrase_tag(pid, tag)
    clip(content UNIQUE, ts)
    meta(k, v)
"""
import json
import os
import sqlite3
import time

TAG_ALL = '全部'
TAG_DEFAULT = '默认'
TAG_QUICK = '快捷发送'
TAG_TIME = '时间'
SYS_TAGS = (TAG_DEFAULT, TAG_QUICK, TAG_TIME)

RECYCLE_DAYS = 30          # 回收站条目保留天数
KEEP_BACKUPS = 15          # 本地备份保留份数


def backup_name(t=None):
    """
    备份文件名：短语库  2026 0925 1624 0526 json
    即「年 月日 时分 秒+周序号」，周一=01 … 周日=07
    """
    t = t or time.localtime()
    week = t.tm_wday + 1                      # 周一=1 … 周日=7
    return '短语库  %04d %02d%02d %02d%02d %02d%02d json' % (
        t.tm_year, t.tm_mon, t.tm_mday,
        t.tm_hour, t.tm_min, t.tm_sec, week)


class Row:
    __slots__ = ('pid', 'code', 'content', 'weight', 'ord', 'mtime', 'tags')

    def __init__(self, pid=0, code='', content='', weight=0, ord_=0, mtime=0, tags=None):
        self.pid = pid
        self.code = code or ''
        self.content = content or ''
        self.weight = weight
        self.ord = ord_
        self.mtime = mtime
        self.tags = tags or []


class Db:
    def __init__(self, path):
        self.path = path
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init()

    # ------------------------------------------------------------ 结构
    def _init(self):
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS phrase(
            pid INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT, content TEXT, weight INTEGER DEFAULT 0,
            ord INTEGER DEFAULT 0, mtime INTEGER,
            deleted INTEGER DEFAULT 0, deltime INTEGER)''')
        c.execute('CREATE TABLE IF NOT EXISTS phrase_tag(pid INTEGER, tag TEXT)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_tag ON phrase_tag(tag)')
        c.execute('CREATE TABLE IF NOT EXISTS clip(content TEXT, ts INTEGER)')
        c.execute('CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)')
        try:
            c.execute('CREATE UNIQUE INDEX IF NOT EXISTS uq_clip ON clip(content)')
        except sqlite3.Error:
            pass
        self.conn.commit()
        self._migrate()

    def _migrate(self):
        """只补结构、绝不删数据；连缺的列也逐列 ALTER 补上"""
        c = self.conn.cursor()
        c.execute("PRAGMA table_info(phrase)")
        cols = {r['name'] for r in c.fetchall()}
        for col, ddl in (('weight', 'INTEGER DEFAULT 0'),
                         ('ord', 'INTEGER DEFAULT 0'),
                         ('mtime', 'INTEGER'),
                         ('deleted', 'INTEGER DEFAULT 0'),
                         ('deltime', 'INTEGER')):
            if col not in cols:
                try:
                    c.execute('ALTER TABLE phrase ADD COLUMN %s %s' % (col, ddl))
                except sqlite3.Error:
                    pass
        self.conn.commit()
        self.purge_recycle()

    # ------------------------------------------------------------ meta
    def get_meta(self, k, default=''):
        c = self.conn.cursor()
        c.execute('SELECT v FROM meta WHERE k=?', (k,))
        r = c.fetchone()
        return r['v'] if r else default

    def set_meta(self, k, v):
        c = self.conn.cursor()
        c.execute('INSERT OR REPLACE INTO meta(k,v) VALUES(?,?)', (k, str(v)))
        self.conn.commit()

    # ------------------------------------------------------------ 查询
    def list(self, tag=TAG_ALL, recycle=False, kw=None):
        c = self.conn.cursor()
        w = ['deleted=%d' % (1 if recycle else 0)]
        args = []
        if not recycle and tag and tag != TAG_ALL:
            w.append('EXISTS(SELECT 1 FROM phrase_tag t WHERE t.pid=p.pid AND t.tag=?)')
            args.append(tag)
        if kw:
            w.append('(content LIKE ? OR code LIKE ?)')
            args.extend(['%%%s%%' % kw, '%%%s%%' % kw])
        order = 'deltime DESC' if recycle else 'ord ASC, pid ASC'
        c.execute('SELECT p.pid,p.code,p.content,p.weight,p.ord,p.mtime FROM phrase p '
                  'WHERE %s ORDER BY %s' % (' AND '.join(w), order), args)
        rows = [r for r in c.fetchall()]
        tm = self._tag_map()
        out = []
        for r in rows:
            out.append(Row(r['pid'], r['code'], r['content'], r['weight'],
                           r['ord'], r['mtime'], tm.get(r['pid'], [])))
        return out

    def _tag_map(self):
        c = self.conn.cursor()
        c.execute('SELECT pid, tag FROM phrase_tag')
        m = {}
        for r in c.fetchall():
            m.setdefault(r['pid'], []).append(r['tag'])
        return m

    def coded(self):
        """带编码的短语（参与输入法候选）；时间模板填了编码也算"""
        out = []
        for r in self.list(TAG_ALL):
            if r.code and r.code.strip() and r.content:
                out.append(r)
        return out

    def contents_of(self, tag):
        return [r.content for r in self.list(tag) if r.content]

    def count_of_tag(self, tag):
        c = self.conn.cursor()
        c.execute('SELECT COUNT(*) n FROM phrase_tag WHERE tag=?', (tag,))
        return c.fetchone()['n']

    def count_all(self):
        c = self.conn.cursor()
        c.execute('SELECT COUNT(*) n FROM phrase WHERE deleted=0')
        return c.fetchone()['n']

    # ------------------------------------------------------------ 写
    def _next_ord_top(self):
        c = self.conn.cursor()
        c.execute('SELECT MIN(ord) m FROM phrase')
        r = c.fetchone()
        return (r['m'] if r and r['m'] is not None else 0) - 10

    def _next_ord_bottom(self):
        c = self.conn.cursor()
        c.execute('SELECT MAX(ord) m FROM phrase')
        r = c.fetchone()
        return (r['m'] if r and r['m'] is not None else 0) + 10

    def insert(self, code, content, tags, weight=0, to_end=False):
        c = self.conn.cursor()
        o = self._next_ord_bottom() if to_end else self._next_ord_top()
        now = int(time.time() * 1000)
        c.execute('INSERT INTO phrase(code,content,weight,ord,mtime,deleted) '
                  'VALUES(?,?,?,?,?,0)', (code or '', content, weight, o, now))
        pid = c.lastrowid
        self._set_tags(pid, tags)
        self.conn.commit()
        return pid

    def insert_ord(self, code, content, tags, weight, ord_):
        """按指定 ord 插入（仅供导入使用，保证恢复后顺序一致）"""
        c = self.conn.cursor()
        now = int(time.time() * 1000)
        c.execute('INSERT INTO phrase(code,content,weight,ord,mtime,deleted) '
                  'VALUES(?,?,?,?,?,0)', (code or '', content, weight, ord_, now))
        pid = c.lastrowid
        self._set_tags(pid, tags)
        self.conn.commit()
        return pid

    def update(self, pid, code, content, tags, weight=None):
        c = self.conn.cursor()
        now = int(time.time() * 1000)
        if weight is None:
            c.execute('UPDATE phrase SET code=?,content=?,mtime=? WHERE pid=?',
                      (code or '', content, now, pid))
        else:
            c.execute('UPDATE phrase SET code=?,content=?,weight=?,mtime=? WHERE pid=?',
                      (code or '', content, weight, now, pid))
        self._set_tags(pid, tags)
        self.conn.commit()

    def _set_tags(self, pid, tags):
        c = self.conn.cursor()
        c.execute('DELETE FROM phrase_tag WHERE pid=?', (pid,))
        seen = set()
        for t in (tags or []):
            t = (t or '').strip()
            if t and t not in seen:
                seen.add(t)
                c.execute('INSERT INTO phrase_tag(pid,tag) VALUES(?,?)', (pid, t))
        self.conn.commit()

    def soft_delete(self, pids):
        now = int(time.time() * 1000)
        c = self.conn.cursor()
        for p in pids:
            c.execute('UPDATE phrase SET deleted=1,deltime=? WHERE pid=?', (now, p))
        self.conn.commit()

    def restore(self, pids):
        c = self.conn.cursor()
        for p in pids:
            c.execute('UPDATE phrase SET deleted=0,deltime=NULL WHERE pid=?', (p,))
        self.conn.commit()

    def hard_delete(self, pids):
        c = self.conn.cursor()
        for p in pids:
            c.execute('DELETE FROM phrase WHERE pid=?', (p,))
            c.execute('DELETE FROM phrase_tag WHERE pid=?', (p,))
        self.conn.commit()

    def recycle_ids(self):
        c = self.conn.cursor()
        c.execute('SELECT pid FROM phrase WHERE deleted=1')
        return [r['pid'] for r in c.fetchall()]

    def purge_recycle(self):
        """回收站 30 天自动清除"""
        limit = int(time.time() * 1000) - RECYCLE_DAYS * 86400 * 1000
        c = self.conn.cursor()
        c.execute('SELECT pid FROM phrase WHERE deleted=1 AND deltime<?', (limit,))
        ids = [r['pid'] for r in c.fetchall()]
        if ids:
            self.hard_delete(ids)
        return len(ids)

    def clear_recycle(self):
        self.hard_delete(self.recycle_ids())

    # ------------------------------------------------------------ 分组
    def all_tags(self):
        c = self.conn.cursor()
        c.execute('SELECT DISTINCT tag FROM phrase_tag ORDER BY tag')
        out = [r['tag'] for r in c.fetchall()]
        for t in self.empty_tags():           # 0 条目的分组也要能选到
            if t not in out:
                out.append(t)
        return out

    def empty_tags(self):
        raw = self.get_meta('emptyTags', '')
        if not raw:
            return []
        try:
            out = json.loads(raw)
            return [x for x in out if isinstance(x, str)]
        except (ValueError, TypeError):
            return []

    def _set_empty(self, lst):
        self.set_meta('emptyTags', json.dumps(lst, ensure_ascii=False))

    def add_empty_tag(self, tag):
        """只建分组、不建词条"""
        t = (tag or '').strip()
        if not t or t in SYS_TAGS:
            return
        lst = self.empty_tags()
        if t not in lst:
            lst.append(t)
            self._set_empty(lst)
        order = self.tag_order()
        if t not in order:
            order.append(t)
            self.set_tag_order(order)

    def remove_empty_tag(self, tag):
        lst = self.empty_tags()
        if tag in lst:
            lst.remove(tag)
            self._set_empty(lst)

    def drop_tag(self, tag):
        """摘掉标签，词条本身保留"""
        self.remove_empty_tag(tag)
        c = self.conn.cursor()
        c.execute('DELETE FROM phrase_tag WHERE tag=?', (tag,))
        self.conn.commit()

    def rename_tag(self, old, new):
        lst = self.empty_tags()
        if old in lst:
            lst[lst.index(old)] = new
            self._set_empty(lst)
        c = self.conn.cursor()
        c.execute('UPDATE phrase_tag SET tag=? WHERE tag=?', (new, old))
        self.conn.commit()

    def tag_order(self):
        raw = self.get_meta('tagOrder', '')
        order = []
        if raw:
            try:
                order = [x for x in json.loads(raw) if isinstance(x, str)]
            except (ValueError, TypeError):
                order = []
        have = set(self.all_tags())
        out = [t for t in order if t in have and t not in SYS_TAGS]
        for t in sorted(have):
            if t not in SYS_TAGS and t not in out:
                out.append(t)
        return out

    def set_tag_order(self, order):
        self.set_meta('tagOrder', json.dumps(order, ensure_ascii=False))

    # ------------------------------------------------------------ 时间模板
    def ensure_time(self, templates):
        """增量补齐时间模板；且模板只打「时间」一个标签"""
        from engine import expand as _e      # 避免循环导入
        del _e
        # 清理历史副标签：时间条目只保留 TAG_TIME
        for r in self.list(TAG_TIME):
            if len(r.tags) > 1:
                self._set_tags(r.pid, [TAG_TIME])
        exist = {r.content for r in self.list(TAG_TIME)}
        for content, _label in templates:
            if content not in exist:
                self.insert('', content, [TAG_TIME], 0, to_end=True)

    # ------------------------------------------------------------ 剪贴板
    def add_clip(self, content):
        if not content:
            return
        c = self.conn.cursor()
        try:
            c.execute('INSERT OR IGNORE INTO clip(content,ts) VALUES(?,?)',
                      (content, int(time.time() * 1000)))
            self.conn.commit()
        except sqlite3.Error:
            pass

    def clips(self, limit=60):
        c = self.conn.cursor()
        c.execute('SELECT content FROM clip ORDER BY ts DESC LIMIT ?', (limit,))
        return [r['content'] for r in c.fetchall()]

    def clear_clips(self):
        c = self.conn.cursor()
        c.execute('DELETE FROM clip')
        self.conn.commit()

    # ------------------------------------------------------------ 导入导出
    def export_obj(self):
        arr = []
        for r in self.list(TAG_ALL):
            arr.append({'code': r.code, 'content': r.content,
                        'weight': r.weight, 'ord': r.ord, 'tags': r.tags})
        return {'v': 1, 'time': int(time.time() * 1000), 'phrases': arr}

    def export_json(self, path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.export_obj(), f, ensure_ascii=False, indent=1)
        return path

    def export_txt(self, path):
        """按分组分块输出，# 开头为分组名"""
        parts = []
        tags = [TAG_DEFAULT] + self.tag_order()
        for t in tags:
            items = [r for r in self.list(t) if r.content]
            if not items:
                continue
            parts.append('#' + t)
            for r in items:
                parts.append('%s\t%s' % (r.code or '', r.content))
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(parts) + '\n')
        return path

    def import_text(self, text):
        if not text or not text.strip():
            return 0
        s = text.strip()
        if s.startswith('{'):
            return self._import_json(s)
        return self._import_txt(s)

    def _import_txt(self, text):
        n = 0
        tag = TAG_DEFAULT
        base = self._next_ord_bottom()
        for line in text.split('\n'):
            ln = line.strip()
            if not ln:
                continue
            if ln.startswith('#'):
                name = ln[1:].strip()
                if name and not name.startswith('TianFu'):
                    tag = name
                continue
            if '\t' in ln:
                code, content = ln.split('\t', 1)
            elif ' ' in ln:
                code, content = ln.split(' ', 1)
            else:
                code, content = '', ln
            code, content = code.strip(), content.strip()
            if not content:
                continue
            self.insert_ord(code, content, [tag], 0, base + n * 10)
            n += 1
        return n

    def _import_json(self, text):
        try:
            root = json.loads(text)
        except ValueError:
            return 0
        arr = root.get('phrases') or []
        n = 0
        base = self._next_ord_bottom()
        for o in arr:
            content = o.get('content') or ''
            if not content:
                continue
            tags = o.get('tags') or [TAG_DEFAULT]
            self.insert_ord(o.get('code') or '', content, tags,
                            o.get('weight') or 0, base + n * 10)
            n += 1
        return n

    def close(self):
        try:
            self.conn.close()
        except sqlite3.Error:
            pass
