#!/usr/bin/env python3
"""
MSFS A320 Checklist Companion - Startup Script

Run this script to start the checklist companion server.
Open http://localhost:8080 (or your PC's IP) on any device to access the UI.
"""

import uvicorn
from backend.config import config


def main():
    print("""
    +-----------------------------------------------------------+
    |         MSFS A320 CHECKLIST COMPANION                     |
    +-----------------------------------------------------------+
    |  Server starting...                                       |
    |                                                           |
    |  Access the checklist UI at:                              |
    |    * http://localhost:{port:<5}                             |
    |    * http://<your-pc-ip>:{port:<5} (from other devices)     |
    |                                                           |
    |  Press Ctrl+C to stop the server                          |
    +-----------------------------------------------------------+
    """.format(port=config.PORT))

    uvicorn.run(
        "backend.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
