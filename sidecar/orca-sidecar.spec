# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for OrcaFlow sidecar
#
# Usage: pyinstaller orca-sidecar.spec
# 또는 bundle-sidecar.sh 로 자동 생성됨
#
# 이 파일은 재현성 확보용 참조 spec 이다.
# bundle-sidecar.sh 가 실행 시 PyInstaller CLI 옵션으로 동일한 설정을 전달하므로
# 이 spec 파일을 직접 사용할 필요는 없다.

a = Analysis(
    ['orca_core/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'orca_core',
        'orca_core.ipc',
        'orca_core.ipc.routes',
        'orca_core.ipc.http_app',
        'orca_core.orchestrator',
        'orca_core.providers',
        'orca_core.tools',
        'orca_core.tools.fs',
        'orca_core.tools.shell',
        'orca_core.tools.browser',
        'orca_core.tools.os',
        'orca_core.tools.web',
        'orca_core.tools.register_all',
        'orca_core.tools.registry',
        'orca_core.tools.runtime',
        'orca_core.policy',
        'orca_core.audit',
        'orca_core.journal',
        'orca_core.persistence',
        'orca_core.schema',
        'orca_core.config',
        'orca_core.errors',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'PIL',
        'pytest',
        '_pytest',
        'mypy',
        'ruff',
    ],
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
    name='orca-sidecar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
