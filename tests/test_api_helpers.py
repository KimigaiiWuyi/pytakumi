from __future__ import annotations

import struct

from pytakumi import html_to_pic, md_to_pic, text_to_pic


def _png_size(data: bytes) -> tuple[int, int]:
    return struct.unpack(">II", data[16:24])


def test_html_to_pic():
    png = html_to_pic(
        """
        <div style="width:100%;height:100%;display:flex;align-items:center;
                    justify-content:center;background:#0f172a;color:white;
                    font-size:36px">Hello API</div>
        """,
        width=400,
        height=200,
    )
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert _png_size(png) == (400, 200)


def test_text_to_pic_dark_and_light():
    dark = text_to_pic(
        "第一行\n第二行内容",
        title="文本卡片",
        eyebrow="NOTICE",
        footer="takumi text_to_pic",
        theme="dark",
        width=640,
        height=360,
    )
    light = text_to_pic("hello", theme="light", width=400, height=240)
    assert dark[:8] == b"\x89PNG\r\n\x1a\n"
    assert light[:8] == b"\x89PNG\r\n\x1a\n"
    assert _png_size(dark) == (640, 360)


def test_md_to_pic_github_style():
    md = """# Takumi

Lightweight **HTML** renderer.

## Features

- no browser
- fast

```python
print("hi")
```

| A | B |
| - | - |
| 1 | 2 |
"""
    png = md_to_pic(md, width=720)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    w, h = _png_size(png)
    assert w == 720
    assert h > 100

    dark = md_to_pic("# Dark\n\nok", width=500, height=300, dark=True)
    assert _png_size(dark) == (500, 300)
