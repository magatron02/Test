"""
Standalone entry point for PyInstaller.
Fixes paths when running as a frozen executable.
"""
import sys
import os
from pathlib import Path

# When frozen by PyInstaller, sys._MEIPASS is the bundle dir (read-only).
# User-writable dirs (config, data, models) must be next to the .exe.
if getattr(sys, 'frozen', False):
    _EXE_DIR = Path(sys.executable).parent
    _BUNDLE_DIR = Path(sys._MEIPASS)
    # Point config/data/models to dirs next to the exe
    os.environ['TRADER_BASE_DIR'] = str(_EXE_DIR)
    # Copy example config if settings.yml is missing
    cfg_dir = _EXE_DIR / 'config'
    cfg_dir.mkdir(exist_ok=True)
    settings_yml = cfg_dir / 'settings.yml'
    example_yml  = _BUNDLE_DIR / 'config' / 'settings.example.yml'
    if not settings_yml.exists() and example_yml.exists():
        import shutil
        shutil.copy(example_yml, settings_yml)
    # Ensure data and models dirs exist
    (_EXE_DIR / 'data').mkdir(exist_ok=True)
    (_EXE_DIR / 'models').mkdir(exist_ok=True)

# Import and run
from src.main import main
main()
