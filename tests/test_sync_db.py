import pytest
import os
from pathlib import Path
from sven.db.sync_db import SyncDB

@pytest.fixture
def fake_syncdb(tmp_path):
    var_db = tmp_path / "var/lib/sven/sync"
    var_db.mkdir(parents=True, exist_ok=True)
    
    # Symlink the fixture core.db to here
    fixture_db = Path(__file__).parent / "fixtures/fake_sync_db/core.db"
    if fixture_db.exists():
        (var_db / "core.db").symlink_to(fixture_db)
    
    return tmp_path

def test_syncdb_load(fake_syncdb, mocker):
    var_db = fake_syncdb / "var/lib/sven/sync"
    db = SyncDB(db_path=str(var_db))
    assert db.db_path.exists()
    
    # It should have loaded core.db
    pkg = db.get("bash")
    if pkg is not None:
        assert pkg.name == "bash"
        assert pkg.version == "5.2-1"
        assert pkg.desc == "Bourne again shell"
        assert "glibc>=2.38" in pkg.deps
    
def test_syncdb_virtual_resolution(fake_syncdb, mocker):
    var_db = fake_syncdb / "var/lib/sven/sync"
    db = SyncDB(db_path=str(var_db))
    
    pkg = db.get("vim")
    if pkg is not None:
        assert pkg.name == "neovim"
    
def test_syncdb_search(fake_syncdb, mocker):
    var_db = fake_syncdb / "var/lib/sven/sync"
    db = SyncDB(db_path=str(var_db))
    res = db.search("shell")
    if res:
        assert any(p.name == "bash" for p in res)

def test_syncdb_sync(fake_syncdb, mocker):
    var_db = fake_syncdb / "var/lib/sven/sync"
    db = SyncDB(db_path=str(var_db), mirror="http://fake.mirror")
    
    # Mock requests.get
    mock_resp = mocker.MagicMock()
    mock_resp.headers = {"content-length": "100"}
    mock_resp.iter_content.return_value = [b"a"*100]
    
    mocker.patch("requests.get", return_value=mock_resp)
    
    # Force sync
    res = db.sync(force=True)
    assert res.get("core", False) is True
