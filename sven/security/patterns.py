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

# Extensible — community can add patterns via PR
DANGEROUS_PATTERNS = [
    Pattern("curl", "network call", "CRITICAL", "Avoid fetching binaries in hooks"),
    Pattern("wget", "network call", "CRITICAL", "Avoid fetching binaries in hooks"),
    Pattern("bash -c", "code execution", "CRITICAL", "Audit shell execution heavily"),
    Pattern("sh -c", "code execution", "CRITICAL", "Audit shell execution heavily"),
    Pattern("eval", "code execution", "CRITICAL", "Avoid eval entirely"),
    Pattern("exec", "code execution", "CRITICAL", "Avoid exec entirely"),
    Pattern("nc", "network utility", "WARNING", "Netcat in a hook is suspicious"),
    Pattern("ncat", "network utility", "WARNING", "Netcat in a hook is suspicious"),
    Pattern("/dev/tcp", "network call", "CRITICAL", "Reverse shell indicator"),
    Pattern("base64 -d", "obfuscation", "WARNING", "Obfuscated payload indicator"),
    Pattern("python -c", "code execution", "CRITICAL", "Arbitrary python execution"),
    Pattern("perl -e", "code execution", "CRITICAL", "Arbitrary perl execution"),
    Pattern("ruby -e", "code execution", "CRITICAL", "Arbitrary ruby execution"),
    Pattern("dd if", "device bypass", "WARNING", "Suspicious disk read/write"),
    Pattern("mkfifo", "ipc manipulation", "WARNING", "Suspicious IPC creation"),
    Pattern("rm -rf /", "destructive", "CRITICAL", "Destructive host deletion")
]
