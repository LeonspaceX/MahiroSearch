# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all

datas = [('E:\\MahiroSearch\\config.yaml', '.'), ('E:\\MahiroSearch\\icon.png', '.'), ('E:\\MahiroSearch\\icon.ico', '.')]
binaries = []
hiddenimports = ['tiktoken_ext.openai_public']
hiddenimports += collect_submodules('watchdog.observers')
hiddenimports += collect_submodules('tiktoken')
hiddenimports += collect_submodules('tiktoken_ext')
tmp_ret = collect_all('qfluentwidgets')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['E:\\MahiroSearch\\main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MahiroSearch',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['E:\\MahiroSearch\\icon.ico'],
)
