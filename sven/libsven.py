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
