import json
import os
from pathlib import Path

from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = BASE_DIR / "src" / "templates" / "graphic.html"


async def render_graphic(title: str, subtitle: str, category: str, output_path: str):
    """
    Renders a social graphic by loading the local template HTML,
    injecting dynamic content, and taking a high-res screenshot using Playwright.
    """
    # 1. Read local HTML template
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html_content = f.read()

    # 2. Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 3. Launch headless Playwright Chromium session
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1200, "height": 630})

        # Load the raw template HTML content
        await page.set_content(html_content)

        # 4. Inject dynamic content safely into DOM nodes using JSON dumps to escape quotes
        await page.evaluate(f"""() => {{
            document.getElementById('title').innerText = {json.dumps(title)};
            document.getElementById('subtitle').innerText = {json.dumps(subtitle)};
            document.getElementById('category').innerText = {json.dumps(category)};
        }}""")

        # 5. Wait for network connections to idle (ensures Google Fonts and Tailwind CSS are rendered)
        await page.wait_for_load_state("networkidle")
        # Give a small 100ms breathing room for font metrics paint
        await page.wait_for_timeout(100)

        # 6. Capture screenshot
        await page.screenshot(path=output_path, type="png")
        await browser.close()


if __name__ == "__main__":
    import asyncio

    print("Testing local render engine...")
    test_out = os.path.join(BASE_DIR, "posts", "cli_test_graphic.png")

    asyncio.run(
        render_graphic(
            title="10x Faster Inference with New Open-Source Framework",
            subtitle="A breakthrough in deep learning compiled kernels achieves massive speedups.",
            category="GitHub Trending",
            output_path=test_out,
        )
    )
    print(f"Successfully rendered test graphic to {test_out}")
