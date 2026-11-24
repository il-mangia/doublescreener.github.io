# Protocollo WebSocket — DoubleScreener v2

Endpoint: `ws://<host>:<port>/ws/player`.
La regia è autoritaria: i client ricevono lo stato e non comandano la navigazione.

## Handshake

Client → Server:

```json
{ "type": "hello", "protocol": 1, "client_id": "uuid", "role": "player" }
```

Server → Client:

```json
{
  "type": "session",
  "protocol": 1,
  "server": { "version": "2.0.0.dev0" },
  "lang": "it",
  "state": { "index": 0, "playing": true, "black": false, "slide_count": 5, "project_id": "prj_..." },
  "project": { "id": "prj_...", "name": "Demo" },
  "deck": { "count": 5 },
  "canvas": { "width": 1920, "height": 1080, "background": "#101014" },
  "slide": { "...payload slide..." }
}
```

## Messaggi Server → Client

- `session`: stato iniziale completo o risposta a `request_state`.
- `slide`: `{index, slide, transition, prefetch}` al cambio slide.
- `state`: `{index, playing, black, slide_count, project_id}` per cambi di stato (es. schermo nero).
- `ping`: `{t}` keepalive periodico.
- `reload`: forza il ricaricamento del player.
- `error`: `{code, message}`.

## Messaggi Client → Server

- `hello`: handshake iniziale.
- `pong`: `{t}` risposta al keepalive.
- `request_state`: richiede nuovamente `session`.
- `ack`: `{index, rendered_ms}` conferma di rendering.
- `error`: `{message}` segnalazione errore lato client.
