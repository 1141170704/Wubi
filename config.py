# -*- coding: utf-8 -*-
"""
配置：存到 %APPDATA%\\TianFuWubi\\config.json。
"""
import json
import os

APP_DIR = os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'), 'TianFuWubi')
DB_NAME = 'phrases.db'
BACKUP_DIR = 'backup'


def ensure_dirs():
    for d in (APP_DIR, os.path.join(APP_DIR, BACKUP_DIR)):
        os.makedirs(d, exist_ok=True)


def db_path():
    ensure_dirs()
    return os.path.join(APP_DIR, DB_NAME)


def backup_dir():
    ensure_dirs()
    return os.path.join(APP_DIR, BACKUP_DIR)


# ---------------------------------------------------------------- 主题
THEMES = {
    'OLED纯黑': {
        'bg': '#000000', 'key': '#101010', 'key_hi': '#1E1E1E',
        'text': '#FFFFFF', 'dim': '#8A8A8A', 'accent': '#C8905A',
        'bar': '#0A0A0A', 'sel': '#1E2A1E',
    },
    '暗色': {
        'bg': '#161616', 'key': '#262626', 'key_hi': '#333333',
        'text': '#FFFFFF', 'dim': '#9A9A9A', 'accent': '#E0A070',
        'bar': '#1C1C1C', 'sel': '#28323E',
    },
    '灰色': {
        'bg': '#2B2B2B', 'key': '#3C3C3C', 'key_hi': '#4A4A4A',
        'text': '#F2F2F2', 'dim': '#B0B0B0', 'accent': '#D8C090',
        'bar': '#303030', 'sel': '#3A424A',
    },
}
THEME_NAMES = list(THEMES.keys())

# ---------------------------------------------------------------- 工具栏
TOOLS = [
    ('left', '←', '左移'), ('right', '→', '右移'),
    ('up', '↑', '上移'), ('down', '↓', '下移'),
    ('sel', '⇱', '移动即选取'), ('clip', '▤', '剪贴板'),
    ('quick', '⚡', '快捷发送'), ('copy', '⧉', '复制'),
    ('paste', '⇩', '粘贴'), ('cut', '✂', '剪切'),
    ('selectall', '≡', '全选'), ('star', '★', '收藏到快捷'),
    ('time', '⏱', '格式化时间'), ('phrases', '✦', '短语管理'),
    ('candminus', 'A-', '候选字小'), ('candplus', 'A+', '候选字大'),
    ('set', '⚙', '设置'), ('hide', '▾', '隐藏面板'),
]
TOOL_ICON = {i: g for i, g, _ in TOOLS}
TOOL_NAME = {i: n for i, _, n in TOOLS}
DEFAULT_TOOLS = [
    ['left', 'right', 'up', 'down', 'sel'],
    ['clip', 'quick', 'star', 'time', 'phrases', 'candminus', 'candplus'],
    ['copy', 'paste', 'cut', 'selectall', 'set', 'hide'],
]
MAX_GROUP = 6
MAX_ITEM = 16

# ---------------------------------------------------------------- 键盘布局
# (显示, 动作, 宽度权重)；动作 None 表示直接输入该字符
def main_rows(classic=False):
    """
    主键盘。每行权重和统一为 10，这样各行键宽一致、不会错位。
    退格键右上加宽、回车明显加宽（用户要求回车符号加大）。
    """
    rows = []
    rows.append([(c, None, 1.0) for c in 'qwertyuiop'])            # 10
    r1 = [(c, None, 1.0) for c in 'asdfghjkl']
    r1.append(('⌫', 'del', 1.5))                                    # 9 + 1.5
    rows.append(r1)
    r2 = [(c, None, 1.0) for c in 'zxcvbnm']
    r2.append(('↵', 'enter', 3.0))                                  # 7 + 3
    rows.append(r2)
    # 五笔键用得少 → 1.0；123 键常按 → 1.6
    r3 = [('五笔', 'caps', 1.0), ('123', 'page_num', 1.6)]
    if classic:
        r3 += [('空格', 'space', 5.4), ('，', None, 1.0), ('。', None, 1.0)]
    else:
        r3.append(('空格', 'space', 7.4))
    rows.append(r3)
    return rows


def num_rows():
    rows = []
    rows.append([(c, None, 1.0) for c in '1234567890'])             # 10
    r1 = [(c, None, 1.0) for c in '+-*/=%()']
    r1.append(('⌫', 'del', 2.0))                                    # 8 + 2
    rows.append(r1)
    r2 = [('符号', 'page_sym', 1.5)] + [(c, None, 1.0) for c in '@#&_~\'"']
    r2.append(('↵', 'enter', 1.5))                                  # 1.5 + 7 + 1.5
    rows.append(r2)
    r3 = [('五笔', 'caps', 1.0), ('返回', 'page_main', 1.6), ('空格', 'space', 5.4),
          ('，', None, 1.0), ('。', None, 1.0)]
    rows.append(r3)
    return rows


SYM_CHARS = [
    list('~!@#$%^&*()_+'),
    list('`-=[]\\;\',./'),
    list('{}|:"<>?'),
    list('。，、；：？！…—·'),
    list('“”‘’（）【】《》'),
]


def sym_rows():
    """符号页：每行都归一到 10 列，键宽才一致"""
    rows = []
    for line in SYM_CHARS:
        w = 10.0 / max(1, len(line))
        rows.append([(c, None, w) for c in line])
    rows.append([('返回', 'page_main', 1.6), ('空格', 'space', 5.4), ('⌫', 'del', 3.0)])
    return rows


DEFAULTS = {
    'theme': 'OLED纯黑',
    'style': '纯净',                 # 纯净 / 经典
    'tools': DEFAULT_TOOLS,
    'sound': '水滴',
    'vol': 30,
    'letter_sp': 16,
    'cand_sp': 15,
    'tool_icon_sp': 13,
    'kb_height': 250,
    'show_second': True,
    'hotkey_mods': 'ctrl+space',     # 唤起面板的全局热键
    'auto_paste': True,              # 上屏后自动粘贴回原窗口
    'clip_watch': True,              # 监视剪贴板
    'page': 'main',                  # 记住上次键盘页
}


class Config:
    def __init__(self):
        ensure_dirs()
        self.path = os.path.join(APP_DIR, 'config.json')
        self.data = dict(DEFAULTS)
        self.load()

    def load(self):
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                self.data.update(saved)
        except (OSError, ValueError):
            pass
        self._fix()

    def _fix(self):
        """纠正越界值，避免旧配置导致界面异常"""
        if self.data.get('theme') not in THEMES:
            self.data['theme'] = DEFAULTS['theme']
        for k in ('letter_sp', 'cand_sp', 'tool_icon_sp'):
            try:
                self.data[k] = max(8, min(40, int(self.data[k])))
            except (TypeError, ValueError):
                self.data[k] = DEFAULTS[k]
        try:
            self.data['kb_height'] = max(150, min(600, int(self.data.get('kb_height', 250))))
        except (TypeError, ValueError):
            self.data['kb_height'] = 250
        tools = self.data.get('tools')
        if not isinstance(tools, list) or not tools:
            self.data['tools'] = [list(g) for g in DEFAULT_TOOLS]

    def save(self):
        try:
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=1)
        except OSError:
            pass

    def get(self, k, default=None):
        return self.data.get(k, default)

    def set(self, k, v):
        self.data[k] = v

    def theme(self):
        return THEMES.get(self.data.get('theme'), THEMES[DEFAULTS['theme']])
