"""Take screenshots of the promptfoo web viewer for chapters 14 and 15.

Start the viewer first (`make eval-view`, port 15500), then run:
    uv run python scripts/shoot_promptfoo.py
It opens the most recent eval, hides the variable columns (they hold file paths) and saves:
    14-promptfoo-matrix.png   the results table, every prompt and provider
    15-promptfoo-matrix.png   the same with pass-rate and metric charts
    15-promptfoo-failures.png the table filtered to failures
    15-promptfoo-nw0419.png   the detail view of one failing cell: prompt and output
    15-promptfoo-nw0419-assertions.png  the same cell: each assertion and its result
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
URL = "http://localhost:15500/eval"


def settle(page: Page, ms: int = 1500) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(ms)


def charts(page: Page, show: bool) -> None:
    want = "Show Charts" if show else "Hide Charts"
    button = page.get_by_role("button", name=want)
    if button.count():
        button.first.click()
        settle(page, 800)


def shot(page: Page, name: str, saved: list[Path]) -> None:
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path))
    saved.append(path)


def main() -> int:
    saved: list[Path] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 2400, "height": 1500})
        page.goto(URL, wait_until="networkidle")
        settle(page, 3000)

        # Hide the variable columns: they are long file paths, and the outputs are the point.
        page.get_by_role("button", name=re.compile(r"^Columns")).click()
        page.get_by_role("button", name="Variables").click()
        page.get_by_role("button", name="Close").last.click()
        settle(page, 800)
        page.evaluate("document.body.style.zoom = '0.7'")

        charts(page, show=False)
        shot(page, "14-promptfoo-matrix", saved)
        charts(page, show=True)
        shot(page, "15-promptfoo-matrix", saved)

        charts(page, show=False)
        page.get_by_role("button", name="Failures", exact=True).click()
        settle(page)
        shot(page, "15-promptfoo-failures", saved)

        page.get_by_role("button", name="All", exact=True).click()
        page.get_by_placeholder("Search...").fill("NW-0419")
        settle(page, 2000)
        page.evaluate("document.body.style.zoom = '1'")
        page.set_viewport_size({"width": 1600, "height": 1200})
        page.get_by_role("button", name="View output and test details").first.click()
        settle(page)
        shot(page, "15-promptfoo-nw0419", saved)
        page.get_by_role("tab", name="Evaluation").click()
        settle(page, 800)
        shot(page, "15-promptfoo-nw0419-assertions", saved)
        browser.close()
    for s in saved:
        print(f"saved {s.relative_to(ROOT)}")
    print(f"shoot_promptfoo: saved {len(saved)} screenshots")
    return 0 if saved else 1


if __name__ == "__main__":
    sys.exit(main())
