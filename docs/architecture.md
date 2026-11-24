# Architettura — DoubleScreener v2

DoubleScreener v2 è composto da tre strati principali in un unico processo Python:

1. **Core (`src/doublescreener/core/`)**
   - `models.py`: modelli Pydantic v2 (`Project`, `Slide`, `Element`, `Rect`, `ElementStyle`, `ElementContent`, `Animation`, `Transition`, `PdfRef`) con `schema_version` e `migrate()`.
   - `store.py`: persistenza JSON atomica (`<data>/projects/<id>.json` + `.bak.json`), backup automatici e importazione JSON con validazione e migrazione.
   - `assets.py`: archivio asset (`<data>/assets/`) deduplicato per SHA-256 con sniffing del contenuto (PNG, JPEG, GIF, WebP, SVG, PDF) e probing dimensioni/pagine.
   - `history.py` e `commands.py`: undo/redo a comandi con coalescing (`merge_key`, finestra 600 ms) fino a 200 voci.
   - `presentation.py`: `PresentationController` thread-safe; mantiene lo stato corrente della presentazione (`open`, `goto`, `step`, `set_black`, `close`) e notifica i subscriber.
   - `templates.py` e `themes.py`: 5 template di slide e 4 temi colore (`dark`, `light`, `ocean`, `sunset`).

2. **Server HTTP/WebSocket (`src/doublescreener/server/`)**
   - `app_factory.py`: FastAPI con router REST (`routes_projects`, `routes_assets`, `routes_presentation`, `routes_export`), hub WebSocket (`ws.py`), mount statici per `/static/shared`, `/static/player`, `/static/canvas` e pagine `/p` (`/player`) e `/editor-canvas`.
   - `runtime.py`: avvia Uvicorn in un thread dedicato con shutdown pulito.

3. **Regia Desktop PyQt6 (`src/doublescreener/ui/`) e Web (`src/doublescreener/web/`)**
   - `MainWindow` con dock nativi (`ProjectsPanel`, `SlidesPanel`, `InspectorPanel`, `PresenterPanel`, `PalettePanel`).
   - `CanvasView`: `QWebEngineView` + `QWebChannel` verso `/editor-canvas`; usa lo stesso `web/shared/renderer.js` del player e dell'export.
   - `export/`: `static_site.py` (cartella standalone compatibile con `file://`) e `single_file.py` (HTML unico con asset inline).
