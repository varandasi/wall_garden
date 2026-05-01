"""Photographer tick + take_photo tests."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from wallgardend.photographer import Photographer, take_photo

from .fakes import FakeBackend, FakeClock


@pytest.fixture
def backend():
    return FakeBackend()


def test_photographer_takes_first_photo_when_due(backend, tmp_path, monkeypatch):
    monkeypatch.setattr('wallgardend.db.insert_photo', lambda **_: 1)
    photog = Photographer(backend=backend, photos_dir=tmp_path, interval_s=3600.0,
                           next_due_mono=0.0)
    out = photog.tick(now_mono=10.0, now_utc=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc))
    assert out is not None
    assert out in [type(out)(p) for p in backend.photos_taken]
    # Second tick within the hour: nothing happens.
    assert photog.tick(now_mono=10.5, now_utc=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)) is None


def test_photographer_repeats_after_interval(backend, tmp_path, monkeypatch):
    monkeypatch.setattr('wallgardend.db.insert_photo', lambda **_: 1)
    photog = Photographer(backend=backend, photos_dir=tmp_path, interval_s=60.0)
    photog.tick(now_mono=0.1, now_utc=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc))
    photog.tick(now_mono=70.0, now_utc=datetime(2026, 5, 1, 12, 1, tzinfo=timezone.utc))
    assert len(backend.photos_taken) == 2


def test_take_photo_persists_row(backend, tmp_path, monkeypatch):
    inserted = {}

    def fake_insert(**kwargs):
        inserted.update(kwargs)
        return 7

    monkeypatch.setattr('wallgardend.db.insert_photo', fake_insert)
    p = take_photo(backend, tmp_path, zone_id=2,
                   now_utc=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc))
    assert p.exists()
    assert inserted['zone_id'] == 2
    assert inserted['path'] == str(p)
