#include <fnmatch.h>
#include <string.h>

/*
 * High-performance ALPM hook path matcher.
 * ALPM hooks specify target globs like "usr/lib/modules/wildcard/vmlinuz".
 * During a transaction, thousands of files are extracted.
 * This function quickly scans the array of extracted files
 * to see if any of them trigger the hook pattern.
 *
 * Returns 1 if a match is found, 0 otherwise.
 */
int sven_match_path(const char *pattern, const char **files, int num_files) {
    if (!pattern || !files || num_files <= 0) return 0;
    
    // fnmatch() is a POSIX standard glob matcher.
    // FNM_PATHNAME ensures '*' doesn't match '/' unless specified.
    // However, ALPM targets treat '*' as matching across directories sometimes,
    // so standard 0 is usually safer for pure string matching unless ALPM strictly requires FNM_PATHNAME.
    // We'll use 0 to match Pacman's broad targeting.
    
    for (int i = 0; i < num_files; i++) {
        if (!files[i]) continue;
        
        // Strip leading slash from files[i] if present, because ALPM targets usually don't have them
        const char *file_path = files[i];
        if (file_path[0] == '/') file_path++;
        
        if (fnmatch(pattern, file_path, 0) == 0) {
            return 1;
        }
    }
    return 0;
}
