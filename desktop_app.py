#!/usr/bin/env python3
"""
A320 Checklist Companion - Desktop Application

This launches the checklist companion as a native desktop window.
The web server runs in the background, and the UI is displayed in a native window.
"""

import sys
import threading
import time
import socket
import webview
import uvicorn

from backend.config import config
from backend.main import app as fastapi_app


def get_local_ip():
    """Get the local network IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


def run_server():
    """Run the FastAPI server in a background thread."""
    try:
        uvicorn.run(
            fastapi_app,
            host=config.HOST,
            port=config.PORT,
            log_level="warning",  # Quieter logging for desktop app
        )
    except OSError as e:
        print(f"Error: Could not start server on port {config.PORT}.")
        print(f"  Another instance may already be running. ({e})")
        sys.exit(1)


def wait_for_server(timeout=10):
    """Wait for the server to be ready."""
    import urllib.request
    import urllib.error

    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(f"http://localhost:{config.PORT}/api/state", timeout=1)
            return True
        except (urllib.error.URLError, ConnectionRefusedError):
            time.sleep(0.1)
    return False


def main():
    # Start the server in a background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for server to be ready
    print("Starting A320 Checklist Companion...")
    if not wait_for_server():
        print("Error: Server failed to start")
        sys.exit(1)

    local_ip = get_local_ip()
    print(f"Server running at http://{local_ip}:{config.PORT}")

    # Create the webview window
    window = webview.create_window(
        title="A320 Checklist Companion",
        url=f"http://localhost:{config.PORT}/welcome",
        width=550,
        height=750,
        resizable=True,
        min_size=(400, 600),
        background_color="#fffef9",
    )

    # Start the webview (this blocks until window is closed)
    webview.start()

    print("Application closed")


if __name__ == "__main__":
    main()
