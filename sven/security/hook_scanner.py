# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/security/hook_scanner.py
# ============================================================
import re
from pathlib import Path
from typing import NamedTuple
from .patterns import DANGEROUS_PATTERNS, SAFE_PATTERNS

class Finding(NamedTuple):
    line_number: int
    line_content: str
    pattern_matched: str
    severity: str

class ScanResult(NamedTuple):
    safe: bool
    findings: list[Finding]

def scan_file(filepath: str) -> list[Finding]:
    findings = []
    path = Path(filepath)

    if not path.exists() or not path.is_file():
        return findings

    try:
        content = path.read_text(errors="replace")
    except OSError:
        return findings

    for line_no, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        is_safe = False
        for sp in SAFE_PATTERNS:
            if re.search(sp, stripped):
                is_safe = True
                break

        if is_safe:
            continue

        for p in DANGEROUS_PATTERNS:
            if re.search(p.regex, stripped):
                findings.append(Finding(
                    line_number=line_no,
                    line_content=stripped[:120],
                    pattern_matched=p.regex,
                    severity=p.severity
                ))


    return findings

def scan_pkgbuild_dir(pkg_dir: str) -> ScanResult:
    dirpath = Path(pkg_dir)
    all_findings = []

    targets = []
    pkgbuild = dirpath / "PKGBUILD"
    if pkgbuild.exists():
        targets.append(pkgbuild)

    for f in dirpath.glob("*.install"):
        targets.append(f)

    for f in dirpath.glob("*.sh"):
        targets.append(f)

    for target in targets:
        all_findings.extend(scan_file(str(target)))

    return ScanResult(
        safe=len(all_findings) == 0,
        findings=all_findings
    )

def prompt_hook_approval(pkg_name: str, result: ScanResult) -> str:
    """
    Shows findings exactly referencing mockup and prompts for action.
    Returns "R" (Run anyway), "S" (Skip), or "A" (Abort)
    """
    if result.safe:
        return "R"
        
    print("\n\033[93m⚠  AUR package — security scan results:\033[0m")
    print(f"   Package: {pkg_name} [AUR]\n")
    print("   Findings:")
    
    for f in result.findings:
        # Resolve pattern
        pattern_dict = {p.regex: p for p in DANGEROUS_PATTERNS}
        desc = pattern_dict.get(f.pattern_matched).description if f.pattern_matched in pattern_dict else ""
        print(f"   → Line {f.line_number}: {f.line_content}  [{f.severity} - {desc}]")
        
    print("\n   Sven strongly recommends rejecting these hooks.\n")
    
    while True:
        try:
            print("   [S] Skip hooks  [A] Abort install  [R] Run anyway")
            # CRITICAL findings → default to SKIP, user must type YES to override
            # Actually, per prompt "user must type YES to override", wait, the options are [S/A/R]
            reply = input("   Choice: ").strip().upper()
            if reply in ("S", "A"):
                return reply
            elif reply == "R":
                has_critical = any(f.severity == "CRITICAL" for f in result.findings)
                if has_critical:
                    override = input("   CRITICAL findings detected. Type YES to run anyway: ").strip()
                    if override == "YES":
                        return "R"
                else:
                    return "R"
        except (EOFError, KeyboardInterrupt):
            return "A"
