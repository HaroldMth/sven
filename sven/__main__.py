# ============================================================
#  Sven — Seven OS Package Manager
#  HANS TECH © 2024 — GPL v3
#  __main__.py — entry point
# ============================================================

from .cli import main

if __name__ == "__main__":
    import sys
    from datetime import datetime
    try:
        main()
    except KeyboardInterrupt:
        print("\n:: Aborted by user.")
        sys.exit(0)
    except Exception as e:
        import traceback

        # Log technical details for HANS TECH support
        try:
            with open("/var/log/sven/error.log", "a") as f:
                f.write(f"\n[{datetime.now()}] CRITICAL: {str(e)}\n")
                traceback.print_exc(file=f)
        except:
            pass

        print(f"\n   ╭──────────────────────────────────────────────────╮")
        print(f"   │  SVEN ERROR: {str(e)[:45]}")
        print(f"   ╰──────────────────────────────────────────────────╯")
        print(f"   Check /var/log/sven/error.log for technical details.")
        sys.exit(1)
