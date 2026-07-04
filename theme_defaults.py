"""Built-in Light and Dark default palettes for TranscribeEdit.

Waveform / Timetable colours are keyed as:
  waveform_fg, waveform_bg
  timetable_fg, timetable_bg, timetable_font

Editor colour keys mirror prefs_tab_editor.py (16 colours + 6 fonts).

Dark editor palette: Atom One Dark
Light editor palette: Atom One Light
"""

# ---------------------------------------------------------------------------
# Waveform / Timetable defaults
# ---------------------------------------------------------------------------

WAVEFORM_DEFAULTS = {
    "dark": {
        "waveform_fg": "#00ffff",   # cyan — base-commit value
        "waveform_bg": "#000000",   # black — base-commit value
    },
    "light": {
        "waveform_fg": "#1a73e8",   # blue
        "waveform_bg": "#f0f4f8",   # near-white
    },
}

TIMETABLE_DEFAULTS = {
    "dark": {
        "timetable_fg": "#00ffff",  # cyan — base-commit stylesheet
        "timetable_bg": "#000000",  # black — base-commit stylesheet
        "timetable_font": "Monospace,24", # Monospaced, size 24
    },
    "light": {
        "timetable_fg": "#1a3a5c",
        "timetable_bg": "#dce8f5",
        "timetable_font": "Monospace,24", # Monospaced, size 24
    },
}

# ---------------------------------------------------------------------------
# Editor — Atom One Dark
# ---------------------------------------------------------------------------
#
# Atom One Dark colour roles:
#   Background:      #282c34  (editor bg)
#   Default text:    #abb2bf
#   Timestamps:      #e5c07b  (yellow), no bg
#   Speaker tags:    #61afef  (blue), no bg
#   MD headings:     #e06c75  (red)
#   MD HR:           #5c6370  (grey)
#   MD list bg:      #2c313c
#   MD list marker:  #98c379  (green)
#   MD markup syms:  #5c6370  (grey)
#   MD code fg:      #56b6c2  (cyan), bg: #21252b
#   MD blockquote:   #98c379  (green), italic
#   Comment fg:      #5c6370  (grey), italic; bg: #21252b
#
EDITOR_DARK_DEFAULTS = {
    # colours
    "text_fg":            "#abb2bf",
    "text_bg":            "#282c34",
    "ts_fg":              "#e5c07b",
    "ts_bg":              "",
    "spk_fg":             "#61afef",
    "spk_bg":             "",
    "md_heading_fg":      "#e06c75",
    "md_hr_fg":           "#5c6370",
    "md_list_bg":         "#2c313c",
    "md_list_marker_fg":  "#98c379",
    "md_markup_fg":       "#5c6370",
    "md_code_bg":         "#21252b",
    "md_code_fg":         "#56b6c2",
    "md_blockquote_fg":   "#98c379",
    "comment_fg":         "#5c6370",
    "comment_bg":         "#21252b",
    # fonts (Family, Size)
    "font":               "Sans Serif,12",
    "ts_font":            "Monospace,12",
    "spk_font":           "Sans Serif,12",
    "md_code_font":       "Monospace,12",
    "md_markup_font":     "Monospace,12",
    "comment_font":       "Monospace,12",
}

# ---------------------------------------------------------------------------
# Editor — Atom One Light
# ---------------------------------------------------------------------------
#
# Atom One Light colour roles:
#   Background:      #fafafa
#   Default text:    #383a42
#   Timestamps:      #c18401  (amber)
#   Speaker tags:    #4078f2  (blue)
#   MD headings:     #e45649  (red)
#   MD HR:           #9d9d9f  (mid-grey)
#   MD list bg:      #eef0f3
#   MD list marker:  #50a14f  (green)
#   MD markup syms:  #a0a1a7  (light grey)
#   MD code fg:      #0184bc  (teal), bg: #e8eaed
#   MD blockquote:   #50a14f  (green)
#   Comment fg:      #a0a1a7  (grey); bg: #eef0f3
#
EDITOR_LIGHT_DEFAULTS = {
    # colours
    "text_fg":            "#383a42",
    "text_bg":            "#fafafa",
    "ts_fg":              "#c18401",
    "ts_bg":              "",
    "spk_fg":             "#4078f2",
    "spk_bg":             "",
    "md_heading_fg":      "#e45649",
    "md_hr_fg":           "#9d9d9f",
    "md_list_bg":         "#eef0f3",
    "md_list_marker_fg":  "#50a14f",
    "md_markup_fg":       "#a0a1a7",
    "md_code_bg":         "#e8eaed",
    "md_code_fg":         "#0184bc",
    "md_blockquote_fg":   "#50a14f",
    "comment_fg":         "#a0a1a7",
    "comment_bg":         "#eef0f3",
    # fonts
    "font":               "Sans Serif,12",
    "ts_font":            "Monospace,12",
    "spk_font":           "Sans Serif,12",
    "md_code_font":       "Monospace,12",
    "md_markup_font":     "Monospace,12",
    "comment_font":       "Monospace,12",
}

# ---------------------------------------------------------------------------
# Convenience accessors
# ---------------------------------------------------------------------------

def get_defaults(mode: str) -> dict:
    """Return the full merged defaults dict for *mode* ('light' or 'dark').

    The returned dict covers all editor colour/font keys plus waveform and
    timetable keys — ready for direct lookup by the theme manager.
    """
    if mode == "light":
        d = {}
        d.update(EDITOR_LIGHT_DEFAULTS)
        d.update(WAVEFORM_DEFAULTS["light"])
        d.update(TIMETABLE_DEFAULTS["light"])
    else:
        d = {}
        d.update(EDITOR_DARK_DEFAULTS)
        d.update(WAVEFORM_DEFAULTS["dark"])
        d.update(TIMETABLE_DEFAULTS["dark"])
    return d


ALL_KEYS = list(EDITOR_DARK_DEFAULTS.keys()) + [
    "waveform_fg", "waveform_bg",
    "timetable_fg", "timetable_bg", "timetable_font",
]
