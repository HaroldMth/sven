import pytest
from sven.db.local_db import LocalDB
from sven.db.models import Package
from sven.exceptions import DatabaseLockError

@pytest.fixture
def fake_localdb(tmp_path):
    return tmp_path

def test_local_db_init(fake_localdb):
    db = LocalDB(db_path=str(fake_localdb / "installed"), lock_path=str(fake_localdb / "db.lck"))
    assert db.db_path.exists()
    assert db.lock_path.name == "db.lck"

def test_register_package(fake_localdb):
    db = LocalDB(db_path=str(fake_localdb / "installed"), lock_path=str(fake_localdb / "db.lck"))
    
    pkg = Package("testpkg", "1.0", "desc", "", "core")
    files = ["/usr/bin/test", "/etc/test.conf"]
    
    db.register(pkg, files, True)
    
    installed = db.get("testpkg")
    assert installed is not None
    assert installed.version == "1.0"
    assert "/usr/bin/test" in db.get_files("testpkg")

def test_unregister_package(fake_localdb):
    db = LocalDB(db_path=str(fake_localdb / "installed"), lock_path=str(fake_localdb / "db.lck"))
    
    pkg = Package("testpkg2", "1.0", "desc", "", "core")
    db.register(pkg, ["/usr/bin/test2"], True)
    
    assert db.get("testpkg2") is not None
    db.unregister("testpkg2")
    assert db.get("testpkg2") is None

def test_orphans(fake_localdb):
    db = LocalDB(db_path=str(fake_localdb / "installed"), lock_path=str(fake_localdb / "db.lck"))
    
    pkg1 = Package("app", "1.0", "desc", "", "core", deps=["libapp"])
    db.register(pkg1, [], True)
    
    pkg2 = Package("libapp", "1.0", "desc", "", "core")
    db.register(pkg2, [], False)
    
    pkg3 = Package("orphanlib", "1.0", "desc", "", "core")
    db.register(pkg3, [], False)
    
    o = db.orphans()
    assert len(o) == 1
    assert o[0].name == "orphanlib"

def test_lock_acquire_release(fake_localdb):
    db = LocalDB(db_path=str(fake_localdb / "installed"), lock_path=str(fake_localdb / "db.lck"))
    
    # First success
    db.acquire_lock()
    assert db.lock_path.exists()
    
    # Second should fail
    db2 = LocalDB(db_path=str(fake_localdb / "installed"), lock_path=str(fake_localdb / "db.lck"))
    with pytest.raises(DatabaseLockError):
        db2.acquire_lock()
        
    db.release_lock()
    assert not db.lock_path.exists()
