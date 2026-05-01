"""Daemon entrypoint — wires settings, hardware backend, DB pool, and the loop."""
from __future__ import annotations

import logging
import signal
import sys

import structlog

from . import db
from .config import load_hardware_map, load_settings
from .control_loop import ControlLoop
from .hardware.factory import make_backend


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
    )


def main() -> int:
    settings = load_settings()
    configure_logging(settings.log_level)
    log = structlog.get_logger("wallgardend.main")
    log.info("starting", backend=settings.backend, sim_speed=settings.sim_speed)

    hw_map = load_hardware_map(settings.hardware_yml)
    backend = make_backend(settings, hw_map)

    # Try to bring up the DB pool — if it fails, log and continue. The loop
    # tolerates DB outages (writes silently drop). This lets you run the daemon
    # against the simulator without Postgres for early development.
    try:
        db.init_pool(settings.database_url)
        log.info("db_pool_ready")
    except Exception as exc:
        log.warning("db_pool_failed", error=str(exc))

    # ControlLoop falls back to default zone configs at first boot, then
    # refreshes from the `zones` table every `config_reload_s` seconds.
    loop = ControlLoop(backend=backend, settings=settings)

    def _handle_term(signum, _frame):
        log.info("shutdown_requested", signal=signum)
        backend.shutdown()
        db.close_pool()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handle_term)
    signal.signal(signal.SIGINT, _handle_term)

    loop.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
