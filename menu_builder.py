# menu_builder.py
import platform
from PyQt5.QtWidgets import QAction, QMenu
from PyQt5.QtGui import QKeySequence


def build_main_menu(window) -> dict:
    menubar = window.menuBar()
    menubar.setNativeMenuBar(True)
    actions = {}

    # ------------------------------------------------------------------ FILE
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
    if platform.system() != "Darwin":
        file_menu.addSeparator()
        file_menu.addAction(quit_action)
    actions["Quit"] = quit_action

    # ------------------------------------------------------------------ EDIT
    edit_menu = menubar.addMenu(window.tr("Edit"))

    cut_action = QAction(window.tr("Cut"), window)
    cut_action.triggered.connect(window.clipboard_cut)
    edit_menu.addAction(cut_action)
    actions["Cut"] = cut_action

    copy_action = QAction(window.tr("Copy"), window)
    copy_action.triggered.connect(window.clipboard_copy)
    edit_menu.addAction(copy_action)
    actions["Copy"] = copy_action

    paste_action = QAction(window.tr("Paste"), window)
    paste_action.triggered.connect(window.clipboard_paste)
    edit_menu.addAction(paste_action)
    actions["Paste"] = paste_action

    edit_menu.addSeparator()

    ins_ts_action = QAction(window.tr("Insert Timestamp"), window)
    ins_ts_action.triggered.connect(window.insert_timestamp)
    edit_menu.addAction(ins_ts_action)
    actions["Insert Timestamp"] = ins_ts_action

    ins_spk_action = QAction(window.tr("Insert Speaker Tag"), window)
    ins_spk_action.triggered.connect(
        lambda: window.editor.insert_or_cycle_speaker(window.speakers)
    )
    edit_menu.addAction(ins_spk_action)
    actions["Insert Speaker Tag"] = ins_spk_action

    edit_menu.addSeparator()

    bold_action = QAction(window.tr("Bold"), window)
    bold_action.triggered.connect(window.editor.format_bold)
    edit_menu.addAction(bold_action)
    actions["Format Bold"] = bold_action

    italic_action = QAction(window.tr("Italic"), window)
    italic_action.triggered.connect(window.editor.format_italic)
    edit_menu.addAction(italic_action)
    actions["Format Italic"] = italic_action

    underline_action = QAction(window.tr("Underline"), window)
    underline_action.triggered.connect(
        lambda: window.editor.toggle_format("<u>", "</u>")
    )
    edit_menu.addAction(underline_action)
    actions["Format Underline"] = underline_action

    comment_action = QAction(window.tr("Comment"), window)
    comment_action.triggered.connect(window.editor.add_comment)
    edit_menu.addAction(comment_action)
    actions["Add Comment"] = comment_action

    edit_menu.addSeparator()

    find_action = QAction(window.tr("Find..."), window)
    find_action.triggered.connect(window.open_find_dialog)
    edit_menu.addAction(find_action)
    actions["Find"] = find_action

    find_next_action = QAction(window.tr("Find Next"), window)
    find_next_action.triggered.connect(window.find_next_silent)
    edit_menu.addAction(find_next_action)
    actions["Find Next"] = find_next_action

    find_prev_action = QAction(window.tr("Find Previous"), window)
    find_prev_action.triggered.connect(window.find_prev_silent)
    edit_menu.addAction(find_prev_action)
    actions["Find Prev"] = find_prev_action

    # ------------------------------------------------------------------ EXPORT
    export_menu = menubar.addMenu(window.tr("Export"))

    default_fmt = window.settings.value("export_default_format", "srt")
    def_export_action = QAction(window.tr(f"Export Default ({default_fmt.upper()})"), window)
    def_export_action.triggered.connect(
        lambda checked: window.export_file(
            window.settings.value("export_default_format", "srt")
        )
    )
    export_menu.addAction(def_export_action)
    actions["Export Default"] = def_export_action

    export_menu.addSeparator()

    for label, fmt in [
        ("SRT", "srt"), ("WebVTT", "vtt"), ("ASS/SSA", "ass"),
        ("TTML", "ttml"), ("Markdown", "md"), ("HTML", "html"),
    ]:
        action = QAction(window.tr(f"Export {label}..."), window)
        action.triggered.connect(lambda checked, f=fmt: window.export_file(f))
        export_menu.addAction(action)

    # ------------------------------------------------------------------ VIEW
    view_menu = menubar.addMenu(window.tr("View"))

    on_top_action = QAction(window.tr("Always on Top"), window, checkable=True)
    on_top_action.triggered.connect(window.toggle_always_on_top)
    view_menu.addAction(on_top_action)
    window.on_top_action = on_top_action

    view_menu.addSeparator()

    fold_action = QAction(window.tr("Fold/Unfold Current Segment"), window)
    fold_action.triggered.connect(window.editor.toggle_fold_current)
    view_menu.addAction(fold_action)
    actions["Fold/Unfold"] = fold_action

    view_menu.addSeparator()

    #~ themes_action = QAction(window.tr("Themes and Colors..."), window)
    # Direct access: Preferences jumped to the Editor tab (index 3 = EditorTab).
    # (There is no separate themes system beyond the editor color/font config.)
    #~ themes_action.triggered.connect(window.open_editor_config)
    #~ view_menu.addAction(themes_action)

    editor_config_action = QAction(window.tr("Editor Options..."), window)
    editor_config_action.triggered.connect(window.open_editor_config)
    view_menu.addAction(editor_config_action)

    # ------------------------------------------------------------------ OPTIONS
    options_menu = menubar.addMenu(window.tr("Options"))

    cloud_config_action = QAction(window.tr("Cloud API Configuration..."), window)
    cloud_config_action.triggered.connect(window.open_cloud_config)
    options_menu.addAction(cloud_config_action)

    handy_config_action = QAction(window.tr("Handy Tool Configuration..."), window)
    handy_config_action.triggered.connect(window.open_handy_config)
    options_menu.addAction(handy_config_action)

    options_menu.addSeparator()

    preferences_action = QAction(window.tr("Preferences..."), window)
    preferences_action.setMenuRole(QAction.PreferencesRole)
    preferences_action.triggered.connect(window.open_preferences_dialog)
    # macOS: Cmd+, provided automatically via PreferencesRole; no explicit shortcut.
    # Windows/Linux: Ctrl+F12 (also user-configurable via Shortcuts tab).
    if platform.system() != "Darwin":
        preferences_action.setShortcut(QKeySequence("Ctrl+F12"))
    options_menu.addAction(preferences_action)
    actions["Preferences"] = preferences_action

    # ------------------------------------------------------------------ HELP
    help_menu = menubar.addMenu(window.tr("Help"))

    online_help_action = QAction(window.tr("Online Help"), window)
    online_help_action.triggered.connect(window.open_online_help)
    help_menu.addAction(online_help_action)

    about_action = QAction(window.tr("About TranscribeEdit"), window)
    about_action.setMenuRole(QAction.AboutRole)
    about_action.triggered.connect(window.show_about)
    help_menu.addAction(about_action)

    return actions
