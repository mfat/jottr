# -*- mode: python ; coding: utf-8 -*-
import sys
import os
import shutil
from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

# Collect all necessary packages
packages = ['PyQt5', 'PyQtWebEngine', 'spellchecker', 'feedparser']
binaries = []
datas = []
hiddenimports = []

# Add PyQt5 resources explicitly
try:
    import PyQt5
    qt_path = os.path.dirname(PyQt5.__file__)
    
    # Try different possible Qt resource locations
    qt_locations = [
        os.path.join(qt_path, "Qt5"),  # Standard location
        os.path.join(qt_path, "Qt"),   # Alternative location
    ]
    
    qt_dir = None
    for loc in qt_locations:
        if os.path.exists(loc):
            qt_dir = loc
            break
    
    if qt_dir:
        print(f"Found Qt directory at: {qt_dir}")
        # Add Qt plugins
        if os.path.exists(os.path.join(qt_dir, "plugins")):
            binaries.extend([
                (os.path.join(qt_dir, "plugins", "platforms", "*.dylib"), "platforms"),
                (os.path.join(qt_dir, "plugins", "styles", "*.dylib"), "styles"),
            ])
        
        # Add QtWebEngine resources
        if os.path.exists(os.path.join(qt_dir, "lib")):
            webengine_path = os.path.join(qt_dir, "lib", "QtWebEngineCore.framework")
            if os.path.exists(webengine_path):
                datas.extend([
                    (os.path.join(webengine_path, "Resources"), os.path.join("QtWebEngineCore.framework", "Resources")),
                ])
        
        # Add general Qt resources
        if os.path.exists(os.path.join(qt_dir, "resources")):
            datas.extend([
                (os.path.join(qt_dir, "resources", "*"), "resources"),
                (os.path.join(qt_dir, "translations", "*"), "translations"),
            ])
    else:
        print("Warning: Could not find Qt directory")
        
except Exception as e:
    print(f"Warning: Could not find PyQt5 resources: {e}")

# Collect other package dependencies
for package in packages:
    try:
        if package != 'PyQtWebEngine':  # Skip QtWebEngine as we handled it above
            pkg_binaries, pkg_datas, pkg_hiddenimports = collect_all(package)
            binaries.extend(pkg_binaries)
            datas.extend(pkg_datas)
            hiddenimports.extend(pkg_hiddenimports)
    except Exception as e:
        print(f"Warning: Error collecting {package}: {e}")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=[
        ('*.json', '.'),
        ('*.py', '.'),
    ] + datas,
    hiddenimports=hiddenimports + [
        'PyQt5.QtPrintSupport',
        'PyQt5.QtWebEngineWidgets',
        'PyQt5.QtWebEngineCore',
        'PyQt5.QtWebEngine',
        'PyQt5.QtNetwork',
        'PyQt5.sip',
        'spellchecker',
        'feedparser',
    ],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AP Editor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = BUNDLE(
    exe,
    name='AP Editor.app',
    icon=None,
    bundle_identifier='com.apeditor',
    info_plist={
        'NSHighResolutionCapable': 'True',
        'LSApplicationCategoryType': 'public.app-category.productivity',
        'CFBundleShortVersionString': '1.0.0',
        'NSRequiresAquaSystemAppearance': 'NO',  # Enable dark mode support
    }
) 