/*
 * Sven — Seven OS Package Manager
 * HANS TECH © 2024 — GPL v3
 * libsven/resolver.c — Dependency string parsing + version constraint checks
 *
 * Three hot-path functions called thousands of times per transaction:
 *   sven_parse_dep()      — "bash>=5.0"  →  name="bash"  op=">="  ver="5.0"
 *   sven_strip_constraint() — "bash>=5.0" →  "bash"
 *   sven_dep_satisfied()  — check if installed_ver satisfies op+req_ver
 */

#include <string.h>
#include <stdlib.h>
#include <stdio.h>

/* Forward declaration from vercmp.c — compiled into the same .so */
extern int sven_vercmp(const char *a, const char *b);


/* ── sven_parse_dep ──────────────────────────────────────────────────────────
 *
 * Parse an Arch-style dependency string into its three parts.
 *
 * Examples:
 *   "bash>=5.0"   → name="bash",    op=">=", ver="5.0"
 *   "glibc>2.17"  → name="glibc",   op=">",  ver="2.17"
 *   "curl=8.0.1"  → name="curl",    op="=",  ver="8.0.1"
 *   "openssl"     → name="openssl", op="",   ver=""
 *
 * Returns 0 on success, -1 if any output buffer is too small.
 * If no operator is found, op_out and ver_out are set to empty strings.
 */
int sven_parse_dep(
    const char *dep_str,
    char       *name_out, size_t name_sz,
    char       *op_out,   size_t op_sz,
    char       *ver_out,  size_t ver_sz
) {
    if (!dep_str || !name_out) return -1;

    const char *p       = dep_str;
    const char *op_pos  = NULL;
    size_t      op_len  = 0;

    /* Scan for operator characters */
    while (*p) {
        if (*p == '>' || *p == '<' || *p == '=') {
            op_pos = p;
            if ((p[0] == '>' || p[0] == '<') && p[1] == '=') {
                op_len = 2;
            } else {
                op_len = 1;
            }
            break;
        }
        p++;
    }

    if (!op_pos) {
        /* No operator — pure package name */
        size_t len = strlen(dep_str);
        if (len >= name_sz) return -1;
        memcpy(name_out, dep_str, len + 1);
        if (op_out  && op_sz  > 0) op_out[0]  = '\0';
        if (ver_out && ver_sz > 0) ver_out[0] = '\0';
        return 0;
    }

    /* Name part */
    size_t name_len = (size_t)(op_pos - dep_str);
    if (name_len >= name_sz) return -1;
    memcpy(name_out, dep_str, name_len);
    name_out[name_len] = '\0';

    /* Operator part */
    if (op_out) {
        if (op_len >= op_sz) return -1;
        memcpy(op_out, op_pos, op_len);
        op_out[op_len] = '\0';
    }

    /* Version part — everything after the operator */
    if (ver_out) {
        const char *ver_start = op_pos + op_len;
        size_t ver_len = strlen(ver_start);
        if (ver_len >= ver_sz) return -1;
        memcpy(ver_out, ver_start, ver_len + 1);
    }

    return 0;
}


/* ── sven_strip_constraint ───────────────────────────────────────────────────
 *
 * Strip the version constraint from a dep string, leaving only the package name.
 *
 *   "bash>=5.0"  →  "bash"
 *   "glibc>2.17" →  "glibc"
 *   "openssl"    →  "openssl"
 *
 * Writes into `out` (up to out_sz bytes incl. null terminator).
 * Also trims any trailing ASCII whitespace from the name.
 * Returns `out` on success, NULL on error.
 */
const char *sven_strip_constraint(const char *dep_str, char *out, size_t out_sz)
{
    if (!dep_str || !out || out_sz == 0) return NULL;

    const char *p = dep_str;
    size_t i = 0;

    while (*p && *p != '>' && *p != '<' && *p != '=') {
        if (i + 1 >= out_sz) return NULL;
        out[i++] = *p++;
    }

    /* Trim trailing whitespace */
    while (i > 0 && (out[i - 1] == ' ' || out[i - 1] == '\t')) {
        i--;
    }

    out[i] = '\0';
    return out;
}


/* ── sven_dep_satisfied ──────────────────────────────────────────────────────
 *
 * Check whether `installed_ver` satisfies the constraint `op` + `req_ver`.
 *
 *   sven_dep_satisfied("5.2", ">=", "5.0")  →  1  (satisfied)
 *   sven_dep_satisfied("4.9", ">=", "5.0")  →  0  (not satisfied)
 *   sven_dep_satisfied("5.0", "=",  "5.0")  →  1
 *
 * Uses sven_vercmp() for correct Arch-compatible version ordering.
 * Returns:
 *    1  — constraint satisfied
 *    0  — constraint not satisfied
 *   -1  — unknown operator or NULL input
 */
int sven_dep_satisfied(const char *installed_ver, const char *op, const char *req_ver)
{
    if (!installed_ver || !op || !req_ver) return -1;

    char *inst_copy = NULL;
    const char *inst_to_compare = installed_ver;

    /* If req_ver has no pkgrel component (no '-'), but installed_ver does,
     * strip the pkgrel part from installed_ver for the comparison. */
    if (!strchr(req_ver, '-') && strchr(installed_ver, '-')) {
        inst_copy = strdup(installed_ver);
        char *last_dash = strrchr(inst_copy, '-');
        if (last_dash) {
            *last_dash = '\0';
        }
        inst_to_compare = inst_copy;
    }

    int cmp = sven_vercmp(inst_to_compare, req_ver);

    if (inst_copy) {
        free(inst_copy);
    }

    if (op[0] == '>' && op[1] == '=') return (cmp >= 0) ? 1 : 0;
    if (op[0] == '<' && op[1] == '=') return (cmp <= 0) ? 1 : 0;
    if (op[0] == '>' && op[1] == '\0') return (cmp >  0) ? 1 : 0;
    if (op[0] == '<' && op[1] == '\0') return (cmp <  0) ? 1 : 0;
    if (op[0] == '=' && op[1] == '\0') return (cmp == 0) ? 1 : 0;
    /* Also handle "==" if someone passes it */
    if (op[0] == '=' && op[1] == '=') return (cmp == 0) ? 1 : 0;

    return -1;
}
