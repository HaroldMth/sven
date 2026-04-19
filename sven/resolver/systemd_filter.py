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

from ..db.models import Package
from ..exceptions import SystemdDependencyError


# ── Known systemd packages and libraries ─────────────────────

# HARD deps: the package links against systemd or requires it to function
SYSTEMD_HARD_DEPS = frozenset({
    "systemd",
    "systemd-sysvcompat",
    "systemd-resolvconf",
    "systemd-ukify",
})

# SOFT deps: the package ships .service files or optional integration
# These are safe to install — the service files just won't be used
SYSTEMD_SOFT_INDICATORS = frozenset({
    "systemd-service",
    "systemctl",
})

# Alternative packages that provide systemd-like functionality on non-systemd
SYSTEMD_ALTERNATIVES = {
    "systemd-libs":    "elogind",
    "libsystemd":      "elogind",
    "libsystemd.so":   "elogind",
    "libsystemd.so=0-64": "elogind",
    "libudev.so":      "eudev",
    "systemd":         None,   # No drop-in alternative
}


class SystemdCheckResult(NamedTuple):
    """Result of checking a package for systemd dependencies."""
    safe: bool                    # True if package is safe to install
    hard_deps: list[str]          # systemd deps that will prevent function
    soft_deps: list[str]          # systemd deps that are optional/ignorable
    alternatives: dict[str, str]  # suggested alternative for each hard dep
    source_build_advised: bool    # should we build from source instead?


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
    # If we're on systemd, everything is fine
    if init_system == "systemd":
        return SystemdCheckResult(
            safe=True, hard_deps=[], soft_deps=[],
            alternatives={}, source_build_advised=False,
        )

    all_deps = pkg.deps
    hard_deps = []
    soft_deps = []

    alternatives = {}

    for dep in all_deps:
        # Strip version constraints
        dep_name = dep.split(">=")[0].split("<=")[0].split(">")[0].split("<")[0].split("=")[0].strip()

        if dep_name in SYSTEMD_HARD_DEPS:
            # Special case: pacman declares "systemd" for sysusers hook but operates
            # perfectly fine natively without it.
            if pkg.name == "pacman" and dep_name == "systemd":
                continue

            hard_deps.append(dep_name)
            alt = SYSTEMD_ALTERNATIVES.get(dep_name)
            if alt:
                alternatives[dep_name] = alt

        elif dep_name in SYSTEMD_SOFT_INDICATORS:
            soft_deps.append(dep_name)

        # Also check for .so references to systemd libraries
        elif "libsystemd" in dep_name or "libudev" in dep_name:
            hard_deps.append(dep_name)
            alt = SYSTEMD_ALTERNATIVES.get(dep_name)
            if alt:
                alternatives[dep_name] = alt

    safe = len(hard_deps) == 0 or (len(hard_deps) > 0 and len(alternatives) == len(hard_deps))
    source_advised = not safe and len(alternatives) < len(hard_deps)

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
