"""Command runner — claims `commands` rows from Rails, runs them through safety.

Slice 2 fills this in. Slice 1 ships the file as a placeholder so imports stabilise.
"""
from __future__ import annotations

from . import db
from .hardware.backend import HardwareBackend


class CommandRunner:
    def __init__(self, backend: HardwareBackend) -> None:
        self.backend = backend

    def process_pending(self) -> int:
        """Process at most one pending command; return number processed."""
        cmd = db.claim_pending_command()
        if cmd is None:
            return 0
        # Slice 2: dispatch by `cmd['kind']` through safety-aware execution.
        db.complete_command(int(cmd["id"]), ok=True, result={"note": "noop in slice 1"})
        return 1
