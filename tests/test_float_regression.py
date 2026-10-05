"""CSS float layout must not abort the process on degenerate segment boundaries.

Regression for the taffy ``compute/float.rs:subdivide_segment`` assertion. A
float whose bottom edge lands exactly on a segment boundary (``height:66.67px``
plus a fractional ``margin-top``) tripped

    assertion failed: old_segment.y.contains(&divide_at_y) && old_segment.y.start != divide_at_y

and, because pytakumi used to build with ``panic = "abort"``, that killed the
whole interpreter instead of raising. It reproduced on takumi 2.5.0 / taffy
0.11.0 and was fixed by moving the engine submodule to takumi 2.14.0 (taffy
0.14 reworked float layout), **not** by patching taffy -- the assertion is
still in taffy 0.14 as a tripwire, so this test is the guard against a future
engine bump regressing it.

Every render here runs in a **subprocess**: with ``panic = "abort"`` a
regression would abort the pytest process itself and take every other test
result in the run with it. A test for a process-killing bug cannot share the
process. ``panic = "unwind"`` is now the default, so the subprocess also proves
the engine survives a panic rather than dying with it.
"""

from __future__ import annotations

import subprocess
import sys

# Minimised repro: four floats, no text, no flexbox. Fractional heights keep the
# float's bottom edge from landing on a segment boundary by rounding luck.
FLOAT_BOUNDARY_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#fff;width:800px}
</style></head><body>
<div style="width:600px">
<div style="float:left;width:120px;height:66.67px;margin-top:75px;background:#345"></div>
<div style="float:right;width:100px;height:100px;margin-top:20px;clear:right;background:#345"></div>
<div style="float:left;width:80px;height:100px;margin-top:22px;clear:both;background:#345"></div>
<div style="float:right;width:150px;height:80px;margin-top:40px;clear:none;background:#345"></div>
</div>
</body></html>"""


def _render_in_subprocess(html: str) -> subprocess.CompletedProcess[str]:
    """Render ``html`` in a fresh interpreter; return the finished process."""
    return subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-c",
            "import sys, pytakumi\n"
            f"html = {html!r}\n"
            "png = pytakumi.html_to_pic(html, width=800, height=None, format='png',"
            " renderer=pytakumi.Renderer())\n"
            "sys.stdout.write(str(len(png)))\n",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_float_segment_boundary_does_not_abort():
    proc = _render_in_subprocess(FLOAT_BOUNDARY_HTML)
    assert "panicked" not in proc.stderr, f"engine panicked: {proc.stderr}"
    # 0xC0000409 (3221226505) / SIGABRT: panic=abort killed the interpreter
    assert proc.returncode == 0, f"returncode={proc.returncode}\nstderr={proc.stderr}"
    assert proc.stdout.strip().isdigit(), f"no image produced: {proc.stdout!r} {proc.stderr}"


def test_float_still_wraps_text():
    """The fix skips one degenerate subdivision; it must not disable float itself."""
    html = (
        '<div style="width:300px;background:#fff">'
        '<div style="float:left;width:100px;height:60px;background:#345"></div>'
        '<p style="font-size:14px">wrap me around the float</p>'
        "</div>"
    )
    proc = _render_in_subprocess(html)
    assert "panicked" not in proc.stderr, f"engine panicked: {proc.stderr}"
    assert proc.returncode == 0, f"returncode={proc.returncode}\nstderr={proc.stderr}"


def test_clear_variants_render():
    """clear:left/right/both all route through the same segment bookkeeping."""
    for clear in ("left", "right", "both"):
        html = (
            '<div style="width:400px">'
            f'<div style="float:left;width:80px;height:50.5px;clear:{clear};background:#345"></div>'
            '<div style="float:left;width:80px;height:33.33px;clear:left;background:#654"></div>'
            f'<div style="float:right;width:90px;height:77.77px;clear:{clear};background:#456"></div>'
            "</div>"
        )
        proc = _render_in_subprocess(html)
        assert "panicked" not in proc.stderr, f"clear={clear} panicked: {proc.stderr}"
        assert proc.returncode == 0, f"clear={clear} returncode={proc.returncode}\n{proc.stderr}"
