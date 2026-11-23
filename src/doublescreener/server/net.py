"""Utility di rete: IP LAN e ricerca porta libera."""

from __future__ import annotations

import socket


def lan_ip() -> str:
    """Rileva l'IP della scheda di rete usata per uscire in LAN.

    Non invia traffico: la connect UDP serve solo al sistema per scegliere
    l'interfaccia. In assenza di rete restituisce ``127.0.0.1``.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def is_port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
        return True


def find_free_port(host: str, start: int, attempts: int = 15) -> int:
    for port in range(start, start + attempts):
        if is_port_free(host, port):
            return port
    raise OSError(f"nessuna porta libera tra {start} e {start + attempts - 1}")
