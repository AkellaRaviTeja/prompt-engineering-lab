"""Screenshot the sampling explorer (docs/explorer/index.html) for chapter 05.

Sets temperature 0.7 and top_p 0.9, draws 100 tokens, and saves
docs/screenshots/05-explorer.png.
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    page_path = ROOT / "docs" / "explorer" / "index.html"
    out = ROOT / "docs" / "screenshots" / "05-explorer.png"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1100, "height": 900}, color_scheme="light")
        page.goto(page_path.as_uri())
        page.fill("#temp", "0.7")
        page.dispatch_event("#temp", "input")
        page.fill("#p", "0.9")
        page.dispatch_event("#p", "input")
        page.click("#draw")
        rows = page.locator(".row").count()
        page.screenshot(path=str(out), full_page=True)
        browser.close()
    print(f"shoot_explorer: {rows} token rows rendered, saved {out.relative_to(ROOT)}")
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(main())
