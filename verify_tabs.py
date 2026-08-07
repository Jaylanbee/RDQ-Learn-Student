import subprocess
import time
import sys
from playwright.sync_api import sync_playwright

def run():
    port = sys.argv[1] if len(sys.argv) > 1 else "8000"
    print(f"Starting server on port {port}...")
    server = subprocess.Popen(["uvicorn", "server:app", "--host", "127.0.0.1", "--port", port])
    time.sleep(2) # wait for server to start

    try:
        with sync_playwright() as p:
            print("Launching browser...")
            browser = p.chromium.launch(headless=True)

            print("Testing mobile...")
            page = browser.new_page(viewport={"width": 375, "height": 812})
            page.goto(f"http://127.0.0.1:{port}/")
            page.wait_for_load_state("networkidle")
            page.screenshot(path="verification/screenshots/dashboard_mobile_final.png", full_page=True)

            print("Testing desktop...")
            page2 = browser.new_page(viewport={"width": 1024, "height": 768})
            page2.goto(f"http://127.0.0.1:{port}/")
            page2.wait_for_load_state("networkidle")
            page2.screenshot(path="verification/screenshots/dashboard_desktop_final.png", full_page=True)

            browser.close()
    finally:
        server.terminate()
        server.wait()
        print("Done")

if __name__ == '__main__':
    run()
