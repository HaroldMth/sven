# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  resolver/systemd_filter.py — systemd dependency filtering
# ============================================================
#
#  Seven OS uses SysVinit. Many Arch packages depend on systemd
#  components. This module classifies those dependencies and
#  blocks hard systemd requirements while allowing soft ones.
# ============================================================

from typing import NamedTuple
from pathlib import Path

from ..db.models import Package
from ..exceptions import SystemdDependencyError
from ..libsven import strip_constraint, classify_systemd_dep, dep_satisfied


class SystemdCheckResult(NamedTuple):
    safe: bool
    hard_deps: list[str]
    soft_deps: list[str]
    alternatives: dict[str, str]
    source_build_advised: bool


SYSTEMD_ALTERNATIVES = {
    "systemd-libs":       "elogind",
    "libsystemd":         "elogind",
    "libsystemd.so":      "elogind",
    "libsystemd.so=0-64": "elogind",
    "libudev.so":         "eudev",
    "systemd":            None,
}


def check_systemd_deps(pkg: Package, init_system: str = "sysvinit") -> SystemdCheckResult:
    """
    Check if a package has dependencies on systemd components.

    On SysVinit/OpenRC systems, hard systemd deps mean the package
    won't function correctly. Soft deps (like .service files) are fine.

    Args:
        pkg: The package to check
        init_system: Current init system (sysvinit, openrc, systemd)

    Returns:
        SystemdCheckResult with classification
    """
    # Normalize init_system input so variants like "SystemD", "systemd-linux",
    # or "systemd os" are treated as systemd-capable environments.
    normalized_init = (init_system or "").strip().lower()

    runtime_systemd = Path("/run/systemd/private").exists()

    # If we're on systemd (configured or detected), everything is fine
    if runtime_systemd or normalized_init == "systemd" or normalized_init.startswith("systemd-") or normalized_init.startswith("systemd "):
        return SystemdCheckResult(
            safe=True, hard_deps=[], soft_deps=[],
            alternatives={}, source_build_advised=False,
        )

    all_deps = pkg.deps
    hard_deps = []
    soft_deps = []
    alternatives = {}

    for dep in all_deps:
        dep_name = strip_constraint(dep)

        cls = classify_systemd_dep(dep_name)

        if cls == 1:
            if pkg.name == "pacman" and dep_name == "systemd":
                continue
            hard_deps.append(dep_name)
            alt = SYSTEMD_ALTERNATIVES.get(dep_name)
            if alt:
                alternatives[dep_name] = alt
        elif cls == 2:
            soft_deps.append(dep_name)

    # Hard systemd deps are not safe on non-systemd init systems.
    # Alternatives are advisory (possible manual replacement), not automatic compatibility.
    safe = len(hard_deps) == 0
    source_advised = len(hard_deps) > 0 and len(alternatives) < len(hard_deps)

    return SystemdCheckResult(
        safe=safe,
        hard_deps=hard_deps,
        soft_deps=soft_deps,
        alternatives=alternatives,
        source_build_advised=source_advised,
    )


def filter_systemd_packages(
    packages: list[Package],
    init_system: str = "sysvinit",
    strict: bool = True,
) -> tuple[list[Package], list[dict]]:
    """
    Filter a list of packages, removing those with hard systemd deps.

    Args:
        packages: List of packages to filter
        init_system: Current init system
        strict: If True, raise SystemdDependencyError on hard deps.
                If False, just warn and exclude.

    Returns:
        (safe_packages, warnings)
        where warnings is a list of dicts with package info
    """
    safe = []
    warnings = []

    for pkg in packages:
        result = check_systemd_deps(pkg, init_system)

        if result.safe:
            safe.append(pkg)
            if result.soft_deps:
                warnings.append({
                    "package": pkg.name,
                    "level": "info",
                    "message": f"Has optional systemd integration "
                               f"({', '.join(result.soft_deps)}) — safe to ignore",
                })
        else:
            if strict:
                raise SystemdDependencyError(pkg.name, result.hard_deps)

            alt_msg = ""
            if result.alternatives:
                alts = [f"{k} → {v}" for k, v in result.alternatives.items()]
                alt_msg = f". Alternatives: {', '.join(alts)}"

            warnings.append({
                "package": pkg.name,
                "level": "blocked",
                "message": f"Requires systemd: {', '.join(result.hard_deps)}"
                           f"{alt_msg}",
                "source_build": result.source_build_advised,
            })

    return safe, warnings
