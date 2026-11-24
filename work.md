# DoubleScreener v2 — Piano di lavoro

**Stato:** pianificazione approvata, implementazione non iniziata
**Branch:** `v2-rewrite` (il branch `main` resta intatto e continua a servire GitHub Pages)
**Data:** 23 novembre 2026
**Autore:** sessione di analisi e progettazione

---

## 1. Visione

DoubleScreener diventa un **sistema di regia e presentazione a doppio schermo**:

- una **regia desktop PyQt6** installata sul PC del presentatore;
- un **second screen** che è una normale pagina web, servita in rete locale;
- il secondo schermo può essere un monitor collegato via HDMI allo stesso PC, oppure una Smart TV, un tablet o un altro PC collegato via browser.

La regia comanda; tutti i second screen sono specchio della stessa slide (mirror). L'editor visuale resta il cuore del prodotto, ma ora salva su disco tramite un backend Python e non più in `localStorage`.

### Obiettivi

1. Sostituire il salvataggio fragile in `localStorage` con persistenza reale su file.
2. Rendere il second screen indipendente dal browser della regia (LAN, multi-dispositivo).
3. Aggiungere un modello a **deck di slide** invece di una singola pagina.
4. Supportare **modalità** intercambiabili: slide HTML, pagine PDF, e in futuro altre (video, web, camera).
5. Rendere l'esperienza offline-first: nessun cloud, nessun account, dati leggibili e portabili.
6. Mantenere il sito GitHub Pages come vetrina + documentazione di setup.

### Non obiettivi v1

Account utente, collaborazione in tempo reale multi-utente, cloud sync, app mobile nativa, sandbox di JavaScript arbitrario, stampa, plugin di terze parti.

### Principi tecnici

- **Una sola fonte di verità:** il modello vive in Python. Il canvas e il player sono viste.
- **Un solo renderer:** la stessa funzione JavaScript trasforma una slide in DOM, usata da canvas, player ed export. Nessuna doppia implementazione HTML.
- **Niente build step:** HTML/CSS/JS serviti così come sono, nessun Node.js richiesto.
- **File leggibili:** progetti in JSON, asset come file separati, cache rigenerabile.
- **Fallire in modo esplicito:** errori con messaggio utente, log su file, nessun salvataggio silenzioso perso.

---

## 2. Decisioni prese

| Tema | Decisione |
|---|---|
| Prodotto | Editor visuale + second screen live |
| Backend | FastAPI + Uvicorn |
| Frontend web | Vanilla JS / HTML / CSS, nessun framework, nessun bundler |
| Comunicazione live | WebSocket |
| Persistenza | File JSON su disco + asset su filesystem |
| Accesso | Sessione locale, nessun login, rete fidata |
| Distribuzione v1 | Server locale, avvio da sorgente (`python -m doublescreener`) |
| Packaging | Rimandato (PyInstaller valutato dopo la v1) |
| Regia | Applicazione desktop **PyQt6** |
| Canvas editor | `QWebEngineView` dentro la regia, con pannelli Qt nativi |
| Processo | App unica: la GUI avvia Uvicorn in un thread |
| Accesso player | URL LAN + QR code |
| PDF | Renderizzato in immagini lato backend con PyMuPDF |
| Deck | Misto: slide HTML e pagine PDF nello stesso progetto |
| Multi-schermo | Mirror: tutti i client vedono la stessa slide |
| Navigazione | La regia è autoritaria, i client seguono |
| Lingua | Interfaccia bilingue IT/EN con i18n; documenti di lavoro in italiano |
| Codice v1 | Riscrittura da zero, conservando logo, landing e demo storica |
| Git | Branch `v2-rewrite`, `main` intatto |

---

## 3. Architettura

```
┌──────────────────────────────── PC REGIA ────────────────────────────────┐
│  PyQt6                                                                   │
│  ┌───────────┬──────────────────────────────┬──────────────────────┐     │
│  │ Progetti  │  Canvas                      │  Inspector           │     │
│  │ Slide     │  (QWebEngineView)            │  Proprietà           │     │
│  │ Presenta  │  renderer.js condiviso       │  Elementi/Template   │     │
│  └─────┬─────┴───────────────┬──────────────┴──────────┬───────────┘     │
│        │   QWebChannel       │                         │                 │
│  ┌─────▼─────────────────────▼─────────────────────────▼───────────┐     │
│  │  CORE                                                            │     │
│  │  models · store(JSON) · history · presentation · modes · export  │     │
│  └─────┬───────────────────────────────────────────┬───────────────┘     │
│        │                                           │                     │
│  ┌─────▼──────────────┐                  ┌─────────▼─────────────────┐   │
│  │ data/              │                  │ FastAPI + WS Hub          │   │
│  │ projects/ assets/  │                  │ (thread Uvicorn, :8765)   │   │
│  │ cache/ backups/    │                  └─────────┬─────────────────┘   │
│  └────────────────────┘                            │ HTTP + WebSocket    │
└────────────────────────────────────────────────────┼─────────────────────┘
                                                     │ LAN
                     ┌───────────────────────────────┴──────────────────┐
                     │                                                  │
          ┌──────────▼───────────┐                       ┌──────────────▼──────────┐
          │ Monitor HDMI / 2° PC │                       │ Smart TV / tablet / PC  │
          │ player web locale    │                       │ player web remoto       │
          └──────────────────────┘                       └─────────────────────────┘
```

### Flussi principali

**Modifica**
`input utente (Qt o canvas)` → `intent JSON` → `Core.apply()` → `mutazione modello` → `history.push()` → `canvas: patch/rerender` → `autosave (debounce)` → `store JSON`

**Presentazione**
`regia: next/prev/goto` → `PresentationController` → `WS broadcast {type:"state"}` + `WS {type:"slide"}` → `player render` → `ack`

**Import PDF**
`upload` → `PyMuPDF apre e conta pagine` → `salvataggio asset originale` → `dialog di import` → `creazione slide kind=pdf_page` → `render pagina on demand + cache WebP`

**Export**
`progetto + asset` → `generatore statico` → `cartella con index.html, renderer.js, assets, project.json` → `funziona anche con file://`

### Perché QWebEngineView per il canvas

Il canvas deve mostrare esattamente ciò che vedrà il second screen: usando lo stesso motore (Chromium) e lo stesso renderer JavaScript si elimina alla radice il problema "nell'editor era diverso". I pannelli, gli shortcut, i menu, la gestione progetti e la presentazione sono invece widget Qt nativi, come richiesto.

Il canvas viene caricato da `http://127.0.0.1:{port}/editor-canvas` (stessa origine del backend), così può usare `fetch` e asset senza problemi di CORS. La comunicazione con Qt avviene tramite **QWebChannel**, non via HTTP: è in-process, a bassa latenza e non richiede porte aggiuntive.

### Perché la GUI avvia Uvicorn

Un solo eseguibile da lanciare, un solo processo da chiudere, nessun "prima avvia il server, poi l'app". Uvicorn gira in un `threading.Thread` con un event loop dedicato; la chiusura avviene con `server.should_exit = True` e `join(timeout)`. Porta default `8765`, configurabile; se occupata si prova `8766..8780` e si segnala in UI.

---

## 4. Struttura del repository

```
doublescreener.github.io/
├── index.html                  # LANDING GitHub Pages (da aggiornare)
├── style.css                   # stile landing
├── logo.png
├── README.md                   # vetrina + quick start (IT/EN)
├── work.md                     # questo documento
├── app/                        # DEMO STORICA v1, intatta (non toccare)
│   ├── backend.html
│   ├── backend.css
│   ├── frontend.html
│   ├── frontend.css
│   └── sniffer.html
│
├── pyproject.toml              # pacchetto Python + dipendenze
├── .gitignore
├── src/doublescreener/
│   ├── __main__.py             # entry point CLI
│   ├── app.py                  # bootstrap QApplication + single instance
│   ├── config.py               # percorsi, porta, settaggi
│   ├── logging_setup.py
│   ├── core/
│   │   ├── models.py           # Project, Slide, Element, ... (Pydantic)
│   │   ├── store.py            # repository JSON atomico
│   │   ├── assets.py           # upload, hash, probing immagini
│   │   ├── history.py          # undo/redo a comandi
│   │   ├── presentation.py     # stato presentazione e broadcast
│   │   ├── templates.py        # template slide + temi
│   │   └── modes/
│   │       ├── base.py         # interfaccia Mode
│   │       ├── html_mode.py
│   │       └── pdf_mode.py
│   ├── server/
│   │   ├── app_factory.py      # creazione FastAPI + mount statici
│   │   ├── routes_projects.py
│   │   ├── routes_assets.py
│   │   ├── routes_presentation.py
│   │   ├── routes_export.py
│   │   ├── ws.py               # hub WebSocket
│   │   ├── runtime.py          # thread Uvicorn
│   │   └── errors.py
│   ├── pdf/
│   │   ├── importer.py         # apertura, conteggio pagine, range
│   │   └── renderer.py         # render + cache WebP
│   ├── export/
│   │   ├── static_site.py      # export cartella
│   │   └── single_file.py      # export self-contained
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── canvas.py           # QWebEngineView + QWebChannel
│   │   ├── bridge.py           # oggetto esposto al JS
│   │   ├── display_manager.py  # apertura player su monitor scelto
│   │   ├── i18n.py
│   │   ├── panels/
│   │   │   ├── projects_panel.py
│   │   │   ├── slides_panel.py
│   │   │   ├── inspector_panel.py
│   │   │   ├── palette_panel.py
│   │   │   └── presenter_panel.py
│   │   ├── dialogs/
│   │   │   ├── settings_dialog.py
│   │   │   ├── pdf_import_dialog.py
│   │   │   └── export_dialog.py
│   │   └── resources/
│   │       ├── icons/
│   │       └── theme.qss
│   ├── locales/
│   │   ├── it.json             # stringhe Qt
│   │   └── en.json
│   └── web/
│       ├── shared/
│       │   ├── renderer.js     # slide JSON → DOM (unico renderer)
│       │   ├── transitions.css
│       │   └── protocol.js
│       ├── player/
│       │   ├── index.html
│       │   ├── player.js
│       │   ├── player.css
│       │   └── locales/{it,en}.json
│       └── editor-canvas/
│           ├── index.html
│           ├── canvas.js
│           ├── canvas.css
│           └── locales/{it,en}.json
│
├── data/                       # runtime, gitignored
│   ├── projects/*.json
│   ├── assets/
│   ├── cache/pdf/
│   ├── backups/
│   └── app.log
│
├── tests/
│   ├── test_models.py
│   ├── test_store.py
│   ├── test_history.py
│   ├── test_api.py
│   ├── test_ws.py
│   ├── test_pdf.py
│   ├── test_export.py
│   └── test_i18n.py
│
└── docs/
    ├── architecture.md
    ├── api.md
    ├── ws-protocol.md
    └── setup.md
```

> `app/` non viene toccato: resta la demo giocabile della v1 su GitHub Pages. La nuova applicazione vive in `src/`.

---

## 5. Modello dati

Tutto è JSON serializzabile, versionato con `schema_version`, con funzione di migrazione `migrate(data)`.

### Project

```json
{
  "schema_version": 1,
  "id": "prj_01HX...",
  "name": "Lezione 3 - Reti",
  "created_at": "2026-11-23T10:00:00Z",
  "updated_at": "2026-11-23T10:42:11Z",
  "canvas": { "width": 1920, "height": 1080, "background": "#101014" },
  "default_transition": { "type": "fade", "duration_ms": 300 },
  "slides": [
    { "id": "sld_01", "kind": "html", "name": "Titolo", "background": null,
      "elements": [], "notes": "" },
    { "id": "sld_02", "kind": "pdf_page", "name": "PDF p. 3",
      "pdf": { "asset_id": "ast_9f2", "page": 3, "source_name": "reti.pdf" },
      "elements": [], "notes": "" }
  ]
}
```

### Slide

| Campo | Tipo | Note |
|---|---|---|
| `id` | string | `sld_` + ULID |
| `kind` | `html` \| `pdf_page` | estendibile |
| `name` | string | etichetta nella lista slide |
| `background` | string? | null = eredita dal progetto |
| `elements` | Element[] | vuoto per `pdf_page` puro |
| `pdf` | object? | solo per `pdf_page` |
| `notes` | string | note relatore (v1: solo visualizzazione in regia) |
| `transition` | object? | override della transizione di progetto |

### Element

```json
{
  "id": "el_7c1",
  "type": "text",
  "rect": { "x": 120, "y": 96, "w": 820, "h": 140 },
  "rotation": 0,
  "opacity": 1,
  "z": 3,
  "locked": false,
  "hidden": false,
  "content": { "text": "Benvenuti", "href": null, "src": null, "alt": "" },
  "style": {
    "font_family": "Inter", "font_size": 72, "font_weight": 700,
    "line_height": 1.1, "letter_spacing": 0,
    "color": "#ffffff", "background": "transparent",
    "padding": 0, "border_radius": 12,
    "border_width": 0, "border_color": "#000000",
    "shadow": null, "text_align": "left"
  },
  "animation": { "enter": "fadeIn", "duration_ms": 400, "delay_ms": 0,
                 "easing": "ease-out" }
}
```

Tipi v1: `text`, `image`, `button`, `box`, `line`. Tipi rimandati: `video`, `iframe`, `icon`, `table`, `group`.

**Coordinate:** sempre in pixel di design, riferite al canvas del progetto. Il player applica un `transform: scale()` con letterbox per adattarsi a qualsiasi viewport, quindi nessuna coordinata dipende dallo schermo.

**z-index:** ordine esplicito nel campo `z`; il renderer ordina per `z` poi per ordine di array (stabile).

### Presentation state (non persistito)

```json
{ "project_id": "prj_...", "index": 3, "playing": true, "black": false }
```

### Settings applicative

`settings.json` nella directory dati: `lang`, `port`, `bind`, `theme`, `last_project_id`, `canvas_defaults`, `pdf_render_width`, `autosave_ms`.

---

## 6. API REST

Base: `http://127.0.0.1:8765`. Tutte le risposte JSON, errori uniformi `{ "error": { "code": "...", "message": "..." } }`.

| Metodo | Path | Descrizione |
|---|---|---|
| GET | `/api/info` | versione, porta, IP LAN, URL player, stato presentazione |
| GET | `/api/projects` | elenco progetti (id, nome, n. slide, updated_at) |
| POST | `/api/projects` | crea progetto `{name, canvas?}` |
| GET | `/api/projects/{pid}` | progetto completo |
| PUT | `/api/projects/{pid}` | sostituzione completa, con `If-Match: updated_at` |
| DELETE | `/api/projects/{pid}` | elimina progetto |
| POST | `/api/projects/{pid}/duplicate` | duplica progetto e asset referenziati |
| POST | `/api/projects/{pid}/assets` | upload multipart → `{id, url, width, height}` |
| GET | `/api/assets/{aid}` | file originale |
| POST | `/api/projects/{pid}/pdf` | upload PDF → `{asset_id, pages, source_name}` |
| GET | `/api/assets/{aid}/pages/{n}` | pagina renderizzata (`?width=1920`) |
| POST | `/api/presentation/open` | `{project_id, index?}` apre sessione |
| POST | `/api/presentation/goto` | `{index}` |
| POST | `/api/presentation/step` | `{delta}` (−1 / +1) |
| POST | `/api/presentation/black` | `{on}` |
| GET | `/api/presentation/state` | stato corrente |
| GET | `/api/presentation/clients` | client connessi (id, ip, ua, ultimo ping) |
| POST | `/api/projects/{pid}/export` | genera export, restituisce job id |
| GET | `/api/exports/{job}/download` | zip dell'export |
| GET | `/p` | player (alias breve per la TV) |
| GET | `/player` | player |
| GET | `/editor-canvas` | canvas per QWebEngineView |
| WS | `/ws/player` | canale second screen |

**Nota:** la regia embedded chiama il `Core` direttamente, non passa da HTTP. Le rotte di presentazione esistono per debug, per test e per un futuro pannello regia remoto via browser.

**Concorrenza:** `PUT` con `If-Match` evita di sovrascrivere modifiche concorrenti. In caso di conflitto: `409` e la regia ricarica.

**Upload:** limite default 200 MB per file, estensioni ammesse per asset (`png jpg jpeg webp gif svg`) e PDF; validazione del contenuto oltre all'estensione.

---

## 7. Protocollo WebSocket

Endpoint: `/ws/player`. Una connessione = un client. Il server tiene un registro `client_id → {ip, ua, connected_at, last_pong}`.

### Handshake

Client → server:

```json
{ "type": "hello", "protocol": 1, "client_id": "uuid-generato-in-locale", "role": "player" }
```

Server → client:

```json
{
  "type": "session",
  "protocol": 1,
  "server": { "version": "2.0.0" },
  "lang": "it",
  "state": { "index": 3, "playing": true, "black": false },
  "project": { "id": "prj_...", "name": "Lezione 3 - Reti" },
  "deck": { "count": 12 },
  "canvas": { "width": 1920, "height": 1080 },
  "slide": { "...payload slide..." }
}
```

### Messaggi server → client

| Tipo | Payload | Uso |
|---|---|---|
| `session` | vedi sopra | stato iniziale completo |
| `slide` | `{index, slide, transition}` | cambia slide (payload completo) |
| `patch` | `{index, element}` | aggiornamento live di un elemento (editing durante presentazione) |
| `state` | `{index, playing, black}` | solo stato, nessun rendering |
| `reload` | `{}` | forza ricaricamento completo |
| `ping` | `{t}` | keepalive ogni 20s |
| `error` | `{code, message}` | errore fatale/progetto non disponibile |

### Messaggi client → server

| Tipo | Payload |
|---|---|
| `hello` | handshake |
| `pong` | `{t}` risposta al ping |
| `request_state` | chiede `session` completo (riconnessione) |
| `ack` | `{index, rendered_ms}` per diagnostica latenza |
| `error` | `{message}` errore rendering lato client |

### Regole

- Il client **non naviga**: può solo chiedere lo stato. Ogni tentativo locale viene ignorato.
- Riconnessione automatica con backoff esponenziale (0.5s → 5s, jitter), poi `request_state` senza ricaricare la pagina.
- Se il server non ha una presentazione attiva, il client mostra schermata di attesa con nome progetto e istruzioni.
- `black` è uno stato a sé: il player mostra nero totale ma resta connesso.
- Payload slide **senza base64**: solo URL agli asset, così il broadcast resta leggero.

### Perché WebSocket e non SSE

Serve la bidirezionalità per `request_state`, `ack`, presence dei client e futura diagnostica. In più Windows/Chrome e i browser delle Smart TV gestiscono bene i WebSocket senza configurazioni proxy particolari in LAN.

---

## 8. Modalità (plugin)

La presentazione non è rigida: una **modalità** definisce cosa significa "slide" e come si naviga. Interfaccia `Mode`:

```python
class Mode(Protocol):
    key: str                      # "html" | "pdf" | ...
    def can_handle(self, slide: Slide) -> bool: ...
    def build_payload(self, slide: Slide) -> dict: ...   # cosa manda al player
    def nav(self, direction: int) -> NavResult: ...      # next/prev, salta pagine?
    def controls(self) -> list[ControlSpec]: ...         # cosa mostra la regia
```

| Modalità | v1 | Comportamento |
|---|---|---|
| `html` | sì | slide con elementi, nav lineare |
| `pdf` | sì | pagina PDF come slide, nav lineare, prefetch pagine adiacenti |
| `video` | dopo | play/pause/seek, il player segue |
| `web` | dopo | URL remoto in iframe/kiosk, nav a comandi |
| `camera` | dopo | stream locale, usato come sfondo/slide |

Nel deck misto, ogni slide dichiara il proprio `kind`; la modalità viene risolta per slide, quindi un progetto può alternare slide HTML e pagine PDF senza cambiare modalità globale. La regia mostra i controlli della modalità della slide corrente.

**Punto di estensione:** aggiungere una modalità non deve richiedere modifiche al player oltre al renderer del nuovo payload; il player è già predisposto a ricevere payload arbitrari e a delegare in `modes/{kind}.js`.

---

## 9. Modulo regia PyQt6

### Layout

```
┌────────────────────────────────────────────────────────────────────────┐
│ Menu: File  Modifica  Slide  Presentazione  Lingua  Aiuto             │
├──────────┬──────────────────────────────────┬──────────────────────────┤
│ PROGETTI │                                  │ INSPECTOR                │
│ ├ lezione│          CANVAS                  │ ├ Posizione / dimensioni │
│ └ ...    │       QWebEngineView             │ ├ Stile tipografico      │
│          │       zoom / griglia / guide     │ ├ Colori / bordi / ombra │
│ SLIDE    │                                  │ ├ Animazione             │
│ ├ 1      │                                  │ └ Contenuto              │
│ ├ 2      │                                  │                          │
│ └ +      │                                  │ PALETTE ELEMENTI         │
├──────────┴──────────────────────────────────┴──────────────────────────┤
│ ▶ Precedente  Successivo  ■ Nero   Slide 3/12   Client: 2   URL+QR     │
└────────────────────────────────────────────────────────────────────────┘
```

### Componenti

- **MainWindow**: splitter ridimensionabili, dock widget, toolbar, status bar con stato server e client connessi.
- **ServerRuntime**: avvio/stop Uvicorn in thread, gestione porta occupata, log in UI, shutdown pulito su `closeEvent`.
- **ProjectsPanel**: elenco, nuovo, apri, rinomina, duplica, elimina (con conferma), import/export progetto.
- **SlidesPanel**: lista con miniature (renderizzate dal canvas o dal renderer headless), riordino drag & drop, aggiungi HTML/PDF, duplica, elimina, note.
- **Canvas**: zoom fit/50–200%, griglia, snap, guide di allineamento, selezione multipla con rubber band, resize/rotate con handle, editing testo inline, drop dalla palette.
- **InspectorPanel**: proprietà contestuali al tipo di elemento, controlli con undo coalescente (spinner/drag = una sola voce di history).
- **PalettePanel**: elementi trascinabili, template di slide, temi colore.
- **PresenterPanel**: stato presentazione, anteprima slide corrente, client connessi, URL LAN + QR, pulsante "apri su monitor…", black screen, note relatore.
- **DisplayManager**: elenco `QScreen`, apertura del player a schermo intero sul monitor scelto tramite seconda finestra `QWebEngineView` (modalità HDMI, senza chrome del browser); in alternativa apre il browser di sistema con l'URL.
- **SettingsDialog**: lingua, porta, binding LAN, canvas default, larghezza render PDF, intervallo autosave, tema.

### Scorciatoie

| Comando | Tasto |
|---|---|
| Salva | `Ctrl+S` |
| Annulla / Ripeti | `Ctrl+Z` / `Ctrl+Y` |
| Duplica elemento | `Ctrl+D` |
| Elimina | `Del` |
| Muovi 1px / 10px | frecce / `Shift+frecce` |
| Zoom fit | `Ctrl+0` |
| Presentazione avanti/indietro | `→` / `←` (con canvas non in editing testo) |
| Black screen | `B` |
| Fullscreen player locale | `F11` |

### Ciclo di vita

1. `QApplication` + verifica istanza singola (`QLocalServer`).
2. Caricamento settings e lingua.
3. Avvio `ServerRuntime` (porta, IP LAN).
4. Apertura progetto `last_project_id` o schermata benvenuto.
5. `MainWindow.show()`.
6. Su chiusura: stop server, flush autosave pendente, salvataggio settings.

---

## 10. Canvas e bridge

### Comunicazione Qt ↔ Canvas

`QWebChannel` espone due oggetti:

**JS → Qt** (`Bridge`), un solo slot generico:

```python
@pyqtSlot(str)
def intent(self, payload_json: str) -> None
```

Payload:

```json
{ "action": "element.update", "payload": { "id": "el_7c1", "changes": { "rect": { "x": 140 } } } }
```

Azioni: `ready`, `element.add`, `element.update`, `element.delete`, `element.move`, `element.reorder`, `element.duplicate`, `selection.change`, `text.edit`, `zoom.change`, `slide.request`, `animation.preview`.

**Qt → JS** (`Bridge.stateChanged` signal con stringa JSON):

| Messaggio | Effetto |
|---|---|
| `render_slide` | rerender completo (cambio slide, undo strutturale) |
| `patch_element` | aggiorna solo un elemento (drag, spinner, testo) |
| `selection` | evidenzia gli id selezionati |
| `zoom` | imposta zoom/pan |
| `play_animation` | anteprima animazione di ingresso |
| `theme` / `lang` | aggiorna variabili CSS e stringhe |

### Regole di interazione

- Durante il drag il canvas aggiorna solo il DOM locale; al `mouseup` invia un solo `element.update` con la posizione finale → una sola voce di undo.
- L'editing testo è inline con `contenteditable`; commit su blur/Invio, annullabile con Esc.
- Il canvas non è mai fonte di verità: se Qt rifiuta un intent, il canvas riceve lo stato corrente e si riallinea.
- Il renderer è lo stesso del player; il canvas aggiunge un livello di overlay (selezione, handle, guide) che **non** esiste nel player.
- Griglia e guide sono opzionali e non fanno parte dell'export.

### Fallback browser (per sviluppo e test)

`canvas.js` rileva l'assenza di `window.qt`: in quel caso mostra il canvas in sola visualizzazione e logga gli intent. Permette di testare il renderer in un browser normale senza avviare Qt. Non è una feature utente v1.

---

## 11. Pipeline PDF

1. **Upload**: file salvato come `data/assets/{aid}.pdf` (nome originale nei metadati).
2. **Ispezione**: PyMuPDF apre il file, legge numero pagine, dimensioni, titolo; rifiuta file corrotti o protetti da password (messaggio chiaro).
3. **Import dialog**: intervallo pagine (es. 1–12, pari, tutte), larghezza di render (default 1920), opzione "una slide per pagina".
4. **Creazione slide**: `kind: "pdf_page"`, con `pdf.asset_id` e `pdf.page`.
5. **Render on demand**: `GET /api/assets/{aid}/pages/{n}?width=1920`.
   - cache key: `{aid}/{width}/{n}.webp`
   - render in thread pool (`anyio.to_thread`), mai nel loop eventi
   - qualità: `width` default 1920; per 4K configurabile 3840
6. **Player**: riceve `image_url`, prefetch pagina `n+1` e `n−1`, transizione CSS.
7. **Regia**: anteprima pagina corrente + pulsanti "vai a pagina", input numerico, note.
8. **Invalidazione cache**: eliminazione asset o cambio larghezza → pulizia selettiva; comando "svuota cache PDF".

**Perché immagini e non PDF nativo:** i browser delle Smart TV spesso non renderizzano PDF inline; le immagini garantiscono identità visiva, sincronizzazione esatta della pagina e transizioni coerenti. Il PDF originale resta comunque conservato e ri-esportabile.

**Limiti v1:** niente annotazioni, niente testo selezionabile nel player, niente crop/zoom della pagina (rimandati).

---

## 12. Export

### Formato "cartella" (default)

```
export/Lezione-3/
├── index.html          # player standalone, apre project.json
├── project.json
├── renderer.js
├── player.css
├── transitions.css
├── locales/{it,en}.json
└── assets/
    ├── img_1.png
    └── pdf_reti_p3.webp
```

- Funziona da `file://` senza server.
- Navigazione: frecce, click, `Home`/`End`, `B` per nero; nessun pannello regia.
- Le pagine PDF sono pre-renderizzate alla larghezza scelta.

### Formato "file singolo"

- Tutto inline (CSS, JS, JSON, immagini base64).
- Warning se supera ~20 MB; sconsigliato per deck con PDF pesanti.
- Utile per consegnare un file unico a chi non ha il software.

### Requisiti di fedeltà

L'export usa **lo stesso** `renderer.js` e le stesse transizioni del player live. Test automatico: snapshot DOM renderizzato per un progetto di esempio, confronto canvas/player/export.

---

## 13. Undo/redo e autosave

**Command pattern** in `core/history.py`:

```python
@dataclass
class Command:
    label: str
    apply: Callable[[Project], None]
    revert: Callable[[Project], None]
    merge_key: str | None = None
    timestamp: float = 0.0
```

- Stack separati undo/redo, limite 200 voci.
- **Coalescing**: comandi con stesso `merge_key` entro 600 ms si fondono (drag, spinner, digitazione testo).
- La history è per progetto, in memoria, azzerata all'apertura (non persistita).
- Operazioni strutturali (aggiungi/elimina slide, import PDF) sono singole voci atomiche.
- Le azioni distruttive chiedono conferma ma restano annullabili.

**Autosave**

- Debounce 1000 ms dopo l'ultima mutazione.
- Scrittura atomica: file temporaneo nella stessa directory + `os.replace`.
- Backup: copia `{id}.bak.json` della versione precedente a ogni scrittura (1 livello) + snapshot giornaliero in `data/backups/` (max 10).
- Indicatore in status bar: "Salvato", "Modifiche non salvate", "Errore di salvataggio".
- Su errore: dialog con percorso e suggerimento, il file precedente resta intatto.
- `Ctrl+S` forza il flush immediato.
- Chiusura applicazione: flush sincrono prima di terminare.

**Recupero**

- All'avvio, se esiste un `.tmp` orfano più recente del JSON, si propone il recupero.
- JSON corrotto: si carica il `.bak` e si avvisa l'utente.

---

## 14. Internazionalizzazione

- **Qt**: `ui/i18n.py`, dizionari JSON `locales/{it,en}.json`, funzione `t("key", **kwargs)`, segnale `language_changed` che ogni pannello ascolta per riapplicare i testi. Nessuna compilazione `.qm`: più semplice da mantenere per due lingue.
- **Web**: `locales/{it,en}.json` + attributi `data-i18n` nel DOM; `i18n.js` carica il file e sostituisce i nodi.
- **Lingua default**: italiano. Override: impostazione app, `?lang=en` sul player.
- **Chiavi**: namespace piatti e leggibili (`menu.file.open`, `inspector.stroke.width`, `player.waiting.title`).
- **Test di parità**: `tests/test_i18n.py` verifica che IT e EN abbiano esattamente le stesse chiavi e che nessun valore sia vuoto.
- **Fallback**: chiave mancante → inglese → nome della chiave, con warning nel log (mai crash).
- **Documentazione**: README bilingue (sezioni IT/EN), `docs/` in italiano per ora, landing con switch lingua.

---

## 15. Persistenza, configurazione, log

- **Directory dati**: default `%APPDATA%\DoubleScreener` su Windows (via `platformdirs`), override CLI `--data-dir`. In sviluppo si usa `./data`.
- **Layout dati**: `projects/`, `assets/`, `cache/pdf/`, `backups/`, `settings.json`, `app.log`.
- **ID**: prefissi `prj_`, `sld_`, `el_`, `ast_` + ULID (ordinabili per tempo, leggibili).
- **Lock**: lock file per la directory dati; istanza singola garantita da `QLocalServer`. In caso di seconda istanza: si porta in primo piano quella esistente.
- **Log**: rotazione a 5 MB × 3, livello INFO di default, `--debug` per DEBUG. Uvicorn logga su file e, in modalità debug, su console.
- **Config**: dataclass `Settings` con default, validazione e migrazione; scrittura atomica come i progetti.

---

## 16. Rete e sicurezza

- Bind default `0.0.0.0:8765` per permettere i client LAN; la UI mostra chiaramente "accessibile a tutti i dispositivi della rete locale".
- Nessuna autenticazione in v1 (rete fidata), ma il codice prevede un hook `session_token` disattivato.
- Il player e le API condividono l'origine: niente CORS aperto.
- Upload: controllo estensione + magic bytes, limite dimensione, nomi file mai usati come path (solo `asset_id`), protezione da path traversal.
- Nessun endpoint che esegua HTML/JS arbitrario dell'utente: i contenuti sono elementi strutturati, non HTML libero. Un eventuale elemento `html` richiederà sanificazione esplicita (fuori v1).
- HTTPS: non necessario in LAN; documentato che l'uso su reti non fidate richiede un reverse proxy (fuori scope).
- Log senza dati sensibili; nessuna telemetria, nessuna chiamata a servizi esterni.

---

## 17. GitHub Pages

La repo è `doublescreener.github.io`, quindi il sito vive sul branch `main`. Regole:

- `main` resta la sorgente del sito: `index.html`, `style.css`, `logo.png`, `app/` non vengono rimossi.
- `v2-rewrite` non è pubblicato: Pages continua a servire `main` finché la v2 non è pronta.
- La landing va aggiornata per **raccontare il progetto e il setup**, non per far girare il backend (Pages è solo statico).
- La demo v1 rimane raggiungibile da `app/backend.html` con un badge "v1 — demo storica".

**Contenuti landing aggiornati**

1. Hero: nome, payoff, screenshot/GIF della regia e del secondo schermo.
2. "Come funziona": diagramma regia ↔ LAN ↔ TV.
3. Feature: editor visuale, PDF, deck misto, export, offline.
4. Requisiti: Windows 10/11, Python 3.11+, rete locale.
5. Setup passo-passo (clone, venv, install, run) con comandi copiabili.
6. Download / link alla release (quando esisterà).
7. Documentazione e wiki.
8. Switch lingua IT/EN e tema.
9. Footer: licenza, contributi, issue.
10. Sezione "Stato": v2 in sviluppo, v1 disponibile.

---

## 18. Stack e dipendenze

**Runtime**

| Pacchetto | Uso |
|---|---|
| Python 3.11+ (sviluppo su 3.13) | runtime |
| `fastapi` | API |
| `uvicorn[standard]` | server ASGI |
| `pydantic` v2 | modelli e validazione |
| `PyQt6`, `PyQt6-WebEngine` | regia e canvas |
| `PyMuPDF` | lettura/render PDF |
| `Pillow` | probing immagini, QR/PNG se serve |
| `segno` | QR code del player |
| `platformdirs` | directory dati per OS |
| `python-multipart` | upload |
| `portalocker` (opzionale) | lock tra processi |

**Sviluppo**

`pytest`, `pytest-asyncio`, `httpx`, `pytest-qt`, `ruff`, `mypy` (opzionale).

**Nessuna dipendenza Node.js.** Nessun bundler, nessun transpiler.

**Licenza:** il progetto è rilasciato sotto **GPL-3.0-only** (file `LICENSE`). La scelta deriva da PyQt6, distribuito sotto GPLv3. Se in futuro servisse una licenza permissiva (MIT/Apache), l'alternativa compatibile a livello API è **PySide6** (LGPL), con migrazione da pianificare a parte. In `pyproject.toml` va dichiarato `license = "GPL-3.0-only"`.

---

## 19. Comandi di sviluppo

```powershell
# 1. Clona e entra nel branch
git clone https://github.com/il-mangia/doublescreener.github.io.git
cd doublescreener.github.io
git switch v2-rewrite

# 2. Ambiente virtuale
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Installa in modalità editabile
pip install -U pip
pip install -e ".[dev]"

# 4. Avvia la regia (sviluppo)
python -m doublescreener --data-dir .\data --port 8765 --debug

# 5. Second screen
#    stesso PC:    http://127.0.0.1:8765/p
#    altro device: http://<IP-LAN>:8765/p

# 6. Solo backend, senza GUI (utile per test API/player)
python -m doublescreener.server --data-dir .\data --port 8765

# 7. Test e lint
pytest
ruff check . --fix
```

Su Linux/macOS: `source .venv/bin/activate` e path `./data`.

---

## 20. Milestone e TODO

Legenda: `[ ]` da fare · `[~]` in corso · `[x]` fatto

### M0 — Fondamenta (0,5 giornata)

- [x] Branch `v2-rewrite` creato da `main`
- [x] `work.md` committato
- [x] `LICENSE` con GNU GPL v3.0, nota di licenza in README e link nel footer della landing
- [x] `pyproject.toml` con dipendenze ed extra `dev` (`license = "GPL-3.0-only"`)
- [x] `.gitignore` (`data/`, `.venv/`, `__pycache__/`, `*.pyc`, `build/`, `dist/`, `.ruff_cache/`)
- [x] Struttura cartelle `src/doublescreener/**` con `__init__.py` minimi (`core`, `server`, `web`, `ui`)
- [x] `config.py` + `logging_setup.py` + CLI (`--data-dir`, `--port`, `--debug`)
- [x] `python -m doublescreener --help` funzionante
- [ ] Smoke test: QApplication vuota che si apre e si chiude (richiede extra `gui`, in M6)

### M1 — Core e persistenza (1–2 giornate)

- [x] Modelli Pydantic: `Project`, `Slide`, `Element`, `Rect`, `Style`, `Transition`, `PdfRef`
- [x] Validazione: id univoci, riferimenti asset esistenti, limiti canvas
- [x] `Store` JSON: list/create/get/update/delete, scritture atomiche, `.bak`
- [x] Lock per progetto + lock directory dati
- [x] `assets.py`: upload, hash SHA-256 per dedupe, probing dimensioni
- [x] `history.py`: comandi, undo/redo, coalescing, limite
- [x] `migrate(data)` con `schema_version`
- [x] Test: `test_models.py`, `test_store.py`, `test_history.py` (suite completa: 93 test, tutti verdi)

### M2 — API (1 giornata)

- [x] `app_factory.py` con router, gestione errori, OpenAPI
- [x] CRUD progetti + duplicate + `If-Match`
- [x] Upload/download asset
- [x] `GET /api/info` con IP LAN e URL player
- [x] Mount statici `/p`, `/player` e asset (`/editor-canvas` arriva in M8)
- [x] Test `test_api.py` con `httpx` (CRUD, upload, errori, conflitti) + avvio/stop `ServerRuntime` reale

### M3 — Renderer e player (2 giornate)

- [x] `renderer.js`: slide → DOM, stili, z-index, transizioni
- [x] `player/index.html|css|js`: fullscreen, letterbox, stati waiting/error/black
- [x] Client WS: hello, session, slide, state, reload, ping/pong, riconnessione
- [x] Prefetch asset e pagina PDF successiva
- [x] Localizzazione player (`?lang=`)
- [ ] Test manuale con 2 dispositivi reali (PC + TV/tablet)

### M4 — Hub WS e presentazione (1–2 giornate)

- [x] `ws.py`: connection manager, ruoli, broadcast, presence
- [x] `presentation.py`: open/goto/step/black, stato coerente
- [x] Broadcast `slide`/`state` + `ack` diagnostica
- [x] Test `test_ws.py` (connessione, handshake, reconnect, black, cambio progetto)
- [x] Endpoint REST di presentazione allineati allo stato WS

### M5 — PDF (2 giornate)

- [ ] `pdf/importer.py`: apertura, pagine, metadati, errori
- [ ] `pdf/renderer.py`: render con PyMuPDF, cache WebP, thread pool
- [ ] Endpoint pagina + invalidazione cache
- [ ] `PdfImportDialog`: range, larghezza, anteprima, "una slide per pagina"
- [ ] `pdf_mode` nel player: immagine, preload, transizione
- [ ] Test `test_pdf.py` (conteggio, range, cache hit/miss, file corrotto)

### M6 — Regia PyQt6: shell (2–3 giornate)

- [ ] `MainWindow`: layout, dock, toolbar, status bar
- [ ] `ServerRuntime`: avvio/stop Uvicorn, porta occupata, shutdown pulito
- [ ] Istanza singola (`QLocalServer`) e ripristino finestra
- [ ] `ProjectsPanel`: lista, nuovo, apri, rinomina, duplica, elimina
- [ ] `SlidesPanel`: lista, miniature, riordino, aggiungi/duplica/elimina
- [ ] `PresenterPanel`: stato, client connessi, URL+QR, black, note
- [ ] `DisplayManager`: apertura player fullscreen su `QScreen` scelto
- [ ] `SettingsDialog`: lingua, porta, canvas, PDF, autosave, tema
- [ ] Persistenza settings e ultimo progetto

### M7 — Canvas (3–4 giornate)

- [ ] `QWebEngineView` su `/editor-canvas` (profilo persistente)
- [ ] `QWebChannel` + `Bridge.intent` / `stateChanged`
- [ ] Rendering slide con `renderer.js` + overlay di editing
- [ ] Selezione singola/multipla + rubber band
- [ ] Drag, resize, rotazione con handle
- [ ] Snap a griglia + guide di allineamento
- [ ] Zoom/pan (fit, 25–200%)
- [ ] Drop dalla palette
- [ ] Editing testo inline (`contenteditable`, Esc/Invio)
- [ ] Scorciatoie globali (frecce, Del, Ctrl+D/Z/Y/S)
- [ ] Sincronizzazione bidirezionale robusta (intent rifiutati → riallineamento)

### M8 — Inspector, contenuti, template (3 giornate)

- [ ] Inspector posizione/dimensioni/rotazione/opacità/z
- [ ] Stile testo: font, size, weight, line-height, spacing, colore, allineamento
- [ ] Stile box: background, padding, bordo, radius, ombra
- [ ] Contenuti: testo, link, immagine (upload/sostituisci/crop semplice), pulsante, box, linea
- [ ] Animazioni di ingresso + anteprima nel canvas
- [ ] 5 template di slide (titolo, titolo+sottotitolo, elenco, immagine full, due colonne)
- [ ] Temi colore (3–4) applicabili al progetto
- [ ] Gestione font di sistema + eventuale font bundle

### M9 — Export e import (2 giornate)

- [ ] `static_site.py`: cartella con player standalone
- [ ] `single_file.py`: HTML unico con asset inline
- [ ] Navigazione standalone (tastiera, click, black) senza server
- [ ] `ExportDialog`: formato, percorso, anteprima dimensioni
- [ ] Import progetto JSON (validazione + migrazione)
- [ ] Test `test_export.py`: snapshot rendering + apertura `file://`

### M10 — i18n, rifiniture, QA (2–3 giornate)

- [ ] Locale Qt IT/EN complete
- [ ] Locale web IT/EN complete (player + canvas)
- [ ] `test_i18n.py` parità chiavi
- [ ] Tema scuro (default) + chiaro
- [ ] Stati vuoti e messaggi di errore utili
- [ ] Accessibilità base: contrasto, focus, tooltip, navigazione tastiera
- [ ] Diagnostica: pannello log, "copia info sistema"
- [ ] `docs/architecture.md`, `api.md`, `ws-protocol.md`, `setup.md`
- [ ] README bilingue + quick start
- [ ] Landing GitHub Pages aggiornata (hero, feature, setup, IT/EN)
- [ ] QA matrix: Windows 10/11, Chrome/Edge/Firefox, Smart TV, tablet
- [ ] Tag `v2.0.0` e note di rilascio

### M11 — Dopo la v1

- [ ] Packaging PyInstaller (WebEngine + PyMuPDF: risorse e plugin)
- [ ] Installer Windows (Inno Setup) e portable ZIP
- [ ] PIN/token opzionale per il player
- [ ] Modalità `video`, `camera`, `web`
- [ ] Note relatore su monitor secondario
- [ ] Assegnazione schermo → slide (multi-view)
- [ ] Gruppi, allineamento/distribuzione, lock tra elementi
- [ ] Export PDF del deck
- [ ] Cronologia versioni progetto in UI

---

## 21. Criteri di accettazione v1

1. Creo un progetto, aggiungo testo/immagine/pulsante/box, modifico stile e animazione, salvo, chiudo e riapro: tutto identico.
2. Apro il player su un altro dispositivo via QR: la slide appare in <1 s e cambia in <300 ms su LAN.
3. Il player si riconnette da solo dopo un riavvio del server e riprende la slide corretta senza reload manuale.
4. Importo un PDF da 50 pagine, navigo pagina per pagina; pagina già renderizzata <150 ms, prima renderizzazione <800 ms a 1920 px.
5. Faccio 20 modifiche, annullo e ripristino tutto; dopo un crash, l'autosave ripristina l'ultimo stato senza perdita.
6. Esporto in cartella e apro `index.html` da `file://`: resa identica al player live, navigazione funzionante.
7. Tutta l'interfaccia è disponibile in italiano e inglese senza chiavi mancanti.
8. Nessun dato viene corrotto da scritture concorrenti o chiusura improvvisa.
9. Il canvas mostra esattamente ciò che vede il player (stesso motore, stesso renderer).
10. Il server non è raggiungibile da Internet per configurazione errata: bind e messaggi UI sono espliciti.

---

## 22. Strategia di test

| Livello | Strumento | Cosa |
|---|---|---|
| Unit | pytest | modelli, store, history, migrazioni, i18n |
| API | httpx + ASGITransport | CRUD, upload, errori, conflitti |
| WS | TestClient WebSocket | handshake, broadcast, reconnect, black |
| PDF | pytest + fixture PDF | conteggio, range, cache, file corrotto |
| Export | pytest + parsing HTML | presenza asset, snapshot DOM (node non richiesto: si confronta struttura) |
| GUI | pytest-qt (mirato) | apertura finestra, azioni pannelli, senza pixel test |
| E2E manuale | checklist | 2 dispositivi, TV, proiettore, HDMI |

**CI:** GitHub Actions opzionale, solo job Linux per test Python (senza PyQt6/WebEngine); i test GUI restano locali.

---

## 23. Rischi e mitigazioni

| Rischio | Impatto | Mitigazione |
|---|---|---|
| Licenza permissiva richiesta in futuro | medio | il progetto è GPL-3.0-only per via di PyQt6; fallback PySide6 (LGPL) con migrazione pianificata |
| QWebEngineView instabile/GPU su alcuni Windows | medio | flag software rendering attivabile, log, versione Qt pinnata |
| PDF enormi o pagine giganti | medio | render on demand, limite dimensioni, timeout, cache |
| Wi-Fi debole in aula | medio | payload leggeri, preload, riconnessione, indicatore qualità |
| Perdita dati | alto | scrittura atomica, `.bak`, backup giornalieri, test |
| Doppia implementazione del rendering | alto | un solo `renderer.js`, test di parità canvas/player/export |
| Latenza del re-render del canvas | medio | patch mirate invece di rerender completo |
| Smart TV con browser datati | medio | solo feature CSS/JS baseline, test su device reale |
| Packaging WebEngine complicato | medio | rimandato, con checklist PyInstaller dedicata |
| Python da Microsoft Store | basso | documentare installazione python.org o `uv` |
| Multi-monitor e DPI scaling | medio | test su 100/125/150%, coordinate in px di design |

---

## 24. Domande aperte

1. **Elementi extra v1:** servono video, iframe, icone, tabelle o gruppi?
2. **Allineamento:** in v1 basta lo snap o servono allinea/distribuisci espliciti?
3. **Font:** solo font di sistema o download di Google Fonts per uso offline?
4. **Note relatore:** in v1 solo testo in regia o anche finestra separata sul monitor del presentatore?
5. **Telecomando:** supporto a clicker/presenter USB (tasti Pagina su/giù) in v1?
6. **Tema visivo:** mantenere l'identità attuale (blu/verde) o nuovo design system?
7. **Destinazione dell'app v1:** resta demo in `app/` o va spostata in `legacy/`?
8. **Limiti:** dimensione massima asset, numero massimo slide, durata cache PDF?
9. **Export PDF del deck:** utile in v1 o rimandato?

---

## 25. Registro delle decisioni

| Data | Decisione | Motivazione |
|---|---|---|
| 2026-11-23 | Licenza **GPL-3.0-only** | PyQt6 è GPLv3: coerenza legale senza cambiare framework |
| 2026-11-23 | Riscrittura completa, branch `v2-rewrite` | il codice v1 è monolitico e basato su `localStorage` |
| 2026-11-23 | Backend FastAPI + Uvicorn | WebSocket nativi, async, OpenAPI, ecosistema |
| 2026-11-23 | Regia in PyQt6, canvas in QWebEngineView | pannelli nativi + resa identica al player |
| 2026-11-23 | Player web vanilla, niente framework | zero build, gira su qualsiasi browser/TV |
| 2026-11-23 | WebSocket per il live | bidirezionalità, presence, riconnessione |
| 2026-11-23 | JSON su disco invece di database | portabilità, trasparenza, zero setup |
| 2026-11-23 | App unica con server embedded | un solo avvio, un solo processo |
| 2026-11-23 | PDF in immagini via PyMuPDF | compatibilità Smart TV e sync esatta |
| 2026-11-23 | Deck misto HTML + PDF | flessibilità didattica |
| 2026-11-23 | Mirror su tutti gli schermi | semplicità e comportamento prevedibile |
| 2026-11-23 | Regia autoritaria sulla navigazione | evita client fuori sincrono in aula |
| 2026-11-23 | i18n IT/EN con dizionari JSON | niente toolchain Qt, facile manutenzione |
| 2026-11-23 | `main` intatto per GitHub Pages | il sito continua a funzionare durante lo sviluppo |
| 2026-11-23 | Demo v1 conservata in `app/` | valore storico e confronto |
| 2026-11-23 | Packaging rimandato | prima validare il prodotto |
