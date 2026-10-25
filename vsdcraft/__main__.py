"""
VSDCraft Linux - Main Entry Point
"""

import sys
import argparse
import logging
import signal

def main():
    parser = argparse.ArgumentParser(description="VSDCraft Linux - Stream Dock N3 Controller")
    parser.add_argument("--mock", action="store_true", help="Run in mock/virtual mode without physical USB hardware")
    parser.add_argument("--daemon", action="store_true", help="Run in background daemon mode (headless without GUI)")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    if args.daemon:
        from .daemon import run_daemon
        run_daemon(is_mock=args.mock)
    else:
        from .gui.app import VSDCraftApp
        app = VSDCraftApp(is_mock=args.mock)
        app.mainloop()

if __name__ == "__main__":
    main()
