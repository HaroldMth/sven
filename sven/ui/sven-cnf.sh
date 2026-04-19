# ============================================================
#  Sven Command-Not-Found Shell Integration
#  HANS TECH © 2024 — GPL v3
# ============================================================
#
#  To enable, add this to your .bashrc or .zshrc:
#    source /etc/sven/sven-cnf.sh
#

# BASH integration
command_not_found_handle() {
    local cmd="$1"
    # Call sven cnf
    # We use 'sven' directly, assuming it's in PATH
    sven cnf "$cmd" 2>/dev/null
    
    # Return 127 to keep standard Bash behavior (Command not found)
    return 127
}

# ZSH integration
command_not_found_handler() {
    local cmd="$1"
    sven cnf "$cmd" 2>/dev/null
    return 127
}
