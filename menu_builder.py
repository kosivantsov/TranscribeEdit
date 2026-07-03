# menu_builder.py
import platform
from PyQt5.QtWidgets import QAction, QMenuBar, QMenu
from PyQt5.QtGui import QKeySequence
from PyQt5.QtCore import Qt

def build_main_menu(window) -> dict:
    menubar = window.menuBar()
    menubar.setNativeMenuBar(True)
    actions = {}

    # --- FILE MENU ---
    file_menu = menubar.addMenu(window.tr("File"))

    open_proj_action = QAction(window.tr("Open Project..."), window)
    open_proj_action.triggered.connect(window.load_project)
    file_menu.addAction(open_proj_action)
    actions["Open Project"] = open_proj_action

    save_proj_action = QAction(window.tr("Save Project"), window)
    save_proj_action.triggered.connect(window.save_project)
    file_menu.addAction(save_proj_action)
    actions["Save Project"] = save_proj_action

    save_proj_as_action = QAction(window.tr("Save Project As..."), window)
    save_proj_as_action.triggered.connect(window.save_project_as)
    file_menu.addAction(save_proj_as_action)
    actions["Save Project As"] = save_proj_as_action

    file_menu.addSeparator()

    open_action = QAction(window.tr("Open Audio..."), window)
    open_action.triggered.connect(window.open_file)
    file_menu.addAction(open_action)
    actions["Open Audio"] = open_action

    load_json_action = QAction(window.tr("Load JSON..."), window)
    load_json_action.triggered.connect(window.load_json)
    file_menu.addAction(load_json_action)
    actions["Load JSON"] = load_json_action

    save_json_action = QAction(window.tr("Save JSON"), window)
    save_json_action.triggered.connect(window.save_json)
    file_menu.addAction(save_json_action)
    actions["Save JSON"] = save_json_action

    save_json_as_action = QAction(window.tr("Save JSON As..."), window)
    save_json_as_action.triggered.connect(window.save_json_as)
    file_menu.addAction(save_json_as_action)

    file_menu.addSeparator()

    cloud_transcribe_action = QAction(window.tr("Transcribe (Cloud API)"), window)
    cloud_transcribe_action.triggered.connect(window.send_to_cloud)
    file_menu.addAction(cloud_transcribe_action)

    handy_transcribe_action = QAction(window.tr("Transcribe with Handy Tool"), window)
    handy_transcribe_action.triggered.connect(window.transcribe_with_handy)
    file_menu.addAction(handy_transcribe_action)

    quit_action = QAction(window.tr("Quit"), window)
    quit_action.setMenuRole(QAction.QuitRole)
    quit_action.triggered.connect(window.quit_app)
    if platform.system() != 'Darwin':
        file_menu.addSeparator()
        file_menu.addAction(quit_action)
    actions["Quit"] = quit_action

    # --- EXPORT MENU ---
    export_menu = menubar.addMenu(window.tr("Export"))

    default_fmt = window.settings.value("export_default_format", "srt")
    def_export_action = QAction(window.tr(f"Export Default ({default_fmt.upper()})"), window)
    # Late binding: fetch the setting at the moment of triggering, not creation!
    def_export_action.triggered.connect(
        lambda checked: window.export_file(window.settings.value("export_default_format", "srt"))
    )
    export_menu.addAction(def_export_action)
    actions["Export Default"] = def_export_action

    export_menu.addSeparator()

    formats = [
        ("SRT", "srt"), ("WebVTT", "vtt"), ("ASS/SSA", "ass"),
        ("TTML", "ttml"), ("Markdown", "md"), ("HTML", "html")
    ]

    for label, fmt in formats:
        action = QAction(window.tr(f"Export {label}..."), window)
        action.triggered.connect(lambda checked, f=fmt: window.export_file(f))
        export_menu.addAction(action)

    # --- VIEW MENU ---
    view_menu = menubar.addMenu(window.tr("View"))
    on_top_action = QAction(window.tr("Always on Top"), window, checkable=True)
    on_top_action.triggered.connect(window.toggle_always_on_top)
    view_menu.addAction(on_top_action)
    window.on_top_action = on_top_action

    # --- OPTIONS MENU ---
    options_menu = menubar.addMenu(window.tr("Options"))

    cloud_config_action = QAction(window.tr("Cloud API Configuration..."), window)
    cloud_config_action.triggered.connect(window.open_cloud_config)
    options_menu.addAction(cloud_config_action)

    preferences_action = QAction(window.tr("Preferences..."), window)
    preferences_action.setMenuRole(QAction.PreferencesRole)
    preferences_action.triggered.connect(window.open_preferences_dialog)
    # macOS: Cmd+, is handled automatically via PreferencesRole.
    # Windows / Linux: bind Ctrl+F12.
    if platform.system() != 'Darwin':
        preferences_action.setShortcut(QKeySequence("Ctrl+F12"))
    options_menu.addAction(preferences_action)
    actions["Preferences"] = preferences_action

    # --- HELP MENU ---
    help_menu = menubar.addMenu(window.tr("Help"))

    online_help_action = QAction(window.tr("Online Help"), window)
    online_help_action.triggered.connect(window.open_online_help)
    help_menu.addAction(online_help_action)

    about_action = QAction(window.tr("About TranscribeEdit"), window)
    about_action.setMenuRole(QAction.AboutRole)
    about_action.triggered.connect(window.show_about)
    help_menu.addAction(about_action)

    return actions
