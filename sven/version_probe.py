# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/version_probe.py — real version detection for adoption
#
#  Used by scripts/adopt_lfs.py and scripts/adopt_blfs.py to find
#  the ACTUAL installed version of a package on disk, instead of
#  writing a placeholder string into LocalDB.
#
#  Strategy, in order:
#    1. Curated map     — exact known-good command per package,
#                          for tools whose --version convention is
#                          irregular (openssl, e2fsprogs, less, ...)
#    2. Header/derived   — packages with no CLI at all but a real
#                          version encoded in a header or another
#                          package (zlib.h, linux/version.h, glibc
#                          via ldd, *-config helper scripts)
#    3. Generic fallback — `<bin> --version`, then `<bin> version`,
#                          then `pkg-config --modversion <name>`
#    4. Unknown          — no reliable source exists; caller must
#                          mark the package version_verified=False
#
#  Returns (version_str, verified: bool) from detect_version().
#  verified=False means "this is a placeholder, do not trust it
#  for version-constraint comparisons."
# ============================================================

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .ssl_bundle import clean_subprocess_env


_TIMEOUT = 5  # seconds — never let a probe hang the adoption run

# Generic "looks like a version" pattern: requires at least one dot,
# so we don't accidentally grab a bare copyright year like "2024".
_VER_RE = re.compile(r"\b(\d+\.\d+(?:\.\d+)*(?:[-_][a-zA-Z0-9]+)?)\b")

# Looser pattern for the handful of tools with single-integer versions
# (e.g. "less 643"). Only used by curated entries that opt into it.
_VER_RE_LOOSE = re.compile(r"\b(\d+(?:\.\d+)*)\b")


def _run(cmd: list[str]) -> str:
    """Run a command, return combined stdout+stderr text. Never raises."""
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
            env=clean_subprocess_env(os.environ.copy()),
        )
        return (r.stdout or "") + "\n" + (r.stderr or "")
    except (OSError, subprocess.SubprocessError):
        return ""


def _extract(text: str, pattern: re.Pattern = _VER_RE) -> Optional[str]:
    m = pattern.search(text)
    return m.group(1) if m else None


def _read_header_macro(header_path: str, macro: str) -> Optional[str]:
    """
    Read a #define MACRO "value" or #define MACRO value style line
    from a C header. Returns the raw value text, or None.
    """
    p = Path(header_path)
    if not p.exists():
        return None
    try:
        text = p.read_text(errors="ignore")
    except OSError:
        return None

    m = re.search(rf'#define\s+{re.escape(macro)}\s+"?([^"\n]+)"?', text)
    if m:
        return m.group(1).strip()
    return None


# ── Curated probes ───────────────────────────────────────────
# name -> callable returning version string or None.
# Only tools whose behavior is well-documented/standard are listed
# here; everything else goes through the generic fallback.

def _probe_bash():       return _extract(_run(["bash", "--version"]))
def _probe_coreutils():  return _extract(_run(["ls", "--version"]))
def _probe_make():       return _extract(_run(["make", "--version"]))
def _probe_patch():      return _extract(_run(["patch", "--version"]))
def _probe_m4():         return _extract(_run(["m4", "--version"]))
def _probe_gawk():       return _extract(_run(["gawk", "--version"]))
def _probe_grep():       return _extract(_run(["grep", "--version"]))
def _probe_sed():        return _extract(_run(["sed", "--version"]))
def _probe_findutils():  return _extract(_run(["find", "--version"]))
def _probe_tar():        return _extract(_run(["tar", "--version"]))
def _probe_gzip():       return _extract(_run(["gzip", "--version"]))
def _probe_bzip2():      return _extract(_run(["bzip2", "--version"]))
def _probe_xz():         return _extract(_run(["xz", "--version"]))
def _probe_zstd():       return _extract(_run(["zstd", "--version"]))
def _probe_curl():       return _extract(_run(["curl", "--version"]))
def _probe_wget():       return _extract(_run(["wget", "--version"]))
def _probe_gcc():        return _extract(_run(["gcc", "-dumpversion"])) or _extract(_run(["gcc", "--version"]))
def _probe_binutils():   return _extract(_run(["ld", "--version"]))
def _probe_perl():       return _extract(_run(["perl", "--version"]), re.compile(r"v(\d+\.\d+\.\d+)"))
def _probe_python():
    return _extract(_run(["python3", "--version"])) or _extract(_run(["python", "--version"]))

def _probe_util_linux():   return _extract(_run(["mount", "--version"]))
def _probe_procps_ng():    return _extract(_run(["ps", "--version"]))
def _probe_e2fsprogs():    return _extract(_run(["mke2fs", "-V"]))
def _probe_shadow():       return _extract(_run(["passwd", "--version"]))
def _probe_less():         return _extract(_run(["less", "--version"]), _VER_RE_LOOSE)
def _probe_openssl():      return _extract(_run(["openssl", "version"]))
def _probe_sqlite():       return _extract(_run(["sqlite3", "--version"]))
def _probe_pkgconf():      return _extract(_run(["pkgconf", "--version"])) or _extract(_run(["pkg-config", "--version"]), _VER_RE_LOOSE)

# Library-config helper scripts (the "correct" way to ask a library
# its own version, when one ships a *-config tool)
def _probe_pcre2():        return _extract(_run(["pcre2-config", "--version"]))
def _probe_libxml2():      return _extract(_run(["xml2-config", "--version"]))
def _probe_ncurses():
    v = _extract(_run(["ncursesw6-config", "--version"])) or _extract(_run(["ncurses6-config", "--version"]))
    if v:
        return v
    return _read_header_macro("/usr/include/ncurses.h", "NCURSES_VERSION")

# Header-only libraries — no CLI exists at all, version lives in a macro
def _probe_zlib():
    return _read_header_macro("/usr/include/zlib.h", "ZLIB_VERSION")

def _probe_readline():
    raw = _read_header_macro("/usr/include/readline/readline.h", "RL_READLINE_VERSION")
    if not raw:
        return None
    try:
        code = int(raw, 16) if raw.lower().startswith("0x") else int(raw)
        return f"{(code >> 8) & 0xFF}.{code & 0xFF}"
    except ValueError:
        return None

def _probe_libffi():
    return _pkgconfig_modversion("libffi")

def _probe_expat():
    return _pkgconfig_modversion("expat")

def _probe_libcap():
    return _pkgconfig_modversion("libcap")

# Special-cases: no version of their own, derived from / read from elsewhere
def _probe_glibc():
    return _extract(_run(["ldd", "--version"]))

def _probe_linux_api_headers():
    raw = _read_header_macro("/usr/include/linux/version.h", "LINUX_VERSION_CODE")
    if not raw:
        return None
    try:
        code = int(raw)
        major = (code >> 16) & 0xFF
        minor = (code >> 8) & 0xFF
        patch = code & 0xFF
        return f"{major}.{minor}.{patch}"
    except ValueError:
        return None


_CURATED: dict[str, "callable"] = {
    "bash":             _probe_bash,
    "coreutils":        _probe_coreutils,
    "make":             _probe_make,
    "patch":            _probe_patch,
    "m4":               _probe_m4,
    "gawk":             _probe_gawk,
    "grep":             _probe_grep,
    "sed":              _probe_sed,
    "findutils":        _probe_findutils,
    "tar":              _probe_tar,
    "gzip":             _probe_gzip,
    "bzip2":            _probe_bzip2,
    "xz":               _probe_xz,
    "zstd":             _probe_zstd,
    "curl":             _probe_curl,
    "wget":             _probe_wget,
    "gcc":              _probe_gcc,
    "binutils":         _probe_binutils,
    "perl":             _probe_perl,
    "python":           _probe_python,
    "util-linux":       _probe_util_linux,
    "procps-ng":        _probe_procps_ng,
    "e2fsprogs":        _probe_e2fsprogs,
    "shadow":           _probe_shadow,
    "less":             _probe_less,
    "openssl":          _probe_openssl,
    "sqlite":           _probe_sqlite,
    "pkgconf":          _probe_pkgconf,
    "pcre2":            _probe_pcre2,
    "libxml2":          _probe_libxml2,
    "ncurses":          _probe_ncurses,
    "zlib":             _probe_zlib,
    "readline":         _probe_readline,
    "libffi":           _probe_libffi,
    "expat":            _probe_expat,
    "libcap":           _probe_libcap,
    "glibc":            _probe_glibc,
    "linux-api-headers": _probe_linux_api_headers,
}

# Packages with genuinely no stable, discoverable version source on a
# manually-built LFS/BLFS system. Documented honestly rather than guessed.
# - filesystem:      pure directory-layout metadata, no upstream version at all
# - ca-certificates: a cert bundle; no standard embedded version marker
# - linux-firmware:  a data blob; no standard embedded version marker
_NO_VERSION_SOURCE = {"filesystem", "ca-certificates", "linux-firmware"}

# glibc-locales ships from the exact same source tree as glibc, so we
# derive its version from glibc rather than treating it as unknown.
_DERIVED_FROM = {"glibc-locales": "glibc"}


# ── pkg-config helper ────────────────────────────────────────

def _pkgconfig_modversion(pc_name: str) -> Optional[str]:
    if not shutil.which("pkg-config"):
        return None
    out = _run(["pkg-config", "--modversion", pc_name])
    v = out.strip().splitlines()[0].strip() if out.strip() else ""
    return v if re.match(r"^\d+(\.\d+)*", v) else None


# ── Generic fallback (anything not curated) ──────────────────

def _generic_probe(pkg_name: str) -> Optional[str]:
    binary = pkg_name if shutil.which(pkg_name) else None
    if binary:
        v = _extract(_run([binary, "--version"]))
        if v:
            return v
        v = _extract(_run([binary, "version"]))
        if v:
            return v
    return _pkgconfig_modversion(pkg_name)


# ── Public API ────────────────────────────────────────────────

def generic_probe(pkg_name: str) -> Optional[str]:
    """Public entry point for the generic --version / pkg-config fallback probe."""
    return _generic_probe(pkg_name)


def detect_version(pkg_name: str) -> tuple[str, bool]:
    """
    Try to find the real, comparable version of an installed package.

    Returns (version, verified):
        verified=True  — version came from a real, trustworthy source
        verified=False — no reliable source exists; version is a
                          placeholder and must not be used for
                          version-constraint comparisons
    """
    if pkg_name in _NO_VERSION_SOURCE:
        return "unknown", False

    if pkg_name in _DERIVED_FROM:
        base = _DERIVED_FROM[pkg_name]
        v, verified = detect_version(base)
        return (v, verified) if verified else ("unknown", False)

    probe = _CURATED.get(pkg_name)
    if probe:
        v = probe()
        if v:
            return v, True
        # Curated probe exists but failed at runtime (tool missing /
        # behaved unexpectedly) — fall through to generic as a backstop
        # before giving up.

    v = _generic_probe(pkg_name)
    if v:
        return v, True

    return "unknown", False


# Packages where the package name itself is not a runnable binary —
# map to a representative binary that the package is known to ship.
_REPRESENTATIVE_BINARY = {
    "coreutils":   "ls",
    "util-linux":  "mount",
    "procps-ng":   "ps",
    "e2fsprogs":   "mke2fs",
    "shadow":      "passwd",
    "findutils":   "find",
    "binutils":    "ld",
    "glibc":       "ldd",
    "python":      "python3",
}


def is_present(pkg_name: str) -> bool:
    """
    Best-effort check that a package is actually present on this system
    before adopting it — avoids registering phantom entries for things
    that aren't really installed.
    """
    rep_bin = _REPRESENTATIVE_BINARY.get(pkg_name, pkg_name)
    if shutil.which(rep_bin):
        return True
    if pkg_name == "python" and shutil.which("python"):
        return True
    if pkg_name in _NO_VERSION_SOURCE:
        # No binary by definition — presence is checked structurally instead.
        if pkg_name == "filesystem":
            return Path("/etc").is_dir() and Path("/usr").is_dir()
        if pkg_name == "ca-certificates":
            return Path("/etc/ssl/certs").exists() or Path("/etc/ssl/cert.pem").exists()
        if pkg_name == "linux-firmware":
            return Path("/usr/lib/firmware").is_dir()
        return False
    if pkg_name in _DERIVED_FROM:
        return is_present(_DERIVED_FROM[pkg_name])
    # Header-only libs: presence = the header/lib actually being there
    header_checks = {
        "zlib":     ["/usr/include/zlib.h"],
        "readline": ["/usr/include/readline/readline.h"],
        "linux-api-headers": ["/usr/include/linux/version.h"],
    }
    if pkg_name in header_checks:
        return any(Path(p).exists() for p in header_checks[pkg_name])
    # Last resort: pkg-config knows about it
    if shutil.which("pkg-config"):
        r = subprocess.run(
            ["pkg-config", "--exists", pkg_name],
            capture_output=True, timeout=_TIMEOUT,
            env=clean_subprocess_env(os.environ.copy()),
        )
        if r.returncode == 0:
            return True
    return False
