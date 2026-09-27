# -*- coding: utf-8 -*-
"""
按键音：程序化合成 WAV（零音频资源、零第三方依赖），用 winsound 异步播放。

内置 1 个「水滴」；其余音色由用户导入 wav（16bit PCM）。
合成模型沿用移动端：正弦分量 × 指数衰减包络，末尾做峰值归一化。
"""
import math
import os
import struct
import threading
import wave

try:
    import winsound
except ImportError:              # 非 Windows 环境（便于模块自检）
    winsound = None

SR = 44100
DEFAULT = '水滴'
BUILTIN = (DEFAULT,)
USER_PREFIX = 'u_'
CACHE_PREFIX = 'b_'


def _cache_dir():
    base = os.environ.get('APPDATA') or os.path.expanduser('~')
    d = os.path.join(base, 'TianFuWubi', 'sounds')
    os.makedirs(d, exist_ok=True)
    return d


def _pitch_mul(which):
    if which == 1:
        return 0.85            # 空格低一点
    if which == 2:
        return 0.92            # 回车重一点
    if which == 3:
        return 1.18            # 删除轻一点
    return 1.0


def _len_mul(which):
    if which == 1:
        return 1.2
    if which == 2:
        return 1.1
    if which == 3:
        return 0.8
    return 1.0


def _sample(name, t, tms, pm):
    """单点采样。内置只有水滴：音高快速下滑的正弦 + 极快衰减"""
    f = (1400.0 - 900.0 * (tms / 130.0)) * pm
    return math.sin(2 * math.pi * f * t) * math.exp(-tms / 22.0) * 0.9


def synth(name, which=0):
    """合成指定音色的采样列表。which: 0字母 1空格 2回车 3删除"""
    pm = _pitch_mul(which)
    lm = _len_mul(which)
    dur = 130.0 * lm
    n = max(64, int(SR * dur / 1000.0))
    buf = []
    peak = 0.0
    for i in range(n):
        t = i / float(SR)
        tms = t * 1000.0
        v = _sample(name, t, tms, pm)
        # 淡入淡出，避免爆音
        fade_in = min(1.0, tms / 0.6)
        fade_out = max(0.0, min(1.0, (dur - tms) / 3.0))
        v *= fade_in * fade_out
        buf.append(v)
        a = abs(v)
        if a > peak:
            peak = a
    gain = 0.8 / peak if peak > 1e-4 else 1.0
    return [max(-1.0, min(1.0, v * gain)) for v in buf]


def write_wav(path, samples):
    data = bytearray()
    for s in samples:
        v = max(-1.0, min(1.0, s))
        data += struct.pack('<h', int(v * 32767))
    hdr = b'RIFF' + struct.pack('<I', 36 + len(data)) + b'WAVE'
    hdr += b'fmt ' + struct.pack('<IHHIIHH', 16, 1, 1, SR, SR * 2, 2, 16)
    hdr += b'data' + struct.pack('<I', len(data))
    with open(path, 'wb') as f:
        f.write(hdr + bytes(data))
    return path


def is_builtin(name):
    return name in BUILTIN


def desc(name):
    if name == DEFAULT:
        return '清亮水滴，音高快速下滑（内置，不可删除）'
    return ''


def user_dir():
    d = os.path.join(_cache_dir())
    return d


def user_file(name):
    safe = ''.join(c if c not in '\\/:*?"<>|' else '_' for c in (name or ''))
    return os.path.join(user_dir(), USER_PREFIX + safe + '.wav')


def list_sounds():
    """内置 + 用户导入。目录里 b_ 开头的是合成缓存，不能当音色名显示"""
    out = list(BUILTIN)
    d = user_dir()
    try:
        names = os.listdir(d)
    except OSError:
        names = []
    extra = []
    for fn in names:
        if not fn.endswith('.wav'):
            continue
        if not fn.startswith(USER_PREFIX):
            continue
        extra.append(fn[len(USER_PREFIX):-4])
    extra.sort(key=lambda s: s.lower())
    return out + extra


def import_wav(src_path, name=None):
    """导入一个 wav 文件。返回展示名，失败返回 None"""
    try:
        with wave.open(src_path) as w:
            pass
    except (wave.Error, OSError, EOFError):
        return None
    base = name or os.path.splitext(os.path.basename(src_path))[0]
    dst = user_file(base)
    k = 1
    while os.path.exists(dst):
        dst = user_file('%s_%d' % (base, k))
        base = '%s_%d' % (base, k)
        k += 1
    try:
        with open(src_path, 'rb') as f:
            data = f.read()
        with open(dst, 'wb') as f:
            f.write(data)
    except OSError:
        return None
    return base


def delete(names):
    """删除导入的音色（内置不可删），返回删除数"""
    n = 0
    for s in names:
        if is_builtin(s):
            continue
        p = user_file(s)
        try:
            if os.path.exists(p):
                os.remove(p)
                n += 1
        except OSError:
            pass
    return n


def export(names, out_dir):
    """导出为 wav 到指定目录，返回导出成功的文件数"""
    os.makedirs(out_dir, exist_ok=True)
    ok = 0
    for s in names:
        try:
            if is_builtin(s):
                p = os.path.join(out_dir, s + '.wav')
                write_wav(p, synth(s, 0))
            else:
                src = user_file(s)
                if not os.path.exists(src):
                    continue
                with open(src, 'rb') as f:
                    data = f.read()
                with open(os.path.join(out_dir, s + '.wav'), 'wb') as f:
                    f.write(data)
            ok += 1
        except OSError:
            pass
    return ok


def clean_cache():
    """清掉内置音色的旧合成缓存（b_ 前缀）"""
    d = user_dir()
    try:
        for fn in os.listdir(d):
            if fn.startswith(CACHE_PREFIX) and fn.endswith('.wav'):
                try:
                    os.remove(os.path.join(d, fn))
                except OSError:
                    pass
    except OSError:
        pass


def _path_of(name, which):
    """返回可直接播放的 wav 路径；内置音色先合成落盘"""
    if is_builtin(name):
        p = os.path.join(user_dir(), CACHE_PREFIX + str(abs(hash((name, which)))) + '.wav')
        if not os.path.exists(p):
            write_wav(p, synth(name, which))
        return p
    return user_file(name)


def play(name, which=0, vol=0.3):
    """
    异步播放一声。vol 为 0~1；winsound 不支持音量，
    这里通过「静音档跳过 + 音量过低时用 Beep 兜底」尽量体现差异。
    """
    if not name or name == '无' or vol <= 0 or winsound is None:
        return False
    try:
        p = _path_of(name, which)
        if not p or not os.path.exists(p):
            return False
        winsound.PlaySound(p, winsound.SND_FILENAME | winsound.SND_ASYNC)
        return True
    except (OSError, RuntimeError):
        return False
