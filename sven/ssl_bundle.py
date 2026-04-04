# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  ssl_bundle.py — CA trust for git/curl on minimal (LFS) systems
# ============================================================
#
#  Many setups have no single ca-certificates.crt but do have
#  /etc/ssl/certs with OpenSSL-hashed *.0 entries — git needs either
#  http.sslCAInfo (bundle file) or http.sslCAPath (that directory).
# ============================================================

import os
import re
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

_openssl_trust_cache: Optional[Tuple[Optional[str], Optional[str]]] = None


def _is_nonempty_file(p: Path) -> bool:
    try:
        return p.is_file() and p.stat().st_size > 0
    except OSError:
        return False


def _dir_has_capath_material(d: Path) -> bool:
    """True if directory looks like an OpenSSL CApath (hashed .0) or many PEMs."""
    if not d.is_dir():
        return False
    try:
        resolved = d.resolve()
    except OSError:
        resolved = d
    # Standard trust store layout on most Linux distros (may lack ca-certificates.crt)
    try:
        if resolved == Path("/etc/ssl/certs").resolve():
            return any(x for x in d.iterdir() if not x.name.startswith("."))
    except OSError:
        pass
    try:
        entries = [x for x in d.iterdir() if x.is_file()]
    except OSError:
        return False
    if len(entries) >= 8:
        return True
    hash_style = 0
    pem_like = 0
    for x in entries:
        name = x.name
        if len(name) == 10 and name.endswith(".0") and re.match(
            r"^[0-9a-f]{8}\.0$", name, re.I
        ):
            hash_style += 1
        elif name.endswith((".pem", ".crt")):
            pem_like += 1
    return hash_style >= 1 or pem_like >= 3


def _parse_openssl_dir(stdout: str) -> Optional[Path]:
    m = re.search(r'OPENSSLDIR:\s*"([^"]+)"', stdout)
    if m:
        return Path(m.group(1).strip())
    m = re.search(r"OPENSSLDIR:\s*(\S+)", stdout)
    if m:
        return Path(m.group(1).strip().strip('"'))
    return None


def _openssl_ca_paths() -> Tuple[Optional[str], Optional[str]]:
    """
    Ask OpenSSL where it was built to look for certs (matches linked git often).
    Returns (cafile, capath) — either may be None.
    """
    global _openssl_trust_cache
    if _openssl_trust_cache is not None:
        return _openssl_trust_cache

    cafile: Optional[str] = None
    capath: Optional[str] = None

    try:
        r = subprocess.run(
            ["openssl", "version", "-d"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if r.returncode == 0:
            od = _parse_openssl_dir(r.stdout)
            if od and od.is_dir():
                for cand in (
                    od / "cert.pem",
                    od.parent / "cert.pem",
                    od / "certs" / "ca-certificates.crt",
                    od / "certs" / "ca-bundle.crt",
                ):
                    if _is_nonempty_file(cand):
                        cafile = str(cand.resolve())
                        break
                certs_dir = od / "certs"
                if not cafile and certs_dir.is_dir() and _dir_has_capath_material(certs_dir):
                    capath = str(certs_dir.resolve())
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    _openssl_trust_cache = (cafile, capath)
    return _openssl_trust_cache


def _static_bundle_candidates() -> List[str]:
    return [
        "/etc/ssl/certs/ca-certificates.crt",
        "/etc/ca-certificates/extracted/tls-ca-bundle.pem",
        "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",
        "/etc/ssl/cert.pem",
        "/etc/pki/tls/certs/ca-bundle.crt",
        "/etc/ssl/ca-bundle.pem",
        "/var/lib/ca-certificates/ca-bundle.pem",
        "/usr/lib/ssl/cert.pem",
        "/usr/lib/ssl/certs/ca-certificates.crt",
        "/usr/ssl/cert.pem",
        "/usr/local/share/certs/ca-root-nss.crt",
        "/usr/share/ssl/cert.pem",
    ]


def _static_capath_candidates() -> List[str]:
    return [
        "/etc/ssl/certs",
        "/etc/pki/tls/certs",
        "/usr/lib/ssl/certs",
        "/usr/ssl/certs",
    ]


def find_ca_bundle() -> Optional[str]:
    """
    Return path to a PEM CA bundle, or None.
    Order: env vars, static paths, OpenSSL OPENSSLDIR cert.pem, certifi.
    """
    for key in ("GIT_SSL_CAINFO", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
        v = os.environ.get(key)
        if v and _is_nonempty_file(Path(v)):
            return str(Path(v).resolve())

    for p in _static_bundle_candidates():
        path = Path(p)
        if _is_nonempty_file(path):
            return str(path.resolve())

    ossl_file, _ = _openssl_ca_paths()
    if ossl_file:
        return ossl_file

    try:
        import certifi

        p = Path(certifi.where())
        if _is_nonempty_file(p):
            return str(p.resolve())
    except ImportError:
        pass

    return None


def find_ca_capath() -> Optional[str]:
    """Return an OpenSSL-style CA directory (hashed .0 and/or many PEMs), or None."""
    for key in ("GIT_SSL_CAPATH", "SSL_CERT_DIR"):
        v = os.environ.get(key)
        if v:
            p = Path(v)
            if p.is_dir() and _dir_has_capath_material(p):
                return str(p.resolve())

    _, ossl_capath = _openssl_ca_paths()
    if ossl_capath:
        return ossl_capath

    for d in _static_capath_candidates():
        p = Path(d)
        if p.is_dir() and _dir_has_capath_material(p):
            return str(p.resolve())

    return None


def git_ssl_config_args() -> list:
    """
    Extra git global arguments: prefer CA file, else CA directory.
    Must appear immediately after 'git' and before the subcommand.
    """
    bundle = find_ca_bundle()
    if bundle:
        return ["-c", f"http.sslCAInfo={bundle}"]
    cap = find_ca_capath()
    if cap:
        return ["-c", f"http.sslCAPath={cap}"]
    return []


def git_subprocess_environ() -> dict:
    """
    Environment for git: set CA file when known; else SSL_CERT_DIR for capath.
    Does not override GIT_SSL_CAINFO if already set.
    """
    env = os.environ.copy()
    if env.get("GIT_SSL_CAINFO"):
        return env
    bundle = find_ca_bundle()
    if bundle:
        env["GIT_SSL_CAINFO"] = bundle
        env.setdefault("SSL_CERT_FILE", bundle)
        return env
    cap = find_ca_capath()
    if cap:
        env.setdefault("SSL_CERT_DIR", cap)
    return env


def ssl_failure_hint() -> str:
    return (
        "Git could not verify HTTPS (AUR). Sven tried common CA files and "
        "/etc/ssl/certs as a CA directory.\n"
        "Fix: install or regenerate system trust (e.g. run `update-ca-certificates` "
        "or your distro’s CA package), or set GIT_SSL_CAINFO to a PEM bundle, "
        "or SSL_CERT_DIR to a directory of trusted CAs."
    )


def augment_env_with_ssl_certs(env: dict) -> dict:
    """For curl/wget/makepkg: set SSL_CERT_FILE and/or SSL_CERT_DIR."""
    bundle = find_ca_bundle()
    cap = find_ca_capath()
    if bundle:
        env.setdefault("SSL_CERT_FILE", bundle)
        env.setdefault("GIT_SSL_CAINFO", bundle)
    elif cap:
        env.setdefault("SSL_CERT_DIR", cap)
    return env
