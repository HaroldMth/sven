# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  ui/progress.py — Multi-line parallel progress bars
# ============================================================

import os
import sys
import threading
from typing import List, Dict


def _term_width() -> int:
    """Get terminal width, default 80 if not a TTY."""
    try:
        return os.get_terminal_size().columns
    except (ValueError, OSError):
        return 80


class MultiProgressDisplay:
    """
    Manages a windowed set of parallel progress bars + a global total bar.
    Adapts to terminal width to prevent line wrapping/breakage.
    """

    def __init__(self, filenames: List[str], window_size: int = 6):
        self.all_filenames = filenames
        self.total_count   = len(filenames)
        self.window_size   = min(window_size, self.total_count)
        self.lock          = threading.Lock()
        self.is_tty        = os.isatty(sys.stdout.fileno())

        # State
        self.completed_count = 0
        self.total_bytes_dl  = 0
        self.total_bytes_expected = 0

        # Mapping: filename -> {slot_idx, downloaded, total}
        self.active_slots: Dict[str, dict] = {}
        self.pending_queue = filenames.copy()

        # Slot indices currently available
        self.free_slots = list(range(self.window_size))

        if not self.is_tty:
            print(f"   :: Downloading {self.total_count} package(s)...", flush=True)
            return

        # Initial setup: reserve space for window_size lines + global bar
        print("\n" * (self.window_size + 1), end="", flush=True)

    def update(self, filename: str, downloaded: int, total: int):
        """Update a specific package's progress and the global bar."""
        if not self.is_tty:
            return

        with self.lock:
            # Assign a slot if this package is new and we have space
            if filename not in self.active_slots:
                if not self.free_slots:
                    return  # No slot available yet
                slot = self.free_slots.pop(0)
                self.active_slots[filename] = {"slot": slot, "dl": 0, "tot": 0}

            data = self.active_slots[filename]
            data["dl"] = downloaded
            data["tot"] = total

            self._render()

    def finish_single(self, filename: str):
        """Log the package as done above the block and free its slot."""
        with self.lock:
            self.completed_count += 1

            if not self.is_tty:
                idx = self.completed_count
                name = self._format_name(filename)
                print(f"   [{idx}/{self.total_count}]  {name:<35}  ✓ DONE", flush=True)
                return

            if filename in self.active_slots:
                data = self.active_slots.pop(filename)
                self.free_slots.append(data["slot"])
                self.free_slots.sort()

                # Log completion ABOVE the block
                lines_up = self.window_size + 1
                sys.stdout.write(f"\033[{lines_up}A\r\033[2K")

                name_str = self._format_name(filename)
                idx_str  = f"[{self.completed_count}/{self.total_count}]".rjust(7)
                sys.stdout.write(f"   {idx_str}  {name_str:<35}  ✓ DONE\n")

                # Move back to bottom
                sys.stdout.write(f"\033[{lines_up - 1}B")
                sys.stdout.flush()

            self._render()

    def _render(self):
        """Re-render the active window and global bar, adapted to terminal width."""
        tw = _term_width()
        jump_up = self.window_size + 1
        sys.stdout.write(f"\033[{jump_up}A")

        # Adaptive bar sizing
        # Layout: "    » name  [bar]  pct  dl/tot MB"
        # Fixed overhead: ~45 chars (prefix + spacing + size text)
        # We want bar_width to fill the remaining space
        name_len = min(25, tw // 4)
        overhead = 6 + name_len + 5 + 6 + 16  # "    » " + name + "  [" + "]  " + "100%  xx.x/xx.x MB"
        bar_width = max(8, tw - overhead)

        slot_map = {v["slot"]: k for k, v in self.active_slots.items()}

        for i in range(self.window_size):
            sys.stdout.write("\r\033[2K")
            if i in slot_map:
                fname = slot_map[i]
                data  = self.active_slots[fname]

                pct = data["dl"] / data["tot"] if data["tot"] > 0 else 0
                pct_int = int(pct * 100)
                filled = int(pct * bar_width)
                bar = "█" * filled + "░" * (bar_width - filled)

                dl_mb = data["dl"] / 1_000_000
                tot_mb = data["tot"] / 1_000_000
                name = self._format_name(fname, maxlen=name_len)

                line = f"    » {name:<{name_len}}  [{bar}] {pct_int:>3}%  {dl_mb:.1f}/{tot_mb:.1f} MB"
                sys.stdout.write(line[:tw] + "\n")
            else:
                sys.stdout.write("    -- (waiting for slot) --\n")

        # Global Total Bar
        sys.stdout.write("\r\033[2K")
        total_pct = self.completed_count / self.total_count if self.total_count > 0 else 0
        total_pct_int = int(total_pct * 100)
        g_bar_width = max(8, tw - 50)
        filled = int(total_pct * g_bar_width)
        global_bar = "█" * filled + "░" * (g_bar_width - filled)

        total_line = f"   TOTAL: [{global_bar}] {total_pct_int:>3}%  {self.completed_count}/{self.total_count} packages complete"
        sys.stdout.write(total_line[:tw] + "\n")
        sys.stdout.flush()

    def finish_all(self):
        """Final cleanup."""
        if self.is_tty:
            print("\n   ★ Download phase complete.", flush=True)

    def _format_name(self, filename: str, maxlen: int = 25) -> str:
        name = filename
        for ext in (".pkg.tar.zst", ".pkg.tar.xz", ".sven"):
            if name.endswith(ext):
                name = name[:-len(ext)]
                break
        if len(name) > maxlen:
            return name[:maxlen-3] + "..."
        return name


# ── Compatibility Stubs ────────────────────────────────────────

class ProgressBar:
    """Legacy single progress bar stub."""
    def __init__(self, *args, **kwargs): pass
    def update(self, *args, **kwargs): pass
    def finish(self, *args, **kwargs): pass


class Spinner:
    """Legacy spinner stub."""
    def __init__(self, *args, **kwargs): pass
    def start(self, *args, **kwargs): pass
    def stop(self, *args, **kwargs): pass
