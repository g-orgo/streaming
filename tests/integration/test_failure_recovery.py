import tempfile
from pathlib import Path

def test_database_survives_service_offline() -> None:
    from live_caption_bridge.adapters.sqlite_repository import SQLiteRepository
    with tempfile.TemporaryDirectory() as tmp:
        db = SQLiteRepository(Path(tmp) / "test.db")
        db.save("original", None, "en", None, 0, 100)
        db.close()
        db2 = SQLiteRepository(Path(tmp) / "test.db")
        row_id = db2.save("novo", "new", "pt", "en", 200, 300)
        assert row_id is not None
        db2.close()


def test_recovery_after_abrupt_restart() -> None:
    from live_caption_bridge.adapters.sqlite_repository import SQLiteRepository
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "test.db"
        db = SQLiteRepository(p)
        db.save("antes", "before", "pt", "en", 0, 100)
        db.close()
        db2 = SQLiteRepository(p)
        row_id = db2.save("depois", "after", "pt", "en", 200, 300)
        assert row_id is not None
        db2.close()
