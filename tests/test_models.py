import pytest
from sven.db.models import Package

def test_package_creation_minimal():
    pkg = Package(name="foo", version="1.0", desc="A pkg", url="", repo="core")
    assert pkg.name == "foo"
    assert pkg.deps == []
    assert pkg.origin == "official"

def test_package_creation_full():
    pkg = Package(
        name="bar", version="2.0", desc="Bar pkg", url="http://bar.com",
        repo="extra", origin="core",
        deps=["foo>=1.0"], makedeps=["make"], optdeps=["baz: optional"],
        conflicts=["bar-git"], provides=["bar"], replaces=["bar-old"]
    )
    assert "foo>=1.0" in pkg.deps
    assert "make" in pkg.makedeps
    assert "bar" in pkg.provides
    
def test_package_equality():
    pkg1 = Package("a", "1", "d", "u", "r")
    pkg2 = Package("a", "1", "d", "u", "r")
    pkg3 = Package("a", "2", "d", "u", "r")
    assert pkg1 == pkg2
    assert pkg1 != pkg3
