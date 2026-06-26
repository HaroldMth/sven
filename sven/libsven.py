# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  libsven.py — C Extension Interface
#
#  Exposes all libsven_core.so functions to Python via ctypes.
#  Functions fall back to pure Python if the .so is missing.
# ============================================================

import os
import ctypes
import fnmatch

_lib_path = os.path.join(os.path.dirname(__file__), "libsven_core.so")
try:
    _lib = ctypes.CDLL(_lib_path)

    # ── vercmp ────────────────────────────────────────────────
    _lib.sven_vercmp.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    _lib.sven_vercmp.restype  = ctypes.c_int

    # ── hooks ─────────────────────────────────────────────────
    _lib.sven_match_path.argtypes = [
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_char_p),
        ctypes.c_int,
    ]
    _lib.sven_match_path.restype = ctypes.c_int

    # ── resolver ──────────────────────────────────────────────
    _lib.sven_parse_dep.argtypes = [
        ctypes.c_char_p,
        ctypes.c_char_p, ctypes.c_size_t,
        ctypes.c_char_p, ctypes.c_size_t,
        ctypes.c_char_p, ctypes.c_size_t,
    ]
    _lib.sven_parse_dep.restype = ctypes.c_int

    _lib.sven_strip_constraint.argtypes = [
        ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t,
    ]
    _lib.sven_strip_constraint.restype = ctypes.c_char_p

    _lib.sven_dep_satisfied.argtypes = [
        ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p,
    ]
    _lib.sven_dep_satisfied.restype = ctypes.c_int

    # ── filter ────────────────────────────────────────────────
    _lib.sven_classify_systemd_dep.argtypes = [ctypes.c_char_p]
    _lib.sven_classify_systemd_dep.restype  = ctypes.c_int

    _lib.sven_filter_systemd_deps.argtypes = [
        ctypes.POINTER(ctypes.c_char_p), ctypes.c_int,
        ctypes.POINTER(ctypes.c_int),    ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),    ctypes.POINTER(ctypes.c_int),
    ]
    _lib.sven_filter_systemd_deps.restype = ctypes.c_int

    # ── graph (topo sort) ─────────────────────────────────────
    _lib.sven_topo_sort.argtypes = [
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
    ]
    _lib.sven_topo_sort.restype = ctypes.c_int

    # ── extractor (requires libarchive — optional) ────────────
    try:
        _lib.sven_extract_zst.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_char_p),
            ctypes.c_int,
        ]
        _lib.sven_extract_zst.restype = ctypes.c_int

        _lib.sven_free_file_list.argtypes = [
            ctypes.POINTER(ctypes.c_char_p), ctypes.c_int,
        ]
        _lib.sven_free_file_list.restype = None
        _HAS_EXTRACTOR = True
    except AttributeError:
        _HAS_EXTRACTOR = False

    # ── checksum ──────────────────────────────────────────────
    _lib.sven_sha256_file.argtypes = [
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_size_t,
    ]
    _lib.sven_sha256_file.restype = ctypes.c_int

    _lib.sven_verify_checksum.argtypes = [
        ctypes.c_char_p,
        ctypes.c_char_p,
    ]
    _lib.sven_verify_checksum.restype = ctypes.c_int

    # ── conflicts (opaque pointer ctx) ────────────────────────
    _lib.sven_conflict_new.argtypes  = [ctypes.c_int]
    _lib.sven_conflict_new.restype   = ctypes.c_void_p

    _lib.sven_conflict_free.argtypes = [ctypes.c_void_p]
    _lib.sven_conflict_free.restype  = None

    _lib.sven_conflict_add.argtypes  = [
        ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p,
    ]
    _lib.sven_conflict_add.restype   = ctypes.c_int

    _lib.sven_conflict_owner.argtypes = [
        ctypes.c_void_p, ctypes.c_char_p,
    ]
    _lib.sven_conflict_owner.restype  = ctypes.c_char_p

    _lib.sven_conflict_check.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_char_p), ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_char_p, ctypes.c_size_t,
        ctypes.c_char_p, ctypes.c_size_t,
    ]
    _lib.sven_conflict_check.restype  = ctypes.c_int

    # ── pacnew / pacsave ──────────────────────────────────────
    _lib.sven_is_config_path.argtypes = [ctypes.c_char_p]
    _lib.sven_is_config_path.restype  = ctypes.c_int

    _lib.sven_needs_pacnew.argtypes   = [ctypes.c_char_p, ctypes.c_char_p]
    _lib.sven_needs_pacnew.restype    = ctypes.c_int

    _lib.sven_save_pacnew.argtypes    = [ctypes.c_char_p, ctypes.c_char_p]
    _lib.sven_save_pacnew.restype     = ctypes.c_int

    _lib.sven_save_pacsave.argtypes   = [ctypes.c_char_p]
    _lib.sven_save_pacsave.restype    = ctypes.c_int

except OSError:
    _lib = None
    _HAS_EXTRACTOR = False

_BUF = 512  # default string buffer size for C calls


# ══════════════════════════════════════════════════════════════
#  Public API
# ══════════════════════════════════════════════════════════════

# ── vercmp ────────────────────────────────────────────────────

def vercmp(a: str, b: str) -> int:
    """Compare two Arch package version strings. Returns -1/0/1."""
    if _lib:
        return _lib.sven_vercmp(a.encode(), b.encode())
    # Python fallback
    import re
    pa = re.split(r'[^a-zA-Z0-9]+', a)
    pb = re.split(r'[^a-zA-Z0-9]+', b)
    for p1, p2 in zip(pa, pb):
        if p1.isdigit() and p2.isdigit():
            n1, n2 = int(p1), int(p2)
            if n1 != n2: return -1 if n1 < n2 else 1
        else:
            if p1 < p2: return -1
            if p1 > p2: return 1
    if len(pa) < len(pb): return -1
    if len(pa) > len(pb): return 1
    return 0


# ── match_path ────────────────────────────────────────────────

def match_path(pattern: str, files: list[str]) -> bool:
    """Check if any file matches pattern using C fnmatch engine."""
    if not files:
        return False
    if _lib:
        c_pattern = pattern.encode()
        c_arr = (ctypes.c_char_p * len(files))(*[f.encode() for f in files])
        return bool(_lib.sven_match_path(c_pattern, c_arr, len(files)))
    for f in files:
        if fnmatch.fnmatch(f.lstrip('/'), pattern):
            return True
    return False


# ── parse_dep ─────────────────────────────────────────────────

def parse_dep(dep_str: str) -> tuple[str, str | None, str | None]:
    """
    Parse "bash>=5.0" → ("bash", ">=", "5.0").
    Returns (name, None, None) when there is no version constraint.
    """
    if _lib:
        name_buf = ctypes.create_string_buffer(_BUF)
        op_buf   = ctypes.create_string_buffer(8)
        ver_buf  = ctypes.create_string_buffer(_BUF)
        r = _lib.sven_parse_dep(
            dep_str.encode(),
            name_buf, _BUF,
            op_buf,   8,
            ver_buf,  _BUF,
        )
        if r == 0:
            name = name_buf.value.decode()
            op   = op_buf.value.decode()   or None
            ver  = ver_buf.value.decode()  or None
            return name, op, ver
    # Python fallback
    import re
    m = re.match(r'^([^<>=]+)([<>=]+)(.+)$', dep_str)
    if m:
        return m.group(1), m.group(2), m.group(3)
    return dep_str, None, None


# ── strip_constraint ──────────────────────────────────────────

def strip_constraint(dep_str: str) -> str:
    """
    Strip version constraint from a dep string.
    "bash>=5.0" → "bash",  "openssl" → "openssl"
    """
    if _lib:
        buf = ctypes.create_string_buffer(_BUF)
        result = _lib.sven_strip_constraint(dep_str.encode(), buf, _BUF)
        if result:
            return buf.value.decode()
    # Python fallback
    for sep in ('>=', '<=', '>', '<', '='):
        if sep in dep_str:
            return dep_str.split(sep)[0].strip()
    return dep_str.strip()


# ── dep_satisfied ─────────────────────────────────────────────

def dep_satisfied(installed_ver: str, op: str, req_ver: str) -> bool:
    """
    Check whether installed_ver satisfies the constraint op+req_ver.
    E.g. dep_satisfied("5.2", ">=", "5.0") → True
    """
    # If the required constraint has no pkgrel component (no '-'), but the candidate
    # version does, strip the pkgrel component for comparison — but ONLY when the
    # pkgver portion (before the last '-') exactly equals req_ver. This prevents false
    # matches for constraints like glibc=2.43+r22+g8362e8 when installed is 2.43-1.
    if "-" not in req_ver and "-" in installed_ver:
        pkgver = installed_ver.rsplit("-", 1)[0]
        if pkgver == req_ver:
            installed_ver = pkgver

    if _lib:
        r = _lib.sven_dep_satisfied(
            installed_ver.encode(), op.encode(), req_ver.encode()
        )
        if r >= 0:
            return bool(r)
    # Python fallback
    cmp = vercmp(installed_ver, req_ver)
    if op == '>=': return cmp >= 0
    if op == '<=': return cmp <= 0
    if op == '>':  return cmp >  0
    if op == '<':  return cmp <  0
    if op in ('=', '=='): return cmp == 0
    return False


# ── classify_systemd_dep ──────────────────────────────────────

def classify_systemd_dep(dep_name: str) -> int:
    """
    Classify a stripped dep name against known systemd packages.
    Returns: 0=none, 1=hard dep, 2=soft dep
    """
    if _lib:
        return _lib.sven_classify_systemd_dep(dep_name.encode())
    # Python fallback
    HARD = {
        "systemd", "systemd-libs", "systemd-sysvcompat",
        "systemd-resolvconf", "systemd-ukify",
    }
    SOFT = {"systemd-service", "systemctl"}
    if dep_name in HARD: return 1
    if dep_name in SOFT: return 2
    if dep_name.startswith("libsystemd") or dep_name.startswith("libudev"):
        return 1
    return 0


# ── topo_sort ─────────────────────────────────────────────────

def topo_sort(
    names: list[str],
    edges: dict[str, set[str]],
) -> tuple[list[str], list[str]]:
    """
    Topologically sort packages for install order.

    Parameters:
        names : list of all package names (establishes index mapping)
        edges : {pkg_name: set_of_dep_names}

    Returns:
        (sorted_names, cycle_names)
        sorted_names — install order (deps before dependents)
        cycle_names  — packages involved in cycles (if any)
    """
    if not names:
        return [], []

    n = len(names)
    idx = {name: i for i, name in enumerate(names)}

    if _lib:
        # Build flat adjacency arrays
        flat_adj = []
        adj_idx  = []
        adj_cnt  = []

        for name in names:
            deps = edges.get(name, set())
            valid_deps = [idx[d] for d in deps if d in idx]
            adj_idx.append(len(flat_adj))
            adj_cnt.append(len(valid_deps))
            flat_adj.extend(valid_deps)

        total_edges = len(flat_adj)
        c_adj     = (ctypes.c_int * max(total_edges, 1))(*flat_adj)
        c_adj_idx = (ctypes.c_int * n)(*adj_idx)
        c_adj_cnt = (ctypes.c_int * n)(*adj_cnt)
        c_order   = (ctypes.c_int * n)()
        c_cycles  = (ctypes.c_int * n)()
        n_cycles  = ctypes.c_int(0)

        count = _lib.sven_topo_sort(
            n, c_adj, c_adj_idx, c_adj_cnt,
            c_order, c_cycles, ctypes.byref(n_cycles),
        )

        if count >= 0:
            sorted_names = [names[c_order[i]] for i in range(count)]
            cycle_names  = [names[c_cycles[i]] for i in range(n_cycles.value)]
            return sorted_names, cycle_names

    # Python fallback (same DFS as original sorter.py)
    order = []
    visited: set[str] = set()
    temp: set[str]    = set()
    cycles: list[str] = []

    def visit(name: str):
        if name in temp:
            if name not in cycles:
                cycles.append(name)
            return
        if name in visited:
            return
        temp.add(name)
        for dep in sorted(edges.get(name, set())):
            visit(dep)
        temp.discard(name)
        visited.add(name)
        order.append(name)

    for name in sorted(names):
        visit(name)

    return order, cycles


# ── extract_zst ───────────────────────────────────────────────

_MAX_FILES_PER_PKG = 65536  # generous upper bound

def extract_zst(archive_path: str, root_path: str) -> list[str]:
    """
    Extract a .pkg.tar.zst archive to root_path using the C libarchive engine.
    Returns list of absolute paths of extracted files (not dirs).
    Falls back to Python zstandard+tarfile if libarchive not compiled in.
    """
    if _lib and _HAS_EXTRACTOR:
        c_files = (ctypes.c_char_p * _MAX_FILES_PER_PKG)()
        count = _lib.sven_extract_zst(
            archive_path.encode(),
            root_path.encode(),
            c_files,
            _MAX_FILES_PER_PKG,
        )
        if count < 0:
            raise RuntimeError(f"sven_extract_zst failed for {archive_path}")
        result = [c_files[i].decode() for i in range(count)]
        _lib.sven_free_file_list(c_files, count)
        return result

    # Python fallback (original extractor logic)
    import tarfile
    try:
        import zstandard as zstd
    except ImportError:
        raise RuntimeError("zstandard module required for Python extraction fallback")

    from pathlib import Path
    META = {".PKGINFO", ".MTREE", ".INSTALL", ".BUILDINFO"}
    root = Path(root_path)
    extracted = []

    with open(archive_path, "rb") as f_in:
        dctx = zstd.ZstdDecompressor()
        with dctx.stream_reader(f_in) as zstream:
            with tarfile.open(fileobj=zstream, mode="r|") as tar:
                for member in tar:
                    if member.name in META:
                        continue
                    dest = root / member.name
                    if member.isdir():
                        dest.mkdir(parents=True, exist_ok=True)
                        continue
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if member.isreg():
                        try:
                            dest.unlink(missing_ok=True)
                        except OSError:
                            pass
                        with tar.extractfile(member) as src, open(dest, "wb") as dst:
                            dst.write(src.read())
                        import os
                        os.chmod(dest, member.mode)
                        extracted.append(str(dest))
                    elif member.issym():
                        if dest.exists() or dest.is_symlink():
                            dest.unlink()
                        dest.symlink_to(member.linkname)
                        extracted.append(str(dest))
    return extracted


# ── sha256_file ───────────────────────────────────────────────

def sha256_file(path: str) -> str:
    """Compute the SHA-256 hex digest of a file. Returns lowercase hex digest string."""
    if _lib:
        buf = ctypes.create_string_buffer(65)
        if _lib.sven_sha256_file(path.encode(), buf, 65) == 0:
            return buf.value.decode()
    # Python fallback
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


# ── verify_checksum ───────────────────────────────────────────

def verify_checksum(path: str, expected_hex: str) -> bool:
    """Verify a file's SHA-256 against expected_hex. Returns True on match, False on mismatch/error."""
    if _lib:
        res = _lib.sven_verify_checksum(path.encode(), expected_hex.encode())
        return res == 1
    # Python fallback
    try:
        actual = sha256_file(path)
        return actual.lower() == expected_hex.lower()
    except Exception:
        return False


# ── ConflictContext ───────────────────────────────────────────

class ConflictContext:
    """Opaque context representing the fast conflict detection hash map in C."""
    def __init__(self, capacity: int = 1024):
        self._ctx = None
        if _lib:
            self._ctx = _lib.sven_conflict_new(capacity)
        self._fallback_map = {}

    def add(self, filepath: str, owner_pkg: str):
        filepath = filepath.lstrip('/')
        if self._ctx:
            _lib.sven_conflict_add(self._ctx, filepath.encode(), owner_pkg.encode())
        else:
            self._fallback_map[filepath] = owner_pkg

    def owner(self, filepath: str) -> str | None:
        filepath = filepath.lstrip('/')
        if self._ctx:
            res = _lib.sven_conflict_owner(self._ctx, filepath.encode())
            if res:
                return res.decode()
            return None
        else:
            return self._fallback_map.get(filepath)

    def check(self, new_files: list[str], installing_pkg: str) -> tuple[str, str] | None:
        """
        Check a list of files against the registered owners.
        Returns (conflicting_file, owner_pkg) or None.
        """
        cleaned_files = [f.lstrip('/') for f in new_files]
        if self._ctx:
            if not cleaned_files:
                return None
            c_arr = (ctypes.c_char_p * len(cleaned_files))(*[f.encode() for f in cleaned_files])
            file_buf = ctypes.create_string_buffer(1024)
            owner_buf = ctypes.create_string_buffer(256)
            res = _lib.sven_conflict_check(
                self._ctx,
                c_arr, len(cleaned_files),
                installing_pkg.encode(),
                file_buf, 1024,
                owner_buf, 256,
            )
            if res == 1:
                return file_buf.value.decode(), owner_buf.value.decode()
            return None
        else:
            for f in cleaned_files:
                owner = self._fallback_map.get(f)
                if owner and owner != installing_pkg:
                    return f, owner
            return None

    def __del__(self):
        if self._ctx and _lib:
            try:
                _lib.sven_conflict_free(self._ctx)
            except AttributeError:
                pass
            self._ctx = None


# ── pacnew / pacsave ─────────────────────────────────────────

def is_config_path(path: str) -> bool:
    """Returns True if path looks like a user-editable config file (under /etc/)."""
    if _lib:
        return bool(_lib.sven_is_config_path(path.encode()))
    # Python fallback
    if not path.startswith('/etc/'):
        return False
    if path.endswith('/'):
        return False
    if any(path.endswith(ext) for ext in ('.so', '.a', '.pyc')):
        return False
    return True


def needs_pacnew(dest_path: str, src_sha256: str) -> bool:
    """Returns True if dest_path exists and its SHA-256 differs from src_sha256."""
    if _lib:
        res = _lib.sven_needs_pacnew(dest_path.encode(), src_sha256.encode() if src_sha256 else None)
        return res == 1
    # Python fallback
    import os
    if not os.path.exists(dest_path) or os.path.isdir(dest_path):
        return False
    if not src_sha256 or len(src_sha256) != 64:
        return True
    try:
        existing = sha256_file(dest_path)
        return existing.lower() != src_sha256.lower()
    except Exception:
        return True


def save_pacnew(src_path: str, dest_path: str) -> bool:
    """Copy src_path to dest_path.pacnew."""
    if _lib:
        return _lib.sven_save_pacnew(src_path.encode(), dest_path.encode()) == 0
    # Python fallback
    import shutil
    try:
        shutil.copy2(src_path, dest_path + '.pacnew')
        return True
    except Exception:
        return False


def save_pacsave(path: str) -> bool:
    """Copy path to path.pacsave."""
    if _lib:
        return _lib.sven_save_pacsave(path.encode()) == 0
    # Python fallback
    import os
    import shutil
    if not os.path.exists(path) or os.path.isdir(path):
        return True
    try:
        shutil.copy2(path, path + '.pacsave')
        return True
    except Exception:
        return False
