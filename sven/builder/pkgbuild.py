# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  builder/pkgbuild.py — PKGBUILD parser
# ============================================================
#
#  Parses Arch Linux PKGBUILD bash files into a structured
#  PKGBuild dataclass. Handles arrays, quoted strings, and
#  detects -git packages.
# ============================================================

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..exceptions import PKGBUILDError


@dataclass
class PKGBuild:
    """Parsed representation of a PKGBUILD file."""
    pkgname:      str            = ""
    pkgver:       str            = ""
    pkgrel:       str            = ""
    pkgdesc:      str            = ""
    depends:      list[str]      = field(default_factory=list)
    makedepends:  list[str]      = field(default_factory=list)
    optdepends:   list[str]      = field(default_factory=list)
    conflicts:    list[str]      = field(default_factory=list)
    provides:     list[str]      = field(default_factory=list)
    source:       list[str]      = field(default_factory=list)
    sha256sums:   list[str]      = field(default_factory=list)
    install:      str            = ""         # .install hook file name
    is_git:       bool           = False      # -git package

    @property
    def full_version(self) -> str:
        return f"{self.pkgver}-{self.pkgrel}" if self.pkgrel else self.pkgver


# ── Regex patterns for PKGBUILD fields ──────────────────────

# Matches: varname=value  or  varname="value"  or  varname='value'
_SCALAR_RE = re.compile(
    r"""^(\w+)=(?:"([^"]*)"|'([^']*)'|(\S*))""",
    re.MULTILINE,
)

# Matches: varname=(item1 item2 item3 ...)
# Handles multi-line arrays with parentheses
_ARRAY_START_RE = re.compile(r"^(\w+)=\(", re.MULTILINE)


def parse_pkgbuild(filepath: str) -> PKGBuild:
    """
    Parse a PKGBUILD file and return a PKGBuild dataclass.

    Extracts scalar variables and bash arrays.
    Detects -git packages based on pkgname suffix or VCS version patterns.

    Args:
        filepath: Path to the PKGBUILD file

    Returns:
        PKGBuild dataclass

    Raises:
        PKGBUILDError if the file cannot be read or pkgname is missing
    """
    path = Path(filepath)
    if not path.exists():
        raise PKGBUILDError(filepath)

    try:
        content = path.read_text(errors="replace")
    except OSError:
        raise PKGBUILDError(filepath)

    # Strip comments (but not inside quotes — good enough for PKGBUILDs)
    lines = content.splitlines()
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # Remove inline comments (naive — works for 99% of PKGBUILDs)
        if " #" in line and not (line.count('"') % 2 or line.count("'") % 2):
            line = line[:line.index(" #")]
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)

    # ── Extract scalars ──
    scalars = {}
    for m in _SCALAR_RE.finditer(cleaned):
        name = m.group(1)
        value = m.group(2) or m.group(3) or m.group(4) or ""
        scalars[name] = value

    # ── Extract arrays ──
    arrays = _extract_arrays(cleaned)

    # ── Build the dataclass ──
    pkg = PKGBuild()

    # Scalars
    pkg.pkgname = scalars.get("pkgname", "")
    pkg.pkgver  = scalars.get("pkgver", "")
    pkg.pkgrel  = scalars.get("pkgrel", "")
    pkg.pkgdesc = scalars.get("pkgdesc", "")
    pkg.install = scalars.get("install", "")

    # If pkgname was defined as an array (split packages), take the first
    if not pkg.pkgname and "pkgname" in arrays:
        names = arrays["pkgname"]
        pkg.pkgname = names[0] if names else ""

    # Arrays
    pkg.depends     = arrays.get("depends", [])
    pkg.makedepends = arrays.get("makedepends", [])
    pkg.optdepends  = arrays.get("optdepends", [])
    pkg.conflicts   = arrays.get("conflicts", [])
    pkg.provides    = arrays.get("provides", [])
    pkg.source      = arrays.get("source", [])
    pkg.sha256sums  = arrays.get("sha256sums", [])

    # ── Validate ──
    if not pkg.pkgname:
        raise PKGBUILDError(filepath)

    # ── Detect -git packages ──
    pkg.is_git = _detect_git_package(pkg)

    return pkg


def _extract_arrays(content: str) -> dict[str, list[str]]:
    """
    Extract bash array assignments from PKGBUILD content.
    Handles multi-line arrays with parentheses.
    """
    arrays = {}

    for m in _ARRAY_START_RE.finditer(content):
        name = m.group(1)
        start = m.end()

        # Find the closing parenthesis
        depth = 1
        pos = start
        while pos < len(content) and depth > 0:
            ch = content[pos]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            pos += 1

        if depth != 0:
            continue

        body = content[start:pos - 1]
        items = _parse_array_body(body)
        arrays[name] = items

    return arrays


def _parse_array_body(body: str) -> list[str]:
    """
    Parse the body of a bash array (between parentheses).
    Handles single-quoted, double-quoted, and unquoted items.
    """
    items = []
    i = 0
    body = body.strip()

    while i < len(body):
        ch = body[i]

        # Skip whitespace and newlines
        if ch in (" ", "\t", "\n", "\r"):
            i += 1
            continue

        # Single-quoted string
        if ch == "'":
            end = body.index("'", i + 1) if "'" in body[i + 1:] else len(body)
            items.append(body[i + 1:end])
            i = end + 1
            continue

        # Double-quoted string
        if ch == '"':
            end = body.index('"', i + 1) if '"' in body[i + 1:] else len(body)
            items.append(body[i + 1:end])
            i = end + 1
            continue

        # Unquoted word
        end = i
        while end < len(body) and body[end] not in (" ", "\t", "\n", "\r", ")", "'", '"'):
            end += 1
        word = body[i:end]
        if word and not word.startswith("#"):
            items.append(word)
        elif word and word.startswith("#"):
            # Rest of this line is a comment, skip to next line
            nl = body.find("\n", end)
            i = nl + 1 if nl != -1 else len(body)
            continue
        i = end

    return items


def _detect_git_package(pkg: PKGBuild) -> bool:
    r"""
    Detect if this is a VCS (-git) package.
    Checks:
      1. pkgname ends with -git
      2. Version pattern matches .r\d+.g[a-f0-9]+ (VCS version)
      3. Source contains a git+http URL
    """
    if pkg.pkgname.endswith("-git"):
        return True

    # VCS version pattern: e.g. 1.0.r123.gabcdef
    if re.search(r"\.r\d+\.g[a-f0-9]+", pkg.pkgver):
        return True

    # Git source URL
    for src in pkg.source:
        if src.startswith("git+") or src.startswith("git://"):
            return True

    return False
