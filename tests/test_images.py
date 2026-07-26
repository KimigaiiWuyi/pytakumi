"""Image embedding and cache options."""

from __future__ import annotations

from helpers import assert_near_rgb, assert_png, raw_pixel, solid_png_bytes


def test_images_dict_by_src(renderer, red_png_bytes):
    html = """
    <div style="width:100%;height:100%;background:#000">
      <img src="mem://red" width="100" height="100" style="width:100%;height:100%;display:block"/>
    </div>
    """
    raw = renderer.render_html(
        html,
        width=64,
        height=64,
        format="raw",
        images={"mem://red": red_png_bytes},
    )
    # Most of the frame should be red from the stretched image
    assert_near_rgb(raw_pixel(raw, 64, 32, 32), (255, 0, 0), tol=15)


def test_images_list_entries(renderer, green_png_bytes):
    html = '<img src="g" style="width:100%;height:100%;display:block"/>'
    png = renderer.render_html(
        html,
        width=40,
        height=40,
        images=[{"src": "g", "data": green_png_bytes, "cache": "auto"}],
    )
    assert_png(png, width=40, height=40)


def test_image_node_with_bytes(renderer, red_png_bytes):
    from pytakumi import container, image_node

    root = container(
        [image_node(red_png_bytes, width=64, height=64)],
        style={"width": "100%", "height": "100%", "background": "#000"},
    )
    png = renderer.render(root, width=64, height=64)
    assert_png(png, width=64, height=64)


def test_data_url_img_in_html(renderer):
    # Small red PNG as data URL
    data = solid_png_bytes(8, 8, (255, 0, 0, 255))
    import base64

    b64 = base64.b64encode(data).decode("ascii")
    html = f'<img src="data:image/png;base64,{b64}" style="width:100%;height:100%;display:block"/>'
    raw = renderer.render_html(html, width=32, height=32, format="raw")
    assert_near_rgb(raw_pixel(raw, 32, 16, 16), (255, 0, 0), tol=20)
