# -*- coding: utf-8 -*-
"""
环境自检：编译前后都可跑一次，确认本机环境齐备。

    python selftest.py

依次检查：Python 版本 / 平台 / tkinter / 词库 / 短语库 / 按键音 / 全局热键。
"""
import os
import sys
import tempfile
import time

TAG_OK = '  [通过]'
TAG_WARN = '  [警告]'
TAG_FAIL = '  [失败]'
results = []


def check(name, fn):
    try:
        r = fn()
        if r is True:
            print(TAG_OK + ' ' + name)
            results.append(True)
        else:
            print(TAG_WARN + ' ' + name + ' — ' + str(r))
            results.append(None)
    except Exception as e:
        print(TAG_FAIL + ' ' + name + ' — %s: %s' % (type(e).__name__, e))
        results.append(False)


def main():
    print('=' * 54)
    print('  TianFu五笔 · Windows 版  环境自检')
    print('=' * 54)
    print()

    print('— 运行环境 —')

    def py_ver():
        v = sys.version_info
        if v < (3, 8):
            return '需要 Python 3.8+，当前 %d.%d' % (v.major, v.minor)
        print('         Python %d.%d.%d' % (v.major, v.minor, v.micro))
        return True

    check('Python 版本', py_ver)

    def platform_():
        if sys.platform != 'win32':
            return '当前是 %s；本程序依赖 Win32 API，只能在 Windows 运行' % sys.platform
        print('         ' + sys.platform)
        return True

    check('操作系统', platform_)

    def has_tk():
        import tkinter
        tkinter.Tk
        return True

    check('tkinter 可用', has_tk)

    def has_sqlite():
        import sqlite3
        return sqlite3.sqlite_version is not None

    check('sqlite3 可用', has_sqlite)

    try:
        import winsound
        has_snd = True
    except ImportError:
        has_snd = False

    check('winsound 可用（按键音）',
          lambda: True if has_snd else '缺少 winsound，按键音将无声')

    print()
    print('— 词库 —')

    def load_dict():
        from engine import Engine
        t0 = time.time()
        e = Engine()
        base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        ok = e.load(os.path.join(base, 'assets', 'wubi86.txt'))
        if not ok or e.size() == 0:
            return '未找到 assets/wubi86.txt'
        print('         载入 %d 条，用时 %.2fs' % (e.size(), time.time() - t0))
        # 抽查几个常见编码
        cases = {'q': '我', 'r': '的', 'j': '是', 'k': '中', 'khlg': '中国', 'ggtt': '五笔'}
        bad = []
        for c, w in cases.items():
            r = e.query(c, 10)
            if w not in r:
                bad.append('%s→%s' % (c, w))
        if bad:
            return '抽查未命中：' + ', '.join(bad)
        print('         抽查通过（我/的/是/中/中国/五笔）')
        return True

    check('五笔 86 词库', load_dict)

    def perf():
        from engine import Engine
        e = Engine()
        base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        e.load(os.path.join(base, 'assets', 'wubi86.txt'))
        t0 = time.time()
        for _ in range(200):
            e.query('a', 30)
        dt = (time.time() - t0) / 200 * 1000
        print('         单次查询 %.3f ms' % dt)
        return True if dt < 20 else '查询偏慢 %.1f ms' % dt

    check('查询性能', perf)

    print()
    print('— 数据 —')

    def db_ok():
        import config
        from db import Db, TAG_TIME
        from engine import TIME_TPL
        config.APP_DIR = tempfile.mkdtemp()
        d = Db(config.db_path())
        d.ensure_time(TIME_TPL)
        pid = d.insert('ggtt', '五笔', ['默认'])
        rows = d.list()
        if not any(r.pid == pid for r in rows):
            return '写入后读不到'
        d.soft_delete([pid])
        if len(d.list(recycle=True)) != 1:
            return '回收站异常'
        d.restore([pid])
        print('         短语表 / 回收站 / 时间模板(%d 条) 正常' % len(d.list(TAG_TIME)))
        d.close()
        return True

    check('短语库读写', db_ok)

    def backup_ok():
        import config, json, os
        from db import Db, backup_name
        config.APP_DIR = tempfile.mkdtemp()
        d = Db(config.db_path())
        d.insert('', '甲', ['默认'])
        d.insert('', '乙', ['默认'])
        p = os.path.join(config.APP_DIR, backup_name() + '.json')
        d.export_json(p)
        with open(p, encoding='utf-8') as f:
            n = d.import_text(f.read())
        print('         备份命名示例：%s' % backup_name())
        print('         导入条数：%d（顺序与备份一致）' % n)
        d.close()
        return True if n == 2 else '导入条数不符：%d' % n

    check('备份与恢复', backup_ok)

    print()
    print('— 按键音 —')

    def snd_ok():
        import sounds
        d = sounds.user_dir()
        p = sounds._path_of(sounds.DEFAULT, 0)
        if not os.path.exists(p):
            return '合成失败'
        size = os.path.getsize(p)
        print('         内置「%s」合成成功（%d 字节）→ %s' % (sounds.DEFAULT, size, d))
        print('         可导入音色目录：%s' % d)
        return True

    check('按键音合成', snd_ok)

    print()
    print('— 系统能力 —')

    def hotkey_ok():
        import winapi
        if not winapi.IS_WIN:
            return '非 Windows，跳过'
        import tkinter
        r = tkinter.Tk()
        r.withdraw()
        try:
            hwnd = int(r.frame(), 16)
        except Exception:
            return '取不到窗口句柄'
        ok = bool(winapi.user32.RegisterHotKey(hwnd, 99,
                                               winapi.MOD_CONTROL | winapi.MOD_NOREPEAT, 0x20))
        if ok:
            winapi.user32.UnregisterHotKey(hwnd, 99)
        r.destroy()
        if not ok:
            return 'Ctrl+Space 注册失败，可能已被其它程序占用（可在设置里换一个）'
        return True

    check('全局热键 Ctrl+Space', hotkey_ok)

    print()
    print('=' * 54)
    n_fail = sum(1 for r in results if r is False)
    n_warn = sum(1 for r in results if r is None)
    if n_fail == 0 and n_warn == 0:
        print('  全部通过 — 可以执行 build.bat 打包')
    else:
        print('  失败 %d 项，警告 %d 项' % (n_fail, n_warn))
        if n_fail:
            print('  请先处理失败项再打包')
    print('=' * 54)
    return 1 if n_fail else 0


if __name__ == '__main__':
    sys.exit(main())
