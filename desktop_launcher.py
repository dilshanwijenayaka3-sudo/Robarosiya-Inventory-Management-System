"""Windows desktop entry point: self-contained bundled Flask server + app-style browser."""
import os
import sys
import subprocess
import threading
import webbrowser
from pathlib import Path
from werkzeug.serving import make_server
from app import app

URL = None  # Determined from the actual free local port at startup

def find_browser():
    pf = os.environ.get('PROGRAMFILES', r'C:\Program Files')
    pf86 = os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)')
    local = os.environ.get('LOCALAPPDATA', '')
    paths = [
        Path(pf86) / 'Microsoft' / 'Edge' / 'Application' / 'msedge.exe',
        Path(pf) / 'Microsoft' / 'Edge' / 'Application' / 'msedge.exe',
        Path(pf) / 'Google' / 'Chrome' / 'Application' / 'chrome.exe',
        Path(pf86) / 'Google' / 'Chrome' / 'Application' / 'chrome.exe',
        Path(local) / 'Google' / 'Chrome' / 'Application' / 'chrome.exe',
    ]
    return next((p for p in paths if p.is_file()), None)

def launch_browser(url):
    browser = find_browser()
    if browser:
        try:
            subprocess.Popen([str(browser), '--app=' + url])
            return
        except OSError:
            pass
    webbrowser.open(url)

def main():
    # Use an available port rather than 5000. This prevents an older running
    # copy of Robarosiya from showing up instead of the newly opened app.
    server = make_server('127.0.0.1', 0, app)
    url = 'http://127.0.0.1:' + str(server.server_port) + '/login'
    print('Robarosiya Inventory running at ' + url, flush=True)
    threading.Timer(1, launch_browser, args=(url,)).start()
    try:
        server.serve_forever()
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
