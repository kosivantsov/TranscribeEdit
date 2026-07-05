# prefs_tab_deps.py
import os, sys, platform, shutil
from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QDialogButtonBox,
    QScrollArea, QFrame,
)
from PyQt5.QtCore import Qt


def _get_dep_definitions():
    sys_name = platform.system()
    defs = [
        {
            "key": "dep_ffmpeg", "name": "ffmpeg", "description": "Audio/video processing binary",
            "is_library": False, "candidates_win": ["ffmpeg.exe"], "candidates_mac": ["ffmpeg"],
            "candidates_lin": ["ffmpeg"], "browse_filter": "Executables (ffmpeg ffmpeg.exe);;All Files (*)",
        },
        {
            "key": "dep_ffprobe", "name": "ffprobe", "description": "Media info binary (optional)",
            "is_library": False, "candidates_win": ["ffprobe.exe"], "candidates_mac": ["ffprobe"],
            "candidates_lin": ["ffprobe"], "browse_filter": "Executables (ffprobe ffprobe.exe);;All Files (*)",
        },
    ]
    if sys_name in ("Linux", "Darwin"):
        lib_name = "libmpv.so.2" if sys_name == "Linux" else "libmpv.dylib"
        alt_names = ["libmpv.so.1", "libmpv.so"] if sys_name == "Linux" else ["libmpv.2.dylib", "libmpv.1.dylib"]
        filter_str = "Shared Libraries (libmpv*.so*);;All Files (*)" if sys_name == "Linux" else "Dynamic Libraries (libmpv*.dylib);;All Files (*)"
        defs.append({
            "key": "dep_mpv_lib", "name": "libmpv", "description": f"mpv shared library ({lib_name})",
            "is_library": True, "candidates_win": [], "candidates_mac": alt_names + [lib_name],
            "candidates_lin": [lib_name] + alt_names, "browse_filter": filter_str,
        })
    return defs


DEP_DEFINITIONS = _get_dep_definitions()


def _base_dir():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def resolve_dep_path(stored: str) -> str:
    if not stored:
        return ""
    if os.path.isabs(stored):
        return stored
    return os.path.normpath(os.path.join(_base_dir(), stored))


def _make_stored_path(abs_path: str) -> str:
    base = _base_dir()
    try:
        rel = os.path.relpath(abs_path, base)
        if not rel.startswith(".."):
            return rel
    except ValueError:
        pass
    return abs_path


def discover_dep(dep: dict) -> str:
    base = _base_dir()
    names = dep["candidates_win"] if platform.system() == "Windows" else (
        dep["candidates_mac"] if platform.system() == "Darwin" else dep["candidates_lin"]
    )

    for name in names:
        if os.path.isfile(os.path.join(base, name)):
            return os.path.join(base, name)

    if dep["is_library"]:
        search_dirs = [
            "/usr/lib", "/usr/local/lib", "/usr/lib/x86_64-linux-gnu",
            "/usr/lib64", "/opt/homebrew/lib", "/opt/local/lib"
        ]
        for d in search_dirs:
            for name in names:
                if os.path.exists(os.path.join(d, name)):
                    return os.path.join(d, name)
    else:
        for name in names:
            found = shutil.which(name)
            if found:
                return found
    return ""


def check_and_store_deps(settings) -> list:
    missing = []
    for dep in DEP_DEFINITIONS:
        stored = settings.value(dep["key"], "")
        if stored and os.path.exists(resolve_dep_path(stored)):
            continue
        found = discover_dep(dep)
        if found:
            settings.setValue(dep["key"], _make_stored_path(found))
        else:
            missing.append(dep)
    return missing


def get_dep_path(settings, key: str) -> str:
    return resolve_dep_path(settings.value(key, ""))


class DepsTab(QWidget):
    TAB_LABEL = "Dependencies"

    def __init__(self, parent, settings, missing_only=False):
        super().__init__(parent)
        self.settings = settings
        self._rows = {}

        outer = QVBoxLayout(self)

        info = QLabel(self.tr(
            "Set paths to required external tools.\n"
            "Fields with red borders are invalid. Relative paths are kept when placed next to the binary."
        ))
        info.setWordWrap(True)
        outer.addWidget(info)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        grid.setColumnMinimumWidth(0, 190)
        grid.setColumnStretch(1, 1)
        grid.setColumnMinimumWidth(2, 96)

        row_index = 0
        for dep in DEP_DEFINITIONS:
            current = settings.value(dep["key"], "")
            if missing_only and current and os.path.exists(resolve_dep_path(current)):
                continue

            lbl = QLabel(f"<b>{dep['name']}</b><br/><small>{dep['description']}</small>")
            lbl.setTextFormat(Qt.RichText)
            lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            lbl.setWordWrap(True)

            edit = QLineEdit(resolve_dep_path(current))
            edit.setPlaceholderText(self.tr("Not set"))
            edit.textChanged.connect(
                lambda t, e=edit: e.setStyleSheet("" if os.path.exists(t) else "border: 2px solid red;")
            )
            edit.textChanged.emit(edit.text())

            btn = QPushButton(self.tr("Browse..."))
            btn.setFixedWidth(96)
            btn.clicked.connect(
                lambda _, d=dep, e=edit: e.setText(
                    QFileDialog.getOpenFileName(
                        self, self.tr(f"Locate {d['name']}"), "", d["browse_filter"]
                    )[0] or e.text()
                )
            )

            self._rows[dep["key"]] = edit

            grid.addWidget(lbl, row_index, 0, alignment=Qt.AlignLeft | Qt.AlignTop)
            grid.addWidget(edit, row_index, 1)
            grid.addWidget(btn, row_index, 2, alignment=Qt.AlignRight | Qt.AlignVCenter)
            row_index += 1

        grid.setRowStretch(row_index, 1)

        scroll.setWidget(container)
        outer.addWidget(scroll)

        btn = QPushButton(self.tr("Re-run Auto-Discovery"))
        btn.clicked.connect(self._rediscover)
        outer.addWidget(btn)

    def _rediscover(self):
        for dep in DEP_DEFINITIONS:
            found = discover_dep(dep)
            if found and dep["key"] in self._rows:
                self._rows[dep["key"]].setText(found)

    def save(self):
        for dep in DEP_DEFINITIONS:
            if dep["key"] in self._rows:
                val = self._rows[dep["key"]].text().strip()
                if val and os.path.exists(val):
                    self.settings.setValue(dep["key"], _make_stored_path(val))
                elif not val:
                    self.settings.remove(dep["key"])


class DepsDialog(QDialog):
    def __init__(self, parent, settings, missing_only=True):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Required Dependencies"))
        self.setMinimumSize(560, 340)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.tr(
            "<b>Some required external tools could not be found automatically.</b><br>"
            "Please locate them below."
        )))
        self.widget = DepsTab(self, settings, missing_only=missing_only)
        layout.addWidget(self.widget, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Cancel).setText(self.tr("Skip"))
        buttons.accepted.connect(lambda: [self.widget.save(), self.accept()])
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
