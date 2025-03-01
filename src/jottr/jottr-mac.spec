# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

import os
import glob

# Enchant and Aspell paths
#enchant_cellar = '/usr/local/Cellar/enchant/2.8.2'
aspell_cellar = '/usr/local/Cellar/aspell/0.60.8.1_1'

# Binaries (libraries)
# enchant_lib_dir = os.path.join(enchant_cellar, 'lib')
# aspell_lib_dir = os.path.join(aspell_cellar, 'lib', 'aspell-0.60')
# binaries = [
#     (os.path.join(enchant_lib_dir, 'libenchant-2.dylib'), '.'),
#     (os.path.join(enchant_lib_dir, 'enchant-2', 'enchant_aspell.so'), 'enchant-2'),
#     (os.path.join(enchant_lib_dir, 'enchant-2', 'enchant_applespell.so'), 'enchant-2'),
#     ('/usr/local/opt/glib/lib/libglib-2.0.0.dylib', '.'),
#     ('/usr/local/opt/glib/lib/libgobject-2.0.0.dylib', '.'),
#     ('/usr/local/opt/glib/lib/libgmodule-2.0.0.dylib', '.'),
#     ('/usr/local/opt/gettext/lib/libintl.8.dylib', '.'),
# ]

# Datas (app files and enchant module)
datas = [
    ('editor_tab.py', '.'),
    ('snippet_manager.py', '.'),
    ('rss_tab.py', '.'),
    ('theme_manager.py', '.'),
    ('settings_manager.py', '.'),
    ('settings_dialog.py', '.'),
    ('snippet_editor_dialog.py', '.'),
    ('rss_reader.py', '.'),
    ('icons', 'icons'),
    ('help', 'help'),
    ('/Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13/site-packages/enchant', 'enchant'),
    ('/Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13/site-packages/spellchecker/resources', 'spellchecker/resources'),
]

# Add Aspell dictionaries
# aspell_files = glob.glob(os.path.join(aspell_lib_dir, '*.multi')) + \
#                glob.glob(os.path.join(aspell_lib_dir, '*.rws')) + \
#                glob.glob(os.path.join(aspell_lib_dir, '*.dat'))
# for dict_file in aspell_files:
#     datas.append((dict_file, 'aspell'))

a = Analysis(['main.py'],
             pathex=['/Users/mahdi/GitHub/jottr/src/jottr'],
             #binaries=binaries,
             datas=datas,
             hiddenimports=['ctypes', 'ctypes.util', 'pyenchant', 'pyspellchecker'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='jottr',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False,
          icon='app.ico')

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='jottr')

app = BUNDLE(coll,
             name='Jottr.app',
             icon='jottr_icon.icns',
             bundle_identifier='io.github.mfat.jottr')