# -*- mode: python ; coding: utf-8 -*-


block_cipher = None


a = Analysis(
    ['src/run.py'],
    pathex=[],
    binaries=[('dist/ffmpeg/*', '.')],
    datas=[ ('src/pypeek/icon/*.*', 'icon') ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Peek',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=False,
    icon=['src/pypeek/icon/peek.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Peek',
)
app = BUNDLE(
    coll,
    name='Peek.app',
    icon='src/pypeek/icon/peek.icns',
    bundle_identifier=None,
)
