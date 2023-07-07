# -*- mode: python -*-
import os
import site
from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata

block_cipher = None

# Need to specially handle these snowflakes
webrtcvad_path = None

site_dirs = site.getsitepackages()

# Add explicit site packages
rhasspy_site_packages = os.environ.get("RHASSPY_SITE_PACKAGES")
if rhasspy_site_packages:
    site_dirs = [rhasspy_site_packages] + site_dirs

# Add virtual environment site packages
venv_path = os.environ.get("VIRTUAL_ENV")
if venv_path:
    venv_lib = Path(venv_path) / "lib"
    for venv_python_dir in venv_lib.glob("python*"):
        venv_site_dir = venv_python_dir / "site-packages"
        if venv_site_dir.is_dir():
            site_dirs.append(venv_site_dir)

# Look for compiled artifacts
for site_dir in site_dirs:
    site_dir = Path(site_dir)
    webrtcvad_paths = list(site_dir.glob("_webrtcvad.*.so"))
    if webrtcvad_paths:
        webrtcvad_path = webrtcvad_paths[0]
        break

assert webrtcvad_path, "Missing webrtcvad"

a = Analysis(
    [Path.cwd() / "__main__.py"],
    pathex=["."],
    binaries=[(webrtcvad_path, ".")],
    datas=copy_metadata("webrtcvad"),
    hiddenimports=["pkg_resources.py2_warn"],
    hookspath=[],
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
    name="rhasspyasr_whisper_hermes",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="rhasspyasr_whisper_hermes",
)
