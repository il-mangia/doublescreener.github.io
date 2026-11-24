# Setup e sviluppo — DoubleScreener v2

## Requisiti

- Python **3.11+** (sviluppato e testato su Python 3.13)
- Windows 10/11, Linux o macOS
- Nessuna dipendenza Node.js richiesta

## Installazione da sorgente

```powershell
git clone https://github.com/il-mangia/doublescreener.github.io.git
cd doublescreener.github.io
git switch v2-rewrite

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -U pip
pip install -e ".[gui,dev]"
```

Su Linux/macOS: `source .venv/bin/activate`.

## Avvio

```powershell
# Regia desktop PyQt6 + server embedded
python -m doublescreener --data-dir .\data --port 8765

# Solo server headless (API + player web)
python -m doublescreener --headless --data-dir .\data --port 8765
```

## Second screen

- Sullo stesso PC: `http://127.0.0.1:8765/p`
- Da altro dispositivo in LAN (TV, tablet, secondo PC): `http://<IP-LAN>:8765/p` (o inquadra il QR mostrato nel pannello Presentazione).

## Test e lint

```powershell
pytest
ruff check .
```
