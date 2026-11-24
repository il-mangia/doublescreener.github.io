# API REST — DoubleScreener v2

Base locale predefinita: `http://127.0.0.1:8765`.
Documentazione interattiva OpenAPI disponibile su `/api/docs`.

Tutti gli errori seguono il formato uniforme:

```json
{ "error": { "code": "...", "message": "..." } }
```

## Endpoint principali

| Metodo | Path | Descrizione |
|---|---|---|
| `GET` | `/api/info` | Versione, porta, IP LAN, URL player, stato presentazione |
| `GET` | `/api/projects` | Elenco progetti |
| `POST` | `/api/projects` | Crea progetto (`{name, canvas?, slides?}`) |
| `GET` | `/api/projects/{pid}` | Progetto completo (header `ETag`) |
| `PUT` | `/api/projects/{pid}` | Sostituzione completa (supporta `If-Match`) |
| `DELETE` | `/api/projects/{pid}` | Elimina progetto |
| `POST` | `/api/projects/{pid}/duplicate` | Duplica progetto |
| `POST` | `/api/projects/{pid}/assets` | Upload multipart immagine/PDF |
| `GET` | `/api/assets/{aid}` | Download file originale dell'asset |
| `POST` | `/api/projects/{pid}/pdf` | Upload PDF con metadati pagine |
| `GET` | `/api/assets/{aid}/pages/{n}` | Pagina PDF renderizzata WebP (`?width=1920`) |
| `POST` | `/api/presentation/open` | Apre presentazione (`{project_id, index?}`) |
| `POST` | `/api/presentation/goto` | Vai alla slide (`{index}`) |
| `POST` | `/api/presentation/step` | Avanza/indietreggia (`{delta}`) |
| `POST` | `/api/presentation/black` | Attiva/disattiva schermo nero (`{on}`) |
| `GET` | `/api/presentation/state` | Stato presentazione corrente |
| `GET` | `/api/presentation/clients` | Client WebSocket connessi |
| `POST` | `/api/projects/{pid}/export` | Genera export (`{format: "folder" \| "single_file"}`) |
| `GET` | `/api/exports/{job}/download` | Scarica `.zip` o `.html` generato |
