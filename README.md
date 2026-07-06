# TranscribeEdit

A cross-platform desktop application that combines a media player with a real-time waveform visualizer and a rich transcript editor — purpose-built for the audio transcription and localization workflow.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Running the Application](#running-the-application)
- [User Interface](#user-interface)
- [Media Player & Waveform](#media-player--waveform)
- [Transcript Editor](#transcript-editor)
- [Timestamps & Speaker Tags](#timestamps--speaker-tags)
- [Transcription Backends](#transcription-backends)
- [File Operations](#file-operations)
- [Export Formats](#export-formats)
- [Preferences](#preferences)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Project File Format](#project-file-format)
- [Architecture Overview](#architecture-overview)
- [License](#license)

---

## Overview

TranscribeEdit is designed for linguists, translators, journalists, and anyone who regularly listens to audio recordings and produces text transcriptions. It integrates a media player driven by [mpv](https://mpv.io/) with an interactive waveform display and a feature-rich plain-text editor in a single window, so you can listen, navigate, and type without switching applications.

---

## Features

| Area | Capabilities |
|---|---|
| **Playback** | Play / Pause / Stop, seek by ±0.1 s / ±0.5 s / ±1 s / ±5 s, speed control 25–100 %, volume slider |
| **Waveform** | Real-time scrolling waveform, configurable window (0.1 s – 5 s), clickable seek, A/B loop markers |
| **Editor** | Limited markdown syntax highlighting, fold/unfold segments, find & replace with regex support |
| **Timestamps** | Insert `⟦HH:MM:SS.mmm⟧` at current playback position, jump to timestamp under cursor, highlight closest timestamp |
| **Speaker tags** | Insert / cycle through up to 6 named speaker labels `⟪NAME⟫` |
| **Auto-transcription** | Cloud REST API (OpenAI-compatible, async polling, custom headers/variables) or local [Handy](https://handy.computer/about) CLI binary |
| **Export** | SRT, WebVTT, ASS/SSA, TTML, Markdown, HTML (MD and HTML with customizable format templates) |
| **Projects** | Self-contained `.teproj` ZIP bundle (audio + JSON data) restores exact playback position and cursor |
| **Themes** | Dark/light auto-detection via `pyqtdarktheme`, fully configurable color/font overrides per UI element |
| **Shortcuts** | Fully remappable keyboard shortcuts (stored per user) |
<!-- | **i18n** | Qt translation framework; loads `transcribeedit_<locale>.qm` and Qt system strings automatically | -->

---

## Requirements

### Python packages

Install via `pip install -r requirements.txt`:
```
PyQt5
pyqtdarktheme
python-mpv
numpy
requests
markdown
```

### External binaries

| Binary | Required? | Purpose |
|---|---|---|
| **ffmpeg** | **Yes** | Decodes audio to 16 kHz WAV for waveform rendering; also used by the CLI transcription worker |
| **ffprobe** | Optional | Media info |
| **libmpv** (`libmpv.so.2` on Linux, `libmpv.dylib` on macOS) | **Yes (Linux/macOS)** | Backend audio playback via `python-mpv`; on Windows the DLL is bundled with the mpv distribution |

TranscribeEdit auto-discovers these paths on startup and prompts you to set them manually if they cannot be found.

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/kosivantsov/TranscribeEdit.git
cd TranscribeEdit
```

### 2. Create a virtual environment (recommended)

```bash
python3 -m venv venv
```

### 3. Install Python dependencies

**Linux / macOS:**
```bash
bash install_req.sh
```

Or manually:
```bash
source venv/bin/activate
pip install -r requirements.txt --ignore-requires-python
```

**Windows:**
```bat
venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Install external dependencies

**Ubuntu/Debian:**
```bash
sudo apt install ffmpeg libmpv2
```

**macOS (Homebrew):**
```bash
brew install ffmpeg mpv
```

**Windows:** Download [ffmpeg](https://ffmpeg.org/download.html) and place `ffmpeg.exe` next to `main.py`, or add it to your `PATH`. The mpv DLL required by `python-mpv` (`mpv-2.dll`) should be placed in the same directory.

---

## Running the Application

```bash
source venv/bin/activate   # Linux/macOS
# or: venv\Scripts\activate  # Windows

python main.py
```

The application opens with a minimum window size of 900 × 850 px. The theme (dark/light) is chosen automatically from the OS preference.

---

## Media Player & Waveform

### Loading audio

Use **File > Open Audio** (`Ctrl+Shift+O`) to load an audio file. Supported formats (via mpv/ffmpeg): `mp3`, `wav`, `flac`, `ogg`, `m4a`, `aac`.

### Playback controls

| Control | Action |
|---|---|
| **▶ Play / ⏸ Pause** | Toggle playback (`Ctrl+P`) |
| **■ Stop** | Pause and return to position 0 (`Shift+Esc`) |
| **Jump…** | Open position slider dialog (`Ctrl+J`) |
| **Speed buttons** | 25 % / 50 % / 75 % / 100 % (`Alt+1` – `Alt+4`) |
| **Speed +/−** | Step speed up or down (`Alt+Up` / `Alt+Down`) |
| **Volume slider** | 0 – 100 % (`Ctrl+Up` / `Ctrl+Down`) |
| **Stop/Play** (shortcut only) | Stop if playing, play if stopped or pauses (`Ctrl+Enter`) |

### Waveform

The waveform is generated by decoding the audio file with **ffmpeg** to a temporary 16 kHz mono WAV and computing 200 amplitude bars per second with NumPy. The visible window is configurable (0.1 s to 5.0 s), and a red cursor line tracks the playback position in real time (updated every 50 ms). **Click anywhere on the waveform** to seek to that position.

### A/B Loop

Mark two positions with **A** (`Ctrl+Alt+A`) and **B** (`Ctrl+Alt+B`) to define a loop region visualized on the waveform as orange markers. Enable looping with the **Loop** button (`Ctrl+Alt+L`). Pressing A or B again while at the marked position clears it; pressing while elsewhere jumps to the marker.

---

## Transcript Editor

- **Limited markdown syntax highlighting** — headings, bold, italic, strikethrough, inline code, blockquotes, lists, links, horizontal rules, and HTML tags
- **Timestamp highlighting** — `⟦HH:MM:SS.mmm⟧` tokens shown in a distinct color/font configurable via Preferences
- **Speaker tag highlighting** — `⟪NAME⟫` tokens styled separately
- **HTML comment highlighting** — `<!-- ... -->` blocks with dedicated styling options
- **Find dialog** (`Ctrl+F`) — plain text and regular-expression search with forward/backward navigation
- **Fold/unfold segments** (`Ctrl+Shift+F`) — collapse a transcription unit to show only its timestamp header
- **Inline formatting** — `Ctrl+B` bold, `Ctrl+I` italic, `Ctrl+U` underline, `Ctrl+/` wrap selection in HTML comment

---

## Timestamps & Speaker Tags

### Timestamp format
```
⟦0:00:05.320⟧ ⟦0:00:12.450⟧
Text of the segment goes here.
```

A segment line may carry a single start timestamp or a start + end pair. The editor validates new timestamps for chronological order and warns about duplicates (configurable in Preferences).

### Inserting a timestamp

- Press **`Ctrl+T`** or click **Insert Timestamp** to stamp the current playback position.
- The timestamp is also copied to the clipboard in `⟦HH:MM:SS.mmm⟧` format.

### Jumping to a timestamp

- Place the cursor on or next to a timestamp token and press **`F5`** or click **Jump to Timestamp**.

### Speaker tags

Configure up to 6 speaker names in **Preferences > Speakers**. Each press of **`Ctrl+Shift+T`** inserts or cycles to the next speaker tag `⟪SPEAKER_01⟫`.

---

## Transcription Backends

### Cloud API

Configure in **Options > Cloud API Configuration**:

| Field | Description |
|---|---|
| **URL** | REST endpoint (supports `${FILE}`, `${JOB_ID}`, and custom variable substitution) |
| **Headers** | e.g., `Authorization: Bearer ${API_KEY}` |
| **Response type** | `json (OpenAI/Lemonfox)`, `text`, `srt`, or `vtt` |
| **Async polling** | Two-step upload → poll workflow; configure job ID key, poll URL, status key, ready/fail values, and interval |

### Local CLI Tool (Handy)

Configure in **Options > Handy Tool Configuration**:

| Setting | Description |
|---|---|
| **Binary path** | Path to the [Handy](https://handy.computer/about) executable |
| **Model** | e.g., `Cohere`, `Parakeet`, `Canary`, etc. |
| **Device** | e.g., `vulcan:0`, `cpu:1` |

Once the executable path has been properly set, you can poll the Handy Tool and select both the model and the device from their respective drop-down lists.

The worker converts audio to a temporary 16 kHz mono WAV via ffmpeg, invokes the binary with `--json`, and streams progress updates.

The transcription results coming from the Handy Tool are usually not timestamped.

---

## File Operations

### Project files (`.teproj`)

A `.teproj` ZIP archive bundles the audio file + `data.json` (segments, raw text, playback position, cursor position) into a single portable file.

| Action | Shortcut |
|---|---|
| Open Project | `Ctrl+O` |
| Save Project | `Ctrl+S` |
| Load JSON | `Ctrl+L` |
| Save JSON | `Ctrl+Shift+S` |
| Open Audio | `Ctrl+Shift+O` |

---

## Export Formats

| Format | Extension | Notes |
|---|---|---|
| **SRT** | `.srt` | Standard SubRip; Markdown stripped |
| **WebVTT** | `.vtt` | Web Video Text Tracks |
| **ASS/SSA** | `.ass` | Advanced SubStation Alpha |
| **TTML** | `.ttml` | Timed Text Markup Language (XML) |
| **Markdown** | `.md` | Configurable template with `${timestamp_start}`, `${timestamp_end}`, `${speaker}`, `${text}` |
| **HTML** | `.html` | Same variables, Markdown converted to HTML |

---

## Preferences

| Tab | Settings |
|---|---|
| **Dependencies** | Locate `ffmpeg`, `ffprobe`, `libmpv`; re-run auto-discovery |
| **Export options** | Default format, Markdown/HTML templates |
| **Speakers** | Define up to 6 speaker names |
| **Editor** | Font, tab size, line wrap, timestamp validation |
| **Themes and Colors** | Colors and fonts for waveform and timetable, UI theme for the application |
| **Shortcuts** | Remap every keyboard shortcut |

---

## Keyboard Shortcuts

| Action | Default |
|---|---|
| Play / Pause | `Ctrl+P` or `Ctrl+Shift+Space` |
| Stop / Play toggle | `Ctrl+Enter` |
| Insert Timestamp | `Ctrl+T` |
| Insert Speaker Tag | `Ctrl+Shift+T` |
| Jump to Timestamp | `F5` |
| Toggle Highlight | `Ctrl+Shift+H` |
| Find | `Ctrl+F` |
| Fold / Unfold | `Ctrl+Shift+F` |
| Bold / Italic / Underline | `Ctrl+B` / `Ctrl+I` / `Ctrl+U` |
| Add Comment | `Ctrl+/` |
| Speed 25–100 % | `Alt+1` – `Alt+4` |
| Waveform window 0.1–5 s | `Ctrl+1` – `Ctrl+5` |
| Set/Jump/Unset A | `Ctrl+Alt+A` |
| Set/Jump/Unset B | `Ctrl+Alt+B` |
| Toggle Loop | `Ctrl+Alt+L` |
| Open Project | `Ctrl+O` |
| Save Project | `Ctrl+S` |
| Preferences | `Ctrl+F12` *(Win/Linux)* |

---

## Project File Format

`.teproj` is a standard ZIP file. Internal `data.json` schema:

```json
{
  "audio_file": "recording.mp3",
  "audio_pos": 42.5,
  "cursor_pos": 1234,
  "raw_text": "Full plain-text editor content…",
  "segments": [
    {
      "start": 0.0,
      "end": 5.32,
      "speaker": "SPEAKER_00",
      "text": "Hello, world.",
      "comment": "optional reviewer note",
      "timestamp": "00:00 - 00:05"
    }
  ]
}
```

---

## Architecture Overview

| Module | Responsibility |
|---|---|
| `main.py` | `AudioPlayer` — UI construction, signal wiring, entry point |
| `playback_mixin.py` | All mpv playback state, A/B loop, waveform sync |
| `io_mixin.py` | Project/JSON/audio I/O, transcription dispatch |
| `dialogs_mixin.py` | Preferences, cloud config, Handy config dialogs |
| `editor.py` | `TranscriptEditor` + syntax highlighter, fold, segment serialization |
| `widgets.py` | `WaveformWidget`, `ColorLabel`, `FindDialog`, `JumpDialog` |
| `exporter.py` | SRT, VTT, ASS, TTML, MD, HTML export |
| `cloud_client.py` | Threaded REST API client with async polling |
| `cli_connector.py` | Threaded subprocess wrapper for Handy/Whisper CLI |
| `theme_manager.py` | Applies color/font overrides to registered widgets |
| `prefs_tab_*.py` | Individual Preferences tabs |
| `shortcuts.py` | `DEFAULT_SHORTCUTS` (platform-aware) |
| `utils.py` | Timestamp parsing/formatting helpers |

---

## License

This project is licensed under the [MIT License](LICENSE).

