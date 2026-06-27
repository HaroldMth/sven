# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  ui/progress.py — Parallel download progress (TTY-safe)
# ============================================================

import os
import sys
import threading
import time
from collections import deque
from typing import Dict, List, Optional, Set

from .output import color_enabled


def _term_width() -> int:
    try:
        return os.get_terminal_size().columns
    except (ValueError, OSError):
        return 80


def _style(code: str, text: str) -> str:
    if not color_enabled:
        return text
    return f"{code}{text}\033[0m"


class MultiProgressDisplay:
    """
    Parallel download progress for a TTY: redraws a fixed block of lines in place.
    Ignores updates for finished files (avoids ghost 100% bars after failover / races).
    When a download restarts (new mirror), byte counts may go backwards — we accept that.
    """

    _RENDER_MIN_INTERVAL = 0.09  # ~11 fps — less flicker than per-chunk redraws

    def __init__(
        self,
        filenames: List[str],
        window_size: int = 12,
        verbose: bool = False,
        shared_lock: Optional[threading.Lock] = None,
        known_sizes: Optional[Dict[str, int]] = None,
    ):
        self.all_filenames = filenames
        self.total_count = len(filenames)
        self.window_size = min(window_size, max(1, self.total_count))
        self.verbose = verbose
        self.lock = shared_lock if shared_lock is not None else threading.Lock()
        self.is_tty = os.isatty(sys.stdout.fileno())

        self.completed_count = 0
        self.active_slots: Dict[str, dict] = {}
        self.free_slots = list(range(self.window_size))
        self._finished: Set[str] = set()

        self._wait_fifo: deque[str] = deque()
        self._wait_set: set[str] = set()
        self._wait_buf: Dict[str, dict] = {}

        # For byte-weighted global progress. Seeded with every file's known
        # size upfront (from sync DB metadata) rather than discovered
        # incrementally as each download starts — otherwise the denominator
        # only covers whichever subset has started so far, grows as more
        # files get promoted from the wait queue, and the Overall percentage
        # ends up non-monotonic even though the byte math is locally correct
        # at each instant.
        self._file_totals: Dict[str, int] = dict(known_sizes or {})
        self._file_downloaded: Dict[str, int] = {}

        self._ever_rendered = False
        self._block_lines = self.window_size + 1
        self._last_render_ts = 0.0
        self._is_rendering = False

        if not self.is_tty:
            print(
                _style("\033[96m", f"   :: Downloading {self.total_count} package(s)…"),
                flush=True,
            )
            return

    def safe_print(self, message: str):
        """
        Safely print a message during progress rendering.
        In TTY mode, this clears the progress block, prints the message,
        then re-renders the progress to avoid corruption.
        Must be called with the lock held by caller.
        """
        if not self.is_tty:
            print(message, flush=True)
            return

        if self._ever_rendered:
            # Clear the progress block
            jump = self._block_lines
            sys.stdout.write(f"\033[{jump}A")
            for _ in range(jump):
                sys.stdout.write("\r\033[2K\n")
            sys.stdout.write(f"\033[{jump}A")

        # Print the message
        print(message, flush=True)

        # Re-render progress if we had it
        if self._ever_rendered:
            self._render()

    def _assign_slot(self, filename: str, downloaded: int = 0, total: int = 0) -> bool:
        """Return True if filename is active in a slot (mutate state; caller holds lock)."""
        if filename in self._finished:
            return False
        if filename in self.active_slots:
            return True
        if not self.free_slots:
            if filename not in self._wait_set:
                self._wait_fifo.append(filename)
                self._wait_set.add(filename)
            b = self._wait_buf.setdefault(filename, {"dl": 0, "tot": 0})
            b["dl"] = max(b["dl"], downloaded)
            if total > 0:
                b["tot"] = total
            return False
        slot = self.free_slots.pop(0)
        buf = self._wait_buf.pop(filename, None)
        if buf:
            dl, tot = buf["dl"], buf["tot"] if buf["tot"] > 0 else total
        else:
            dl, tot = downloaded, total
        self.active_slots[filename] = {"slot": slot, "dl": dl, "tot": tot}
        self._wait_set.discard(filename)
        try:
            self._wait_fifo.remove(filename)
        except ValueError:
            pass
        return True

    def _promote_waiting(self):
        while self.free_slots and self._wait_fifo:
            fn = self._wait_fifo.popleft()
            if fn in self._finished:
                self._wait_set.discard(fn)
                self._wait_buf.pop(fn, None)
                continue
            self._wait_set.discard(fn)
            buf = self._wait_buf.pop(fn, {"dl": 0, "tot": 0})
            slot = self.free_slots.pop(0)
            self.active_slots[fn] = {
                "slot": slot,
                "dl": buf["dl"],
                "tot": buf["tot"],
            }

    def update(self, filename: str, downloaded: int, total: int):
        with self.lock:
            if not self.is_tty or filename in self._finished:
                return

            if not self._assign_slot(filename, downloaded, total):
                b = self._wait_buf.setdefault(filename, {"dl": 0, "tot": 0})
                if downloaded < b["dl"]:
                    b["dl"] = downloaded
                elif downloaded > b["dl"]:
                    b["dl"] = downloaded
                if total > 0:
                    b["tot"] = total
                return

            data = self.active_slots[filename]
            # New HTTP attempt / mirror failover: byte count can drop — allow it
            data["dl"] = downloaded
            if total > 0:
                data["tot"] = total
            
            # Track bytes for global progress
            self._file_downloaded[filename] = downloaded
            if total > 0:
                self._file_totals[filename] = total

            now = time.monotonic()
            complete = total > 0 and downloaded >= total
            if (
                not complete
                and (now - self._last_render_ts) < self._RENDER_MIN_INTERVAL
            ):
                return
            self._last_render_ts = now
            self._render()

    # How long to hold a file's bar at a visible 100% before its slot gets
    # reused. Without this, the 100% frame and the slot-replacement render
    # happen back-to-back under the same lock with zero gap — the math is
    # correct but no human eye ever actually catches it on screen.
    _COMPLETE_HOLD_SECONDS = 0.12

    def finish_single(self, filename: str):
        with self.lock:
            if filename in self._finished:
                return
            if self.is_tty and filename in self.active_slots:
                # Force this slot to visibly show 100% and render it as its
                # own frame, before any swap happens.
                data = self.active_slots[filename]
                if data["tot"] > 0:
                    data["dl"] = data["tot"]
                    self._file_downloaded[filename] = data["tot"]
                self._last_render_ts = time.monotonic()
                self._render()

        if self.is_tty:
            time.sleep(self._COMPLETE_HOLD_SECONDS)

        with self.lock:
            if filename in self._finished:
                return  # another thread already finalized it during the hold
            self._finished.add(filename)
            self.completed_count += 1

            if not self.is_tty:
                name = self._format_name(filename)
                idx = self.completed_count
                w = max(2, len(str(self.total_count)))
                line = f"   [{idx:>{w}}/{self.total_count}]  {name:<36}  "
                print(_style("\033[92m", line + "✓"), flush=True)
                return

            if filename in self.active_slots:
                data = self.active_slots.pop(filename)
                self.free_slots.append(data["slot"])
                self.free_slots.sort()

            self._wait_set.discard(filename)
            self._wait_buf.pop(filename, None)
            try:
                self._wait_fifo.remove(filename)
            except ValueError:
                pass

            self._promote_waiting()
            self._last_render_ts = time.monotonic()
            self._render()

    def _render(self):
        if self._is_rendering:
            return  # Prevent concurrent renders
        self._is_rendering = True
        try:
            tw = _term_width()
            jump = self._block_lines

            if self._ever_rendered:
                sys.stdout.write(f"\033[{jump}A")

            slot_map: Dict[int, str] = {}
            for fname, meta in self.active_slots.items():
                slot_map[meta["slot"]] = fname

            name_len = min(22 if not self.verbose else 28, max(12, tw // 5))
            overhead = 8 + name_len + 6 + 18
            bar_width = max(10, tw - overhead)

            for i in range(self.window_size):
                sys.stdout.write("\r\033[2K")
                if i in slot_map:
                    fname = slot_map[i]
                    data = self.active_slots[fname]
                    tot = data["tot"]
                    dl = data["dl"]
                    pct = (dl / tot) if tot > 0 else 0.0
                    pct_i = min(100, int(pct * 100))
                    filled = min(bar_width, int(pct * bar_width))
                    bar_fill = "█" * filled + "░" * (bar_width - filled)
                    if color_enabled and pct_i >= 100:
                        bar = _style("\033[92m", bar_fill)
                    elif color_enabled:
                        bar = _style("\033[36m", bar_fill)
                    else:
                        bar = bar_fill

                    dl_mb = dl / 1_048_576
                    tot_mb = tot / 1_048_576 if tot > 0 else 0.0
                    name = self._format_name(fname, maxlen=name_len)
                    pct_s = f"{pct_i:>3}%"
                    
                    # Show package size even in non-verbose if we have it
                    size_str = f" ({dl_mb:.1f}/{tot_mb:.1f} MB)" if tot > 0 else ""
                    
                    line = f"   ▸ {name:<{name_len}}  [{bar}] {pct_s}{size_str}"
                    sys.stdout.write(line[:tw] + "\n")
                else:
                    idle = "   · waiting…" if self.completed_count < self.total_count else "   · —"
                    if self.verbose and self.completed_count < self.total_count:
                        waiting_count = len(self._wait_fifo)
                        if waiting_count > 0:
                            idle = f"   · waiting… ({waiting_count} queued)"
                    sys.stdout.write(_style("\033[90m", idle + "\n") if color_enabled else idle + "\n")

            sys.stdout.write("\r\033[2K")
            
            # Calculate global progress based on bytes if we have totals, otherwise fall back to count
            known_tot = sum(self._file_totals.values())
            if known_tot > 0:
                current_dl = sum(self._file_downloaded.values())
                gpct = current_dl / known_tot
            else:
                done = self.completed_count
                total = self.total_count
                gpct = done / total if total > 0 else 0.0
                
            g_pct_i = min(100, int(gpct * 100))
            gw = max(12, tw - 44)
            gf = min(gw, int(gpct * gw))
            g_bar = "█" * gf + "░" * (gw - gf)
            if color_enabled:
                g_bar = _style("\033[94m", g_bar)
            
            done = self.completed_count
            total = self.total_count
            tail = f"   Overall  [{g_bar}] {g_pct_i:>3}%  ({done}/{total} files done)\n"
            sys.stdout.write(tail)
            sys.stdout.flush()
            self._ever_rendered = True
        finally:
            self._is_rendering = False

    def finish_all(self):
        with self.lock:
            if self.is_tty and self._ever_rendered:
                sys.stdout.write("\n")
            msg = "   ★ Downloads finished."
            print(_style("\033[92m", msg) if color_enabled else msg, flush=True)

    def abort_cleanup(self):
        """If an error stops the batch mid-render, reset the terminal to a sane state."""
        with self.lock:
            if not self.is_tty:
                return
            sys.stdout.write("\033[0m")
            if self._ever_rendered:
                sys.stdout.write("\n" * 2)
            sys.stdout.flush()
            self._ever_rendered = False

    def _format_name(self, filename: str, maxlen: int = 22) -> str:
        name = filename
        for ext in (".pkg.tar.zst", ".pkg.tar.xz", ".sven"):
            if name.endswith(ext):
                name = name[: -len(ext)]
                break
        if len(name) > maxlen:
            return name[: max(1, maxlen - 3)] + "…"
        return name


# ── Real Widgets ──────────────────────────────────────────────

class Spinner:
    """A beautiful, premium, thread-safe Unicode CLI spinner."""
    def __init__(self, message: str = "Processing", style: str = "dots"):
        self.message = message
        # Modern unicode dots animation frame sequence
        self.frames = {
            "dots": ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
            "pulse": ["░░░", "▒░░", "▒▒░", "▒▒▒", "░▒▒", "░░▒", "░░░"],
            "line": ["-", "\\", "|", "/"]
        }.get(style, ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"])
        self.interval = 0.08
        self.running = False
        self.thread = None
        self.lock = threading.Lock()

    def _spin(self):
        idx = 0
        fd = sys.stdout.fileno()
        is_tty = os.isatty(fd)
        if not is_tty:
            print(f"   :: {self.message}...", flush=True)
            return

        # Hide cursor
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

        while True:
            with self.lock:
                if not self.running:
                    break
            frame = self.frames[idx % len(self.frames)]
            colored_frame = f"\033[1;36m{frame}\033[0m"
            sys.stdout.write(f"\r   {colored_frame}  {self.message}...")
            sys.stdout.flush()
            idx += 1
            time.sleep(self.interval)

        # Clear line and restore cursor
        sys.stdout.write("\r\033[2K\033[?25h")
        sys.stdout.flush()

    def start(self):
        with self.lock:
            if self.running:
                return
            self.running = True
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()

    def stop(self, success: bool = True, final_msg: str = None):
        with self.lock:
            if not self.running:
                return
            self.running = False
        if self.thread:
            self.thread.join()
        
        msg = final_msg or self.message
        if success:
            print(f"\r   \033[1;32m✔\033[0m  {msg}")
        else:
            print(f"\r   \033[1;31m✘\033[0m  {msg}")


class ProgressBar:
    """A premium, modern terminal progress bar with colors and ETA."""
    def __init__(self, total: int = 100, prefix: str = "", suffix: str = "", decimals: int = 1, length: int = 30):
        self.total = total or 100
        self.prefix = prefix
        self.suffix = suffix
        self.decimals = decimals
        self.length = length
        self.current = 0
        self.start_time = time.time()
        self.is_tty = os.isatty(sys.stdout.fileno())

    def update(self, current: int, suffix: str = None):
        self.current = current
        if suffix is not None:
            self.suffix = suffix
        self._render()

    def _render(self):
        if not self.is_tty:
            return

        percent = ("{0:." + str(self.decimals) + "f}").format(100 * (self.current / float(self.total)))
        filled_length = int(self.length * self.current // self.total)
        bar_fill = "█" * filled_length + "░" * (self.length - filled_length)
        
        if self.current >= self.total:
            colored_bar = f"\033[32m{bar_fill}\033[0m"
        else:
            colored_bar = f"\033[36m{bar_fill}\033[0m"

        elapsed = time.time() - self.start_time
        speed = self.current / elapsed if elapsed > 0 else 0
        if speed > 0 and self.current < self.total:
            eta = (self.total - self.current) / speed
            eta_str = f" | ETA {eta:.1f}s"
        else:
            eta_str = ""

        sys.stdout.write(f"\r   {self.prefix} [{colored_bar}] {percent}% {self.suffix}{eta_str}")
        sys.stdout.flush()

    def finish(self, success: bool = True, final_msg: str = None):
        if not self.is_tty:
            return
        self.current = self.total
        self._render()
        sys.stdout.write("\n")
        sys.stdout.flush()
