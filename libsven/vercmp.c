#include <string.h>
#include <stdlib.h>
#include <ctype.h>

/* 
 * A blazing fast C implementation of the package version comparison.
 * Returns -1 if a < b, 0 if a == b, 1 if a > b.
 * This will replace the slow Regex/Python split in DependencyGraph.
 */
int sven_vercmp(const char *a, const char *b) {
    if (strcmp(a, b) == 0) return 0;
    
    const char *p1 = a;
    const char *p2 = b;
    
    while (*p1 && *p2) {
        // Skip non-alphanumeric separators
        while (*p1 && !isalnum(*p1)) p1++;
        while (*p2 && !isalnum(*p2)) p2++;
        
        if (!*p1 && !*p2) break;
        if (!*p1) return -1;
        if (!*p2) return 1;
        
        int is_num1 = isdigit(*p1);
        int is_num2 = isdigit(*p2);
        
        if (is_num1 && is_num2) {
            // Compare as numbers
            long n1 = strtol(p1, (char**)&p1, 10);
            long n2 = strtol(p2, (char**)&p2, 10);
            if (n1 < n2) return -1;
            if (n1 > n2) return 1;
        } else if (!is_num1 && !is_num2) {
            // Compare as alphabetic strings
            while (*p1 && *p2 && isalpha(*p1) && isalpha(*p2)) {
                if (*p1 < *p2) return -1;
                if (*p1 > *p2) return 1;
                p1++; p2++;
            }
            if (isalpha(*p1) && !isalpha(*p2)) return 1;
            if (!isalpha(*p1) && isalpha(*p2)) return -1;
        } else {
            // Number vs String: numbers are typically newer/greater than letters (e.g. 1.0 > 1.rc)
            return is_num1 ? 1 : -1;
        }
    }
    
    // Check if one string has remaining alphanumeric parts
    while (*p1 && !isalnum(*p1)) p1++;
    while (*p2 && !isalnum(*p2)) p2++;
    
    if (*p1 && !*p2) return 1;
    if (!*p1 && *p2) return -1;
    
    return 0;
}
