# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  sven/ui/progress.py — UI Spinners and Progress Bars
# ============================================================
import sys
import time
import itertools

class ProgressBar:
    """Format: [##########          ] 4.2 MiB / 8.9 MiB"""
    def __init__(self, filename: str, total_bytes: int, width: int = 20):
        self.filename = filename
        self.total_bytes = total_bytes
        self.width = width
        self.start_time = time.time()
        self.current = 0

    def _format_size(self, size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KiB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MiB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GiB"

    def update(self, current_bytes: int):
        self.current = current_bytes
        if self.total_bytes > 0:
            pct = self.current / self.total_bytes
            filled = int(self.width * pct)
            bar = "#" * filled + " " * (self.width - filled)
            
            cur_fmt = self._format_size(self.current)
            tot_fmt = self._format_size(self.total_bytes)
            
            sys.stdout.write(f"\r   {self.filename[:20]:<20} [{bar}] {cur_fmt} / {tot_fmt}")
            sys.stdout.flush()
        else:
            # Unknown total
            cur_fmt = self._format_size(self.current)
            sys.stdout.write(f"\r   {self.filename[:20]:<20} [ Unknown total  ] {cur_fmt}")
            sys.stdout.flush()

    def finalize(self):
        self.update(self.total_bytes or self.current)
        sys.stdout.write("\n")
        sys.stdout.flush()


class Spinner:
    def __init__(self, message: str):
        self.message = message
        self.spinner = itertools.cycle(['-', '\\', '|', '/'])
        self.active = False
        
    def start(self):
        self.active = True
        sys.stdout.write(f"   {self.message}  ")
        sys.stdout.flush()

    def spin(self):
        if self.active:
            sys.stdout.write(f"\b{next(self.spinner)}")
            sys.stdout.flush()

    def stop(self, success_msg: str = ""):
        if self.active:
            self.active = False
            sys.stdout.write(f"\b \n")
            if success_msg:
                from .output import print_success
                print_success(success_msg)
            sys.stdout.flush()
