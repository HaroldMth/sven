/*
 * Sven — Seven OS Package Manager
 * HANS TECH © 2024 — GPL v3
 * libsven/filter.c — Systemd dependency classification
 *
 * Replaces the Python frozenset lookups in resolver/systemd_filter.py.
 * Called once per dep per package during the resolver pass — tight loop.
 *
 * sven_classify_systemd_dep(name)   →  0=none, 1=hard, 2=soft
 * sven_filter_systemd_deps(...)     →  classify a whole dep array at once
 */

#include <string.h>

/* ── Static tables (keep in sync with systemd_filter.py) ────────────────── */

/* Packages that hard-require systemd to function */
static const char *HARD_DEPS[] = {
    "systemd",
    "systemd-libs",
    "systemd-sysvcompat",
    "systemd-resolvconf",
    "systemd-ukify",
    NULL
};

/* Packages that only ship .service files — safe on non-systemd */
static const char *SOFT_DEPS[] = {
    "systemd-service",
    "systemctl",
    NULL
};

/* Prefixes that indicate a hard systemd library dependency */
static const char *HARD_PREFIXES[] = {
    "libsystemd",
    "libudev",
    NULL
};


/* ── sven_classify_systemd_dep ───────────────────────────────────────────────
 *
 * Classify a SINGLE already-stripped (no version constraint) dep name.
 *
 * Returns:
 *   0 — not a systemd dep
 *   1 — hard systemd dep  (blocks install on SysVinit/OpenRC)
 *   2 — soft systemd dep  (optional integration, safe to ignore)
 */
int sven_classify_systemd_dep(const char *dep_name)
{
    if (!dep_name || dep_name[0] == '\0') return 0;

    /* Exact match against hard deps */
    for (int i = 0; HARD_DEPS[i]; i++) {
        if (strcmp(dep_name, HARD_DEPS[i]) == 0) return 1;
    }

    /* Exact match against soft deps */
    for (int i = 0; SOFT_DEPS[i]; i++) {
        if (strcmp(dep_name, SOFT_DEPS[i]) == 0) return 2;
    }

    /* Prefix match for .so-style references ("libsystemd.so=0-64", "libudev.so") */
    for (int i = 0; HARD_PREFIXES[i]; i++) {
        size_t plen = strlen(HARD_PREFIXES[i]);
        if (strncmp(dep_name, HARD_PREFIXES[i], plen) == 0) return 1;
    }

    return 0;
}


/* ── sven_filter_systemd_deps ────────────────────────────────────────────────
 *
 * Batch-classify an array of raw dep strings (may contain version constraints).
 * Strips constraints internally before classifying.
 *
 * Parameters:
 *   dep_strs    — array of raw dep strings (e.g. "systemd>=252", "curl")
 *   n_deps      — number of entries in dep_strs
 *   out_hard    — caller-allocated int array; receives indices of hard deps
 *   n_hard_out  — receives count of hard deps written to out_hard
 *   out_soft    — caller-allocated int array; receives indices of soft deps
 *   n_soft_out  — receives count of soft deps written to out_soft
 *
 * Returns total number of systemd-related deps found (hard + soft).
 * Caller must allocate out_hard/out_soft with at least n_deps ints each.
 */
int sven_filter_systemd_deps(
    const char **dep_strs, int n_deps,
    int *out_hard, int *n_hard_out,
    int *out_soft, int *n_soft_out
) {
    if (!dep_strs || n_deps <= 0) {
        if (n_hard_out) *n_hard_out = 0;
        if (n_soft_out) *n_soft_out = 0;
        return 0;
    }

    int n_hard = 0, n_soft = 0, total = 0;
    char stripped[512];

    for (int i = 0; i < n_deps; i++) {
        const char *dep = dep_strs[i];
        if (!dep) continue;

        /* Strip version constraint inline */
        size_t j = 0;
        const char *p = dep;
        while (*p && *p != '>' && *p != '<' && *p != '=' && j < (sizeof(stripped) - 1)) {
            stripped[j++] = *p++;
        }
        /* Trim trailing space */
        while (j > 0 && stripped[j - 1] == ' ') j--;
        stripped[j] = '\0';

        int cls = sven_classify_systemd_dep(stripped);
        if (cls == 1) {
            if (out_hard) out_hard[n_hard] = i;
            n_hard++;
            total++;
        } else if (cls == 2) {
            if (out_soft) out_soft[n_soft] = i;
            n_soft++;
            total++;
        }
    }

    if (n_hard_out) *n_hard_out = n_hard;
    if (n_soft_out) *n_soft_out = n_soft;
    return total;
}
