import os

import pytest

from src.renderer import render_graphic


@pytest.mark.asyncio
async def test_render_graphic_creates_file(tmp_path):
    output_png = str(tmp_path / "test_graphic.png")

    title = "Scaling Laws for Autonomous Agents in 2026"
    subtitle = "Discussing the status of automated LinkedIn content pipeline scaling."
    category = "Hacker News"

    # Assert file does not exist initially
    assert not os.path.exists(output_png)

    # Render the graphic
    await render_graphic(title=title, subtitle=subtitle, category=category, output_path=output_png)

    # Assert file was successfully created
    assert os.path.exists(output_png)
    # Check that file has a reasonable size
    assert os.path.getsize(output_png) > 1000
