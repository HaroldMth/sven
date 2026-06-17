/*
 * Sven — Seven OS Package Manager
 * HANS TECH © 2024 — GPL v3
 * libsven/pacnew.c — .pacnew / .pacsave config-file protection
 *
 * Mirrors pacman's behaviour:
 *
 *   .pacnew  — during upgrade/install, if a config file under /etc/
 *              already exists on disk (user may have edited it), the
 *              incoming file is saved alongside as <path>.pacnew instead
 *              of silently overwriting user changes.
 *
 *   .pacsave — during remove, if a config file under /etc/ exists on
 *              disk, it is copied to <path>.pacsave before being deleted,
 *              so the user doesn't lose their config.
 *
 * Exported symbols:
 *
 *   int sven_is_config_path(const char *path)
 *       Returns 1 if path looks like a user-editable config file
 *       (under /etc/, not a directory, not a .d/ fragment directory).
 *
 *   int sven_needs_pacnew(const char *dest_path,
 *                         const char *src_sha256)
 *       Returns 1 if dest_path exists AND its SHA-256 differs from
 *       src_sha256 (the incoming file's hash), meaning the user has a
 *       local version that would be silently overwritten.
 *       Returns 0 if safe to overwrite, -1 on error.
 *
 *   int sven_save_pacnew(const char *src_path, const char *dest_path)
 *       Copy src_path to dest_path.pacnew.
 *       Returns 0 on success, -1 on error.
 *
 *   int sven_save_pacsave(const char *path)
 *       Copy path to path.pacsave.
 *       Returns 0 on success, -1 on error (file not found = 0).
 */

#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <errno.h>

/* Forward declaration — from checksum.c, same .so */
extern int sven_sha256_file(const char *path, char *hex_out, size_t hex_out_sz);

/* ── sven_is_config_path ─────────────────────────────────────────────────── */

int sven_is_config_path(const char *path)
{
    if (!path) return 0;

    /* Must be under /etc/ */
    if (strncmp(path, "/etc/", 5) != 0) return 0;

    /* Skip drop-in dirs (e.g. /etc/foo.d/) — we care about actual files */
    size_t len = strlen(path);
    if (len > 0 && path[len - 1] == '/') return 0;

    /* Skip common non-config binary blobs */
    const char *ext = strrchr(path, '.');
    if (ext) {
        if (strcmp(ext, ".so")  == 0) return 0;
        if (strcmp(ext, ".a")   == 0) return 0;
        if (strcmp(ext, ".pyc") == 0) return 0;
    }

    return 1;
}

/* ── File copy helper ────────────────────────────────────────────────────── */

static int file_copy(const char *src, const char *dst)
{
    FILE *in  = fopen(src, "rb");
    if (!in) return -1;

    FILE *out = fopen(dst, "wb");
    if (!out) { fclose(in); return -1; }

    char buf[65536];
    size_t n;
    int err = 0;
    while ((n = fread(buf, 1, sizeof(buf), in)) > 0) {
        if (fwrite(buf, 1, n, out) != n) { err = 1; break; }
    }
    if (ferror(in)) err = 1;

    fclose(in);
    fclose(out);
    return err ? -1 : 0;
}

/* ── sven_needs_pacnew ───────────────────────────────────────────────────── */

int sven_needs_pacnew(const char *dest_path, const char *src_sha256)
{
    if (!dest_path) return -1;

    /* File must already exist on disk */
    struct stat st;
    if (stat(dest_path, &st) != 0) return 0;   /* doesn't exist → safe to write */
    if (!S_ISREG(st.st_mode))      return 0;   /* not a regular file → skip */

    /* If no checksum supplied, assume conflict to be safe */
    if (!src_sha256 || strlen(src_sha256) != 64) return 1;

    char existing_hash[65];
    if (sven_sha256_file(dest_path, existing_hash, sizeof(existing_hash)) != 0)
        return 1;   /* can't read existing file → treat as conflict */

    /* If hashes differ, user has modified the file */
    for (int i = 0; i < 64; i++) {
        char a = existing_hash[i];
        char b = src_sha256[i];
        /* lowercase compare */
        if (a >= 'A' && a <= 'F') a += 32;
        if (b >= 'A' && b <= 'F') b += 32;
        if (a != b) return 1;
    }
    return 0;   /* hashes match → file unchanged → safe to overwrite */
}

/* ── sven_save_pacnew ────────────────────────────────────────────────────── */

int sven_save_pacnew(const char *src_path, const char *dest_path)
{
    if (!src_path || !dest_path) return -1;

    char pacnew[4096];
    if (snprintf(pacnew, sizeof(pacnew), "%s.pacnew", dest_path)
            >= (int)sizeof(pacnew)) return -1;

    return file_copy(src_path, pacnew);
}

/* ── sven_save_pacsave ───────────────────────────────────────────────────── */

int sven_save_pacsave(const char *path)
{
    if (!path) return -1;

    struct stat st;
    if (stat(path, &st) != 0) return 0;   /* file gone already — fine */
    if (!S_ISREG(st.st_mode)) return 0;

    char pacsave[4096];
    if (snprintf(pacsave, sizeof(pacsave), "%s.pacsave", path)
            >= (int)sizeof(pacsave)) return -1;

    return file_copy(path, pacsave);
}
