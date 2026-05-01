"""systemd watchdog notification — no-op when not under systemd.

Calling `notify_watchdog()` once per heartbeat is enough; systemd's
`WatchdogSec=30` triggers a restart if we go silent.
"""
from __future__ import annotations

import logging
import os
import socket

log = logging.getLogger(__name__)

_sock: socket.socket | None = None


def _ensure_sock() -> socket.socket | None:
    global _sock
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return None
    if _sock is not None:
        return _sock
    if addr.startswith("@"):
        addr = "\0" + addr[1:]   # abstract socket
    s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        s.connect(addr)
    except OSError as exc:
        log.warning("watchdog: cannot connect to NOTIFY_SOCKET=%r: %s", addr, exc)
        s.close()
        return None
    _sock = s
    return _sock


def notify_ready() -> None:
    s = _ensure_sock()
    if s is None:
        return
    try:
        s.sendall(b"READY=1\n")
    except OSError:
        pass


def notify_watchdog() -> None:
    s = _ensure_sock()
    if s is None:
        return
    try:
        s.sendall(b"WATCHDOG=1\n")
    except OSError:
        pass


def notify_stopping() -> None:
    s = _ensure_sock()
    if s is None:
        return
    try:
        s.sendall(b"STOPPING=1\n")
    except OSError:
        pass
