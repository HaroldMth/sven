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
        window_size: int = 6,
        verbose: bool = False,
        shared_lock: Optional[threading.Lock] = None,
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

        self._ever_rendered = False
        self._block_lines = self.window_size + 1
        self._last_render_ts = 0.0

        if not self.is_tty:
            print(
                _style("\033[96m", f"   :: Downloading {self.total_count} package(s)…"),
                flush=True,
            )
            return

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
            if downloaded < data["dl"]:
                data["dl"] = downloaded
            elif downloaded > data["dl"]:
                data["dl"] = downloaded
            if total > 0:
                data["tot"] = total

            now = time.monotonic()
            complete = total > 0 and data["dl"] >= total
            if (
                not complete
                and (now - self._last_render_ts) < self._RENDER_MIN_INTERVAL
            ):
                return
            self._last_render_ts = now
            self._render()

    def finish_single(self, filename: str):
        with self.lock:
            if filename in self._finished:
                return
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

                dl_mb = dl / 1_000_000
                tot_mb = tot / 1_000_000 if tot > 0 else 0.0
                name = self._format_name(fname, maxlen=name_len)
                pct_s = f"{pct_i:>3}%"
                if self.verbose:
                    extra = f"  {dl_mb:.1f}/{tot_mb:.1f} MB" if tot > 0 else ""
                else:
                    extra = ""
                line = f"   ▸ {name:<{name_len}}  [{bar}] {pct_s}{extra}"
                sys.stdout.write(line[:tw] + "\n")
            else:
                idle = "   · waiting…" if self.completed_count < self.total_count else "   · —"
                sys.stdout.write(_style("\033[90m", idle + "\n") if color_enabled else idle + "\n")

        sys.stdout.write("\r\033[2K")
        done = self.completed_count
        total = self.total_count
        gpct = done / total if total > 0 else 0.0
        g_pct_i = min(100, int(gpct * 100))
        gw = max(12, tw - 44)
        gf = min(gw, int(gpct * gw))
        g_bar = "█" * gf + "░" * (gw - gf)
        if color_enabled:
            g_bar = _style("\033[94m", g_bar)
        tail = f"   Overall  [{g_bar}] {g_pct_i:>3}%  ({done}/{total} done)\n"
        sys.stdout.write(tail)
        sys.stdout.flush()
        self._ever_rendered = True

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


# ── Compatibility Stubs ────────────────────────────────────────

class ProgressBar:
    def __init__(self, *args, **kwargs):
        pass

    def update(self, *args, **kwargs):
        pass

    def finish(self, *args, **kwargs):
        pass


class Spinner:
    def __init__(self, *args, **kwargs):
        pass

    def start(self, *args, **kwargs):
        pass

    def stop(self, *args, **kwargs):
        pass
