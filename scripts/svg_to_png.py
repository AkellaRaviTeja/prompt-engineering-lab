"""Convert the terminal screenshots (SVG from rich) to PNG with headless Chromium.

PNGs render identically everywhere, including GitHub, so READMEs link the PNG.
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    # Optional name filter: `svg_to_png.py 05 06` converts only screenshots starting with 05 or 06.
    prefixes = tuple(sys.argv[1:])
    svgs = sorted(p for p in (ROOT / "docs" / "screenshots").glob("*.svg")
                  if not prefixes or p.name.startswith(prefixes))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(device_scale_factor=1)
        for svg in svgs:
            # Rich sets only a viewBox, so the SVG fills the viewport: size it to the viewBox.
            view_box = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg.read_text()).groups()
            w, h = (math.ceil(float(v)) for v in view_box)
            page.set_viewport_size({"width": w, "height": h})
            page.goto(svg.as_uri())
            # Fira Code draws "<|" and "|>" as arrows; chat templates need them literal.
            page.evaluate(
                "() => { const s = document.createElementNS('http://www.w3.org/2000/svg', 'style');"
                " s.textContent = 'text { font-variant-ligatures: none; }';"
                " document.documentElement.appendChild(s); }"
            )
            page.screenshot(path=str(svg.with_suffix(".png")), animations="disabled",
                            timeout=120000)
        browser.close()
    print(f"svg_to_png: converted {len(svgs)} screenshots")
    return 0 if svgs else 1


if __name__ == "__main__":
    sys.exit(main())
