# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['application_bot/gui.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('application_bot/web_ui', 'web_ui'),        # For pywebview UI
        ('application_bot/settings.json', '.'),      # Settings file at the root of the app folder
        ('application_bot/questions.json', '.'),     # Questions file at the root
        ('application_bot/fonts', 'fonts')           # Fonts folder
    ],
    hiddenimports=[
        'babel.numbers',
        'PIL._imagingtk',
        'PIL.ImageTk',
        'PIL.ImageFont',
        'PIL.PngImagePlugin',
        'PIL.JpegImagePlugin',
        'tkinter.scrolledtext',
        'tkinter.messagebox',
        'tkinter.font',
        'queue',
        'logging.handlers',
        'application_bot.main',
        'application_bot.utils',
        'application_bot.constants',
        'application_bot.pdf_generator',
        'application_bot.handlers.command_handlers',
        'application_bot.handlers.conversation_logic',
        'reportlab.fonts',
        'reportlab.pdfbase.ttfonts',
        'reportlab.platypus.flowables',
        'asyncio',
        'anyio',
        'anyio._backends._asyncio',
        'httpx',
        'httpx._transports.default',
        'httpx._exceptions',
        'httpcore',
        'httpcore._exceptions',
        'httpcore._backends.asyncio',
        'h11',
        'json',
        'certifi', # Make sure certifi is explicitly handled
        'charset_normalizer',
        'webview', # Add pywebview explicitly
        # Add specific pywebview backends if needed, e.g.,
        'webview.platforms.winforms', # For Windows
        # 'webview.platforms.gtk',      # For Linux with GTK
        # 'webview.platforms.cocoa',    # For macOS
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False, # For one-folder this is less critical than one-file
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    # binaries and datas from Analysis are automatically included in one-folder mode
    name='ApplicationBotGUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True, # Set to False if UPX causes issues with httpx or certifi
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='application_bot/icon.ico',
)

# For one-folder mode, the COLLECT step defines the output directory
# and what goes into it.
# The 'exe' object is the main executable.
# a.binaries are other DLLs/dylibs.
# a.zipfiles are usually empty for one-folder unless you structure it specifically.
# a.datas are the data files specified in Analysis.
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True, # Set to False if UPX causes issues
    upx_exclude=[],
    name='ApplicationBotGUI' # This will be the name of the folder in 'dist'
)