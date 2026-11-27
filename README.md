<p align="center">
  <img src="logo.png" alt="DoubleScreener Logo" height="150">
</p>

**DoubleScreener** is an open-source **desktop control room** for presentations with a **second screen in the browser**.

The v2 app is a PyQt6 desktop application with an embedded FastAPI server: build HTML slides, import pages from a PDF, and project them to a TV, tablet or another PC over the local network. No cloud, no account, no database.

> The old web demo has been retired. DoubleScreener now runs locally on your computer; the browser is only used for the second screen.

## Quick start

Requirements: **Python 3.11+** and Git. On Linux, install the Qt/WebEngine libraries provided by your distribution.

```bash
git clone https://github.com/il-mangia/doublescreener.github.io.git
cd doublescreener.github.io
git switch v2-rewrite        # development branch of the v2 rewrite

python -m venv .venv
# Windows
.\.venv\Scripts\Activate.ps1
# Linux / macOS
source .venv/bin/activate

pip install -e ".[gui]"
python -m doublescreener
```

The control room opens with the embedded server. The **Presentation** panel shows the LAN address and a QR code for the second screen (for example `http://192.168.1.20:8765/p`). Projects are stored as JSON in the app's user folder; use `--data-dir PATH` to choose another location.

```bash
python -m doublescreener --headless   # API + player only, no desktop GUI
```

## Features

- **Visual editor** — drag, resize, rotate, snapping guides, zoom, inline text editing, undo/redo and autosave.
- **Inspector** — geometry, typography, colors, box styles, content and entrance animations.
- **Templates and themes** — five slide layouts, four color themes, system fonts.
- **HTML and PDF decks** — import PDF pages by range; pages are rendered server-side as lightweight images.
- **Second screen** — any browser on the LAN, live WebSocket sync, QR connection and black screen.
- **Standalone export** — a static folder or a single HTML file that opens from `file://`.
- **Local-first** — JSON projects on disk, no database, no login, no tracking.
- **Italian and English** interface, dark and light themes.

## Documentation

- [Setup and development](docs/setup.md)
- [Architecture](docs/architecture.md)
- [REST API](docs/api.md)
- [WebSocket protocol](docs/ws-protocol.md)

## Contributing

Feel free to submit issues or pull requests. Suggestions for new features, animations, or usability improvements are very welcome!

## License

DoubleScreener is free software, released under the **GNU General Public License v3.0** (GPL-3.0-only).
You can use, study, modify and redistribute it under the terms of that license.

See [LICENSE](LICENSE) for the full text.

Copyright (C) 2026 il-mangia and DoubleScreener contributors.

> **Why GPLv3?** The v2 desktop app is built with PyQt6, which is distributed under GPLv3.
> A permissive license (MIT/Apache) would require migrating the desktop app to PySide6 (LGPL).
