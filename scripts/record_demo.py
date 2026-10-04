# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.45"]
# ///
"""Record the README demo GIF by driving the running app in a headless browser.

Start the backend and frontend first (see docs/RUNNING.md) with a working model
key, then from the repository root:

    uv run scripts/record_demo.py                     # writes docs/demo.gif
    uv run scripts/record_demo.py --question "Revenue per month in 2013"

Needs ffmpeg on PATH, and a Chromium for Playwright the first time:

    uv run --with playwright playwright install chromium
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SIZE = {"width": 1280, "height": 800}


def ask(page, question: str, answers_before: int, timeout_s: float) -> None:
    box = page.get_by_label("Question", exact=True)
    box.click()
    box.press_sequentially(question, delay=45)  # visible typing
    page.wait_for_timeout(400)
    box.press("Enter")
    # A turn gets its "Ask again" button once it has finished.
    done = page.get_by_label("Ask again", exact=True).nth(answers_before)
    done.wait_for(timeout=timeout_s * 1000)
    page.wait_for_timeout(1500)  # let the chart animate in


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:3000")
    parser.add_argument("--question", default="Total revenue by country, top 10")
    parser.add_argument("--follow-up", default="Only for 2013")
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "demo.gif")
    parser.add_argument("--width", type=int, default=800, help="GIF width in pixels")
    parser.add_argument("--timeout", type=float, default=120, help="seconds per answer")
    parser.add_argument("--theme", choices=["light", "dark"], default="light")
    args = parser.parse_args()

    if not shutil.which("ffmpeg"):
        print("ffmpeg is needed to make the GIF; install it and try again.", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport=SIZE,
            record_video_dir=tmp,
            record_video_size=SIZE,
            color_scheme=args.theme,
        )
        page = context.new_page()
        try:
            page.goto(args.url)
            page.get_by_label("Question", exact=True).wait_for(timeout=30_000)
            page.wait_for_timeout(1200)

            ask(page, args.question, 0, args.timeout)
            corrected = page.get_by_text("Self-corrected after")
            if corrected.count():  # show the self-correction when it happens
                corrected.first.click()
                page.wait_for_timeout(2500)
            if args.follow_up:
                ask(page, args.follow_up, 1, args.timeout)
            page.wait_for_timeout(1500)
        except PlaywrightTimeout:
            page.screenshot(path=str(Path(tmp).parent / "askdb-demo-failed.png"))
            print(
                "Timed out waiting for an answer. Is the app running with a working model "
                f"key? Screenshot: {Path(tmp).parent / 'askdb-demo-failed.png'}",
                file=sys.stderr,
            )
            return 1
        finally:
            video = page.video
            context.close()  # finishes writing the video
            browser.close()

        webm = video.path()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        palette = (
            f"fps=10,scale={args.width}:-1:flags=lanczos,"
            "split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer"
        )
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm), "-vf", palette, str(args.out)],
            check=True,
        )
    size_mb = args.out.stat().st_size / 1e6
    print(f"Wrote {args.out} ({size_mb:.1f} MB)")
    if size_mb > 10:
        print("That's large for a README; try --width 640.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
