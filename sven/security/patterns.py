# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/security/patterns.py
# ============================================================
from typing import NamedTuple

class Pattern(NamedTuple):
    regex: str
    description: str
    severity: str
    recommendation: str

SAFE_PATTERNS = [
    r"exec\s+/[a-zA-Z0-9/_\-\.]+",  # exec fixed path
    r"[a-zA-Z0-9_]+=\(",              # array assignments like depends=(
    r"^[a-zA-Z0-9_]+="                # simple variable assignments
]

# Extensible — community can add patterns via PR
DANGEROUS_PATTERNS = [
    Pattern(r"\bcurl\b.*\|\s*(bash|sh)", "network call", "CRITICAL", "Avoid fetching binaries in hooks"),
    Pattern(r"\bwget\b.*\|\s*(bash|sh)", "network call", "CRITICAL", "Avoid fetching binaries in hooks"),
    Pattern(r"\bbash\s+-c", "code execution", "CRITICAL", "Audit shell execution heavily"),
    Pattern(r"\bsh\s+-c", "code execution", "CRITICAL", "Audit shell execution heavily"),
    Pattern(r"\beval\b", "code execution", "CRITICAL", "Avoid eval entirely"),
    Pattern(r"\bexec\b\s+(bash|\$|\`|\$\()", "code execution", "CRITICAL", "Dangerous exec usage"),
    Pattern(r"\bnc\b", "network utility", "WARNING", "Netcat in a hook is suspicious"),
    Pattern(r"\bncat\b", "network utility", "WARNING", "Netcat in a hook is suspicious"),
    Pattern(r"/dev/tcp", "network call", "CRITICAL", "Reverse shell indicator"),
    Pattern(r"base64\s+-d", "obfuscation", "WARNING", "Obfuscated payload indicator"),
    Pattern(r"\bpython\s+-c", "code execution", "CRITICAL", "Arbitrary python execution"),
    Pattern(r"\bperl\s+-e", "code execution", "CRITICAL", "Arbitrary perl execution"),
    Pattern(r"\bruby\s+-e", "code execution", "CRITICAL", "Arbitrary ruby execution"),
    Pattern(r"\bdd\s+if", "device bypass", "WARNING", "Suspicious disk read/write"),
    Pattern(r"\bmkfifo\b", "ipc manipulation", "WARNING", "Suspicious IPC creation"),
    Pattern(r"\brm\s+-rf\s+/", "destructive", "CRITICAL", "Destructive host deletion")
]
