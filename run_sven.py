#!/usr/bin/env python3
import sys
import warnings
from datetime import datetime

# Filter out the annoying requests/urllib3 version warning
warnings.filterwarnings("ignore")

try:
    from sven.cli import main
    main()
except KeyboardInterrupt:
    print("\n:: Aborted by user.")
    sys.exit(0)
except Exception as e:
    import traceback
    
    # Log technical details for support
    try:
        with open("/var/log/sven/error.log", "a") as f:
            f.write(f"\n[{datetime.now()}] CRITICAL: {str(e)}\n")
            traceback.print_exc(file=f)
    except:
        pass

    try:
        from sven.ui.output import print_error_box
        print_error_box(str(e))
    except Exception:
        # Last-resort fallback if sven.ui itself is what's broken
        print(f"\n   SVEN ERROR: {str(e)[:60]}")
        print(f"   Check /var/log/sven/error.log for technical details.")
    sys.exit(1)
