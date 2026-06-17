/*
 * Sven — Seven OS Package Manager
 * HANS TECH © 2024 — GPL v3
 * libsven/conflicts.c — Fast file-ownership map + conflict detection
 *
 * Replaces the O(n·m) Python dict-build in resolver/file_conflict.py
 * with a C hash set using open-addressing (FNV-1a hashing).
 *
 * Exported symbols:
 *
 *   sven_conflict_ctx *sven_conflict_new(int capacity)
 *       Allocate a new conflict-detection context.
 *       capacity: hint for number of (file, owner) pairs. Auto-grows.
 *       Returns NULL on OOM.
 *
 *   void sven_conflict_free(sven_conflict_ctx *ctx)
 *       Free all memory.
 *
 *   int sven_conflict_add(sven_conflict_ctx *ctx,
 *                         const char *filepath,
 *                         const char *owner_pkg)
 *       Register a file as owned by owner_pkg.
 *       Returns 0 on success, -1 on OOM.
 *
 *   const char *sven_conflict_owner(const sven_conflict_ctx *ctx,
 *                                   const char *filepath)
 *       Return the name of the package that owns filepath,
 *       or NULL if no owner recorded.
 *
 *   int sven_conflict_check(const sven_conflict_ctx *ctx,
 *                           const char **new_files, int n_files,
 *                           const char *installing_pkg,
 *                           char *conflict_file_out,  size_t file_sz,
 *                           char *conflict_owner_out, size_t owner_sz)
 *       Check n_files against the ownership map.
 *       On conflict returns 1 and fills conflict_file_out + conflict_owner_out.
 *       Returns 0 if clean, -1 on bad args.
 */

#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

/* ── FNV-1a hash ─────────────────────────────────────────────────────────── */

static uint64_t fnv1a(const char *s)
{
    uint64_t h = UINT64_C(14695981039346656037);
    while (*s) {
        h ^= (unsigned char)*s++;
        h *= UINT64_C(1099511628211);
    }
    return h;
}

/* ── Hash table entry ────────────────────────────────────────────────────── */

typedef struct {
    char *filepath;     /* heap-allocated copy — NULL = empty slot */
    char *owner;        /* heap-allocated copy */
} ht_entry;

/* ── Context ─────────────────────────────────────────────────────────────── */

typedef struct sven_conflict_ctx {
    ht_entry *table;
    int       capacity;   /* always a power of 2 */
    int       size;       /* number of entries */
} sven_conflict_ctx;

/* ── Internal helpers ────────────────────────────────────────────────────── */

static int next_pow2(int n)
{
    int p = 1;
    while (p < n) p <<= 1;
    return p;
}

/* Insert into a raw table (no ownership check, no resize). */
static int ht_insert_raw(ht_entry *table, int cap,
                          char *filepath, char *owner)
{
    uint64_t h = fnv1a(filepath);
    int idx = (int)(h & (uint64_t)(cap - 1));
    for (int probe = 0; probe < cap; probe++) {
        ht_entry *e = &table[(idx + probe) & (cap - 1)];
        if (!e->filepath) {
            e->filepath = filepath;
            e->owner    = owner;
            return 0;
        }
    }
    return -1; /* table full — should not happen */
}

static int ctx_resize(sven_conflict_ctx *ctx)
{
    int new_cap = ctx->capacity * 2;
    ht_entry *new_table = (ht_entry *)calloc(new_cap, sizeof(ht_entry));
    if (!new_table) return -1;

    for (int i = 0; i < ctx->capacity; i++) {
        ht_entry *e = &ctx->table[i];
        if (e->filepath) {
            ht_insert_raw(new_table, new_cap, e->filepath, e->owner);
        }
    }
    free(ctx->table);
    ctx->table    = new_table;
    ctx->capacity = new_cap;
    return 0;
}

/* ── Public API ──────────────────────────────────────────────────────────── */

sven_conflict_ctx *sven_conflict_new(int capacity)
{
    if (capacity < 16) capacity = 16;
    capacity = next_pow2(capacity * 2); /* keep load < 0.5 */

    sven_conflict_ctx *ctx = (sven_conflict_ctx *)malloc(sizeof(sven_conflict_ctx));
    if (!ctx) return NULL;

    ctx->table    = (ht_entry *)calloc(capacity, sizeof(ht_entry));
    ctx->capacity = capacity;
    ctx->size     = 0;

    if (!ctx->table) { free(ctx); return NULL; }
    return ctx;
}

void sven_conflict_free(sven_conflict_ctx *ctx)
{
    if (!ctx) return;
    for (int i = 0; i < ctx->capacity; i++) {
        if (ctx->table[i].filepath) {
            free(ctx->table[i].filepath);
            free(ctx->table[i].owner);
        }
    }
    free(ctx->table);
    free(ctx);
}

int sven_conflict_add(sven_conflict_ctx *ctx,
                      const char *filepath,
                      const char *owner_pkg)
{
    if (!ctx || !filepath || !owner_pkg) return -1;

    /* Resize if load factor > 0.5 */
    if (ctx->size * 2 >= ctx->capacity) {
        if (ctx_resize(ctx) != 0) return -1;
    }

    char *fp_copy = strdup(filepath);
    char *ow_copy = strdup(owner_pkg);
    if (!fp_copy || !ow_copy) { free(fp_copy); free(ow_copy); return -1; }

    if (ht_insert_raw(ctx->table, ctx->capacity, fp_copy, ow_copy) != 0) {
        free(fp_copy); free(ow_copy); return -1;
    }
    ctx->size++;
    return 0;
}

const char *sven_conflict_owner(const sven_conflict_ctx *ctx,
                                const char *filepath)
{
    if (!ctx || !filepath) return NULL;
    uint64_t h = fnv1a(filepath);
    int idx = (int)(h & (uint64_t)(ctx->capacity - 1));
    for (int probe = 0; probe < ctx->capacity; probe++) {
        ht_entry *e = &ctx->table[(idx + probe) & (ctx->capacity - 1)];
        if (!e->filepath) return NULL;   /* empty slot = not found */
        if (strcmp(e->filepath, filepath) == 0) return e->owner;
    }
    return NULL;
}

int sven_conflict_check(const sven_conflict_ctx *ctx,
                        const char **new_files, int n_files,
                        const char *installing_pkg,
                        char *conflict_file_out,  size_t file_sz,
                        char *conflict_owner_out, size_t owner_sz)
{
    if (!ctx || !new_files || !installing_pkg) return -1;

    for (int i = 0; i < n_files; i++) {
        const char *f = new_files[i];
        if (!f) continue;

        const char *owner = sven_conflict_owner(ctx, f);
        if (owner && strcmp(owner, installing_pkg) != 0) {
            /* Conflict found */
            if (conflict_file_out && file_sz > 0)
                snprintf(conflict_file_out,  file_sz,  "%s", f);
            if (conflict_owner_out && owner_sz > 0)
                snprintf(conflict_owner_out, owner_sz, "%s", owner);
            return 1;
        }
    }
    return 0;
}
