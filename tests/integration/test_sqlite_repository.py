import tempfile
from pathlib import Path

from live_caption_bridge.adapters.sqlite_repository import SQLiteRepository


def test_save_and_retrieve() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = SQLiteRepository(Path(tmp) / "test.db")
        row_id = db.save(
            original="hello",
            translated="olá",
            source_lang="en",
            target_lang="pt",
            started_ns=0,
            ended_ns=100,
        )
        assert row_id is not None and row_id > 0
        db.close()


def test_save_original_without_translation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = SQLiteRepository(Path(tmp) / "test.db")
        row_id = db.save(
            original="hello",
            translated=None,
            source_lang="en",
            target_lang=None,
            started_ns=0,
            ended_ns=100,
        )
        assert row_id is not None
        db.close()
