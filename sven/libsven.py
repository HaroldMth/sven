import os
import ctypes

# ============================================================
#  Sven — Seven OS Package Manager
#  libsven.py — C Extension Interface
# ============================================================

_lib_path = os.path.join(os.path.dirname(__file__), "libsven_core.so")
try:
    _libsven = ctypes.CDLL(_lib_path)
    
    # int sven_vercmp(const char *a, const char *b)
    _libsven.sven_vercmp.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    _libsven.sven_vercmp.restype = ctypes.c_int
    
    # int sven_match_path(const char *pattern, const char **files, int num_files)
    _libsven.sven_match_path.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_char_p), ctypes.c_int]
    _libsven.sven_match_path.restype = ctypes.c_int
except OSError:
    _libsven = None

def vercmp(a: str, b: str) -> int:
    """
    Compare two package version strings using the blazing fast C implementation.
    Returns -1 if a < b, 0 if a == b, 1 if a > b.
    """
    if _libsven:
        return _libsven.sven_vercmp(a.encode('utf-8'), b.encode('utf-8'))
    
    # Fallback to Python if the C library is somehow missing
    import re
    parts_a = re.split(r'[^a-zA-Z0-9]+', a)
    parts_b = re.split(r'[^a-zA-Z0-9]+', b)
    
    for p1, p2 in zip(parts_a, parts_b):
        if p1.isdigit() and p2.isdigit():
            n1, n2 = int(p1), int(p2)
            if n1 < n2: return -1
            if n1 > n2: return 1
        else:
            if p1 < p2: return -1
            if p1 > p2: return 1
            
    if len(parts_a) < len(parts_b): return -1
    if len(parts_a) > len(parts_b): return 1
    return 0


def match_path(pattern: str, files: list[str]) -> bool:
    """
    Check if any file in 'files' matches 'pattern' using the fast C engine.
    """
    if not files:
        return False
        
    if _libsven:
        # Convert list of python strings to ctypes array of char pointers
        c_pattern = pattern.encode('utf-8')
        c_files_array = (ctypes.c_char_p * len(files))()
        c_files_array[:] = [f.encode('utf-8') for f in files]
        
        return bool(_libsven.sven_match_path(c_pattern, c_files_array, len(files)))
        
    # Fallback to python fnmatch
    import fnmatch
    for f in files:
        file_path = f.lstrip('/')
        if fnmatch.fnmatch(file_path, pattern):
            return True
    return False
