# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置（单文件 exe，无控制台窗口）。

    pyinstaller TianFuWubi.spec --noconfirm
"""
import os

ROOT = os.path.abspath(SPECPATH)

# 词库打进包内，程序用 sys._MEIPASS 定位
datas = [
    (os.path.join(ROOT, 'assets', 'wubi86.txt'), 'assets'),
]

hiddenimports = [
    'tkinter',
    'tkinter.ttk',
    'tkinter.font',
    'sqlite3',
    'winsound',
    'engine',
    'db',
    'config',
    'sounds',
    'winapi',
    'ui_keyboard',
    'ui_phrase',
    'ui_settings',
]

excludes = [
    'PyQt5', 'PySide2', 'PySide6', 'matplotlib', 'numpy', 'pandas',
    'PIL', 'scipy', 'IPython', 'notebook', 'pytest', 'setuptools',
    'pip', 'wheel', 'PyInstaller', 'tkinter.test',
]

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TianFuWubi',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # 无控制台窗口（后台常驻）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
