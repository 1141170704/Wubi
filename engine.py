# -*- coding: utf-8 -*-
"""
五笔 86 引擎。

词库 8.6 万条，若按「所有前缀建索引」会占用几十 MB，
这里沿用 Android 端的做法：按编码排序的数组 + 二分定位前缀区间，
查询 O(log n + 命中数)，内存只有几个数组。

排序规则：码长升序（简码优先）→ 权重降序（常用优先）。
"""
import os
import time
from bisect import bisect_left

CODE_MAX = 4


def _fmt(t, pattern):
    """按 strftime 模式格式化，避免频繁创建结构"""
    return time.strftime(pattern, t)


class Engine:
    def __init__(self):
        self.codes = []      # 按编码排序
        self.words = []
        self.weights = []
        self.n = 0
        self._cache = {}     # 打字是增量式的（a→ab→abc），缓存后重复查询几乎零成本

    @property
    def ready(self):
        return self.n > 0

    def size(self):
        return self.n

    def load(self, path):
        """加载码表。格式：编码<TAB>内容[\\t权重]，# 开头为注释"""
        rows = []
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.rstrip('\n').rstrip('\r')
                    if not line or line.startswith('#'):
                        continue
                    i = line.find('\t')
                    if i <= 0:
                        continue
                    code = line[:i].strip().lower()
                    if not code or len(code) > CODE_MAX:
                        continue
                    if not ('a' <= code[0] <= 'y'):
                        continue
                    if any(not ('a' <= c <= 'z') for c in code):
                        continue
                    rest = line[i + 1:]
                    j = rest.find('\t')
                    if j >= 0:
                        word = rest[:j].strip()
                        try:
                            w = int(rest[j + 1:].strip())
                        except ValueError:
                            w = 0
                    else:
                        word = rest.strip()
                        w = 0
                    if not word:
                        continue
                    rows.append((code, word, w))
        except OSError:
            return False

        # 按编码排序（简码自然在前，因为短编码字符串比较更小）
        rows.sort(key=lambda r: r[0])
        self.codes = [r[0] for r in rows]
        self.words = [r[1] for r in rows]
        self.weights = [r[2] for r in rows]
        self.n = len(rows)
        return True

    def query(self, code, limit=30):
        """查询候选：简码优先、常用优先"""
        out = []
        if not code or self.n == 0:
            return out
        c = code.lower().strip()
        if not c:
            return out

        key = (c, limit)
        cached = self._cache.get(key)
        if cached is not None:
            return list(cached)

        start = bisect_left(self.codes, c)
        # 前缀区间内先找出最短码长，优先收齐简码，可大幅减少排序量
        hits = []
        lens = []
        i = start
        while i < self.n and self.codes[i].startswith(c):
            lens.append(len(self.codes[i]))
            i += 1
        if not lens:
            self._cache[key] = out
            return out

        # 按码长升序收集（同长度内权重降序），避免对全区间排序
        order = sorted(range(start, start + len(lens)),
                       key=lambda k: (lens[k - start], -self.weights[k]))
        seen = set()
        for k in order:
            w = self.words[k]
            if w not in seen:
                seen.add(w)
                out.append(w)
                if len(out) >= limit:
                    break

        if len(self._cache) > 512:
            self._cache.clear()
        self._cache[key] = out
        return list(out)


# ---------------------------------------------------------------- 时间模板
def expand(tpl, t=None):
    """
    时间短语模板上屏时动态展开。
    占位符：{yyyy}{MM}{dd}{HH}{mm}{ss}{week}{w}{W}{date}{time}{now}
    {w}：1=周一 … 6=周六，7=周日（中国习惯）
    """
    if not tpl or '{' not in tpl:
        return tpl or ''
    t = t or time.localtime()
    # weekday(): 周一=0 … 周日=6
    wd = t.tm_wday
    wk_cn = ('一', '二', '三', '四', '五', '六', '日')
    w_num = wd + 1                      # 1=周一 … 7=周日
    m = {
        '{yyyy}': _fmt(t, '%Y'),
        '{MM}': _fmt(t, '%m'),
        '{dd}': _fmt(t, '%d'),
        '{HH}': _fmt(t, '%H'),
        '{mm}': _fmt(t, '%M'),
        '{ss}': _fmt(t, '%S'),
        '{week}': '周' + wk_cn[wd],
        '{w}': str(w_num),
        '{W}': str(w_num),
        '{date}': _fmt(t, '%Y年%m月%d日'),
        '{time}': _fmt(t, '%H:%M'),
        '{now}': _fmt(t, '%Y-%m-%d %H:%M:%S'),
    }
    out = tpl
    for k, v in m.items():
        out = out.replace(k, v)
    return out


TIME_TPL = [
    ('{yyyy}年{MM}月{dd}日', '日期'),
    ('{yyyy}-{MM}-{dd}', '短日期'),
    ('{HH}:{mm}', '时间'),
    ('{HH}:{mm}:{ss}', '时间秒'),
    ('{yyyy}-{MM}-{dd} {HH}:{mm}', '日期时间'),
    ('{yyyy}-{MM}-{dd} {HH}:{mm}:{ss}', '完整时间'),
    ('{week}', '星期'),
    ('{yyyy}年{MM}月{dd}日 {week}', '日期星期'),
    ('{now}', '时间戳'),
    ('{w}', '周数字'),
    ('{yyyy}-{MM}-{dd} 周{w}', '日期周数字'),
    ('{yyyy}{MM}{dd}', '紧凑日期'),
]
