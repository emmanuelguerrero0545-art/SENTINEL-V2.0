# -*- mode: python ; coding: utf-8 -*-
# ============================================================
#  SENTINEL v2.0 — PyInstaller Spec
#  Genera: SENTINEL.exe (un solo archivo, Windows x64)
# ============================================================

import os
from pathlib import Path

block_cipher = None

# Ruta base del proyecto
BASE = Path(SPECPATH)

# ── Datos a incluir (source, destino_dentro_del_exe) ────────
datas = [
    # Traducciones
    (str(BASE / 'i18n' / '*.json'),      'i18n'),
    # Fuentes
    (str(BASE / 'fonts' / '*.otf'),      'fonts'),
    # Logos / assets
    (str(BASE / 'assets' / 'logos'),     'assets/logos'),
]

# ── Módulos que PyInstaller no detecta automáticamente ──────
hiddenimports = [
    # scikit-learn
    'sklearn',
    'sklearn.linear_model',
    'sklearn.preprocessing',
    'sklearn.metrics',
    'sklearn.utils._cython_blas',
    'sklearn.neighbors._typedefs',
    'sklearn.neighbors._quad_tree',
    'sklearn.tree._utils',
    # scipy
    'scipy.signal',
    'scipy.stats',
    'scipy.optimize',
    'scipy.special',
    'scipy.linalg',
    'scipy._lib.messagestream',
    # matplotlib backends
    'matplotlib.backends.backend_tkagg',
    'matplotlib.backends._backend_tk',
    'matplotlib.backends.backend_agg',
    # reportlab
    'reportlab',
    'reportlab.lib',
    'reportlab.platypus',
    'reportlab.pdfgen',
    # opencv
    'cv2',
    # joblib
    'joblib',
    # tkinter
    'tkinter',
    'tkinter.ttk',
    'tkinter.filedialog',
    'tkinter.messagebox',
]

# ── Análisis ─────────────────────────────────────────────────
a = Analysis(
    ['BioConnect_App.py'],
    pathex=[str(BASE)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Excluir lo que no se necesita en producción
        'pytest',
        'mypy',
        'IPython',
        'jupyter',
        'notebook',
        'setuptools',
        'pip',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── Ejecutable único ─────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SENTINEL',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,          # compresión UPX si está disponible
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,     # sin ventana de consola (modo GUI)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(BASE / 'assets' / 'logos' / 'sentinel.ico'),
    version_file=None,
)
