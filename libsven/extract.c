/*
 * Sven — Seven OS Package Manager
 * HANS TECH © 2024 — GPL v3
 * libsven/extract.c — .pkg.tar.zst extractor via libarchive
 *
 * Replaces installer/extractor.py's Python tarfile + zstandard loop.
 * Uses libarchive which handles all compression formats natively in C.
 *
 * COMPILE REQUIREMENT: libarchive-dev
 *   gcc -shared -fPIC ... extract.c -larchive
 *
 * On Seven OS / LFS:
 *   sven install libarchive
 *   make build
 *
 * sven_extract_zst()      — extract archive to root, return file list
 * sven_free_file_list()   — free the file list returned above
 */

#include <archive.h>
#include <archive_entry.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <limits.h>

/* Arch package metadata files — never extracted to the filesystem */
static const char *META_FILES[] = {
    ".PKGINFO", ".MTREE", ".INSTALL", ".BUILDINFO", NULL
};

static int is_metadata(const char *name)
{
    /* Strip leading ./ if present */
    if (name[0] == '.' && name[1] == '/') name += 2;

    for (int i = 0; META_FILES[i]; i++) {
        /* META_FILES start with '.' — compare with and without it */
        if (strcmp(name, META_FILES[i]) == 0) return 1;
        /* Compare without leading dot in table entry */
        if (strcmp(name, META_FILES[i] + 1) == 0) return 1;
    }
    return 0;
}

/* Helper: copy archive data to disk entry */
static int copy_data(struct archive *ar, struct archive *aw)
{
    const void *buff;
    size_t size;
    la_int64_t offset;
    int r;

    while (1) {
        r = archive_read_data_block(ar, &buff, &size, &offset);
        if (r == ARCHIVE_EOF) return ARCHIVE_OK;
        if (r < ARCHIVE_OK) return r;
        r = archive_write_data_block(aw, buff, size, offset);
        if (r < ARCHIVE_OK) return r;
    }
}


/* ── sven_extract_zst ────────────────────────────────────────────────────────
 *
 * Extract a .pkg.tar.zst (or any libarchive-supported format) to `root_path`.
 *
 * Parameters:
 *   archive_path  — absolute path to the .pkg.tar.zst file
 *   root_path     — installation root (e.g. "/" or "/mnt/seven")
 *   out_files     — caller-allocated array of char* (size max_files)
 *                   receives strdup'd absolute paths of extracted files
 *   max_files     — capacity of out_files
 *
 * Returns number of files extracted, or -1 on fatal error.
 *
 * IMPORTANT: Call sven_free_file_list(out_files, return_value) when done.
 * Directories are created but NOT counted in the return value or out_files.
 */
int sven_extract_zst(
    const char  *archive_path,
    const char  *root_path,
    char       **out_files,
    int          max_files
) {
    if (!archive_path || !root_path || !out_files || max_files <= 0) return -1;

    struct archive       *a   = archive_read_new();
    struct archive       *ext = archive_write_disk_new();
    struct archive_entry *entry;
    int r, count = 0;

    /* Support all formats and compression types */
    archive_read_support_filter_all(a);
    archive_read_support_format_all(a);

    /* Disk writer: preserve permissions and timestamps */
    int flags = ARCHIVE_EXTRACT_TIME
              | ARCHIVE_EXTRACT_PERM
              | ARCHIVE_EXTRACT_ACL
              | ARCHIVE_EXTRACT_FFLAGS
              | ARCHIVE_EXTRACT_UNLINK;   /* unlink before writing = no text-file-busy */
    archive_write_disk_set_options(ext, flags);
    archive_write_disk_set_standard_lookup(ext);

    r = archive_read_open_filename(a, archive_path, 65536);
    if (r != ARCHIVE_OK) {
        archive_read_free(a);
        archive_write_free(ext);
        return -1;
    }

    char dest[PATH_MAX];
    size_t root_len = strlen(root_path);
    /* Ensure root doesn't end with '/' for clean path joining */
    char root_clean[PATH_MAX];
    strncpy(root_clean, root_path, sizeof(root_clean) - 1);
    root_clean[sizeof(root_clean) - 1] = '\0';
    size_t rc_len = strlen(root_clean);
    if (rc_len > 1 && root_clean[rc_len - 1] == '/') {
        root_clean[rc_len - 1] = '\0';
    }

    while (archive_read_next_header(a, &entry) == ARCHIVE_OK) {
        const char *name = archive_entry_pathname(entry);
        if (!name) continue;

        /* Strip leading './' */
        if (name[0] == '.' && name[1] == '/') name += 2;
        if (name[0] == '.' && name[1] == '\0') { archive_read_data_skip(a); continue; }
        if (name[0] == '\0')                    { archive_read_data_skip(a); continue; }

        /* Skip metadata files */
        if (is_metadata(name)) {
            archive_read_data_skip(a);
            continue;
        }

        /* Build full destination path */
        int needed = snprintf(dest, sizeof(dest), "%s/%s", root_clean, name);
        if (needed < 0 || (size_t)needed >= sizeof(dest)) {
            archive_read_data_skip(a);
            continue;
        }

        /* Rewrite the entry pathname to the full destination */
        archive_entry_set_pathname(entry, dest);

        r = archive_write_header(ext, entry);
        if (r < ARCHIVE_OK) {
            /* Skip files we can't write */
            archive_read_data_skip(a);
            continue;
        }

        if (archive_entry_size(entry) > 0) {
            copy_data(a, ext);
        }
        archive_write_finish_entry(ext);

        /* Only record regular files and symlinks in out_files */
        unsigned int ftype = archive_entry_filetype(entry);
        if (ftype == AE_IFREG || ftype == AE_IFLNK) {
            if (count < max_files) {
                out_files[count] = strdup(dest);
                count++;
            }
        }
    }

    archive_read_close(a);
    archive_read_free(a);
    archive_write_close(ext);
    archive_write_free(ext);

    return count;
}


/* ── sven_free_file_list ─────────────────────────────────────────────────────
 *
 * Free the strdup'd strings written into out_files by sven_extract_zst.
 * Call with the same out_files array and the count returned by sven_extract_zst.
 */
void sven_free_file_list(char **out_files, int count)
{
    if (!out_files) return;
    for (int i = 0; i < count; i++) {
        if (out_files[i]) {
            free(out_files[i]);
            out_files[i] = NULL;
        }
    }
}
