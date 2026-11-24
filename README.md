<p align="center">
  <img src="logo.png" alt="DoubleScreener Logo" height="150">
</p>

**DoubleScreener** is a **HTML visual editor** designed to create web pages with a **live second-screen**.  
For more info or for the program documentation, see the [Wiki Page](https://github.com/il-mangia/doublescreener.github.io/wiki).

## Usage
You can use DoubleScreener [**online**](https://il-mangia.github.io/doublescreener.github.io/) <br>
But you can also use DoubleScreener local by:
1. Clone the repository or download the ZIP:  
   ```bash
   git clone https://github.com/il-mangia/doublescreener.github.io.git
2. Open back-end.html in your browser.
4. Drag elements into the canvas, style them, and press Apply Changes.
5. Open front-end.html to see the live result!

### DoubleScreener v2 (in sviluppo)

La v2 è una regia desktop **PyQt6** con backend Python (FastAPI + Uvicorn) e second screen web. Il codice vive in `src/doublescreener/` sul branch `v2-rewrite`; la demo statica qui sopra resta disponibile su GitHub Pages.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -e ".[gui,dev]"

python -m doublescreener              # regia desktop
python -m doublescreener --headless   # solo backend, senza GUI
```

Con la regia aperta, punta TV, tablet o secondo PC all'indirizzo LAN mostrato nel pannello Presentazione (o inquadra il QR). I dati stanno nella cartella utente dell'app; usa `--data-dir PATH` per cambiarli.

---

## Features

- Drag & drop elements: **Text**, **Button**, **Image**, **Container/Box**  
- Edit content and style **visually**  
- Apply simple **animations** (fade, slide, zoom, bounce)  
- Live preview on a **front-end screen**  
- Works **locally** in your browser, no server needed  
- Easy to use for students, teachers, or hobbyists  

### File Structure
/app <br>
├── back-end.html      <br>
├── back-end.css       <br>
├── front-end.html     <br>
├── front-end.css      <br>

### Contributing
Feel free to submit issues or pull requests.
Suggestions for new features, animations, or usability improvements are very welcome!

### License

DoubleScreener is free software, released under the **GNU General Public License v3.0** (GPL-3.0-only).
You can use, study, modify and redistribute it under the terms of that license.

See [LICENSE](LICENSE) for the full text.

Copyright (C) 2026 il-mangia and DoubleScreener contributors.

> **Why GPLv3?** The v2 desktop app is built with PyQt6, which is distributed under GPLv3.
> A permissive license (MIT/Apache) would require migrating the desktop app to PySide6 (LGPL).
