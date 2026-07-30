from collections.abc import Mapping, Sequence
from typing import Any, Literal, TypedDict

__version__: str

Format = Literal["png", "jpeg", "jpg", "webp", "ico", "raw"]
AnimationFormat = Literal["webp", "apng", "gif", "png"]
Dithering = Literal["none", "ordered-bayer", "floyd-steinberg", "ordered_bayer", "floyd_steinberg"]

class RegisteredFace(TypedDict):
    weight: float
    style: str
    width: float
    index: int

class RegisteredFamily(TypedDict):
    name: str
    faces: list[RegisteredFace]

class NodeTree:
    def __repr__(self) -> str: ...

class Renderer:
    def __init__(self, *, cache_max_bytes: int | None = None) -> None: ...
    def register_font(
        self,
        data: bytes,
        *,
        name: str | None = None,
        weight: float | None = None,
        style: str | None = None,
        subset_of: str | None = None,
        generic: str | None = None,
    ) -> list[RegisteredFamily]: ...
    def render(
        self,
        source: NodeTree | dict[str, Any],
        *,
        width: int | None = None,
        height: int | None = None,
        format: Format = "png",
        quality: int | None = None,
        lossless: bool | None = None,
        stylesheets: Sequence[str] | None = None,
        images: Mapping[str, bytes] | Sequence[Mapping[str, Any]] | None = None,
        draw_debug_border: bool = False,
        device_pixel_ratio: float | None = None,
        time_ms: int | None = None,
        dithering: Dithering | None = None,
        font_families: Sequence[str] | None = None,
        lang: str | None = None,
    ) -> bytes: ...
    def render_svg(
        self,
        source: NodeTree | dict[str, Any],
        *,
        width: int | None = None,
        height: int | None = None,
        stylesheets: Sequence[str] | None = None,
        images: Mapping[str, bytes] | Sequence[Mapping[str, Any]] | None = None,
        time_ms: int | None = None,
        font_families: Sequence[str] | None = None,
        lang: str | None = None,
    ) -> str: ...
    def measure(
        self,
        source: NodeTree | dict[str, Any],
        *,
        width: int | None = None,
        height: int | None = None,
        stylesheets: Sequence[str] | None = None,
        images: Mapping[str, bytes] | Sequence[Mapping[str, Any]] | None = None,
        time_ms: int | None = None,
        font_families: Sequence[str] | None = None,
        lang: str | None = None,
    ) -> dict[str, Any]: ...
    def render_animation(
        self,
        scenes: Sequence[Mapping[str, Any] | tuple[NodeTree | dict[str, Any], int]],
        *,
        width: int,
        height: int,
        fps: int = 30,
        format: AnimationFormat = "webp",
        quality: int | None = None,
        lossless: bool | None = None,
        stylesheets: Sequence[str] | None = None,
        images: Mapping[str, bytes] | Sequence[Mapping[str, Any]] | None = None,
        draw_debug_border: bool = False,
        device_pixel_ratio: float | None = None,
        font_families: Sequence[str] | None = None,
        lang: str | None = None,
    ) -> bytes: ...
    def render_html(
        self,
        html: str,
        *,
        width: int | None = None,
        height: int | None = None,
        format: Format = "png",
        quality: int | None = None,
        lossless: bool | None = None,
        stylesheets: Sequence[str] | None = None,
        images: Mapping[str, bytes] | Sequence[Mapping[str, Any]] | None = None,
        draw_debug_border: bool = False,
        device_pixel_ratio: float | None = None,
        time_ms: int | None = None,
        dithering: Dithering | None = None,
        font_families: Sequence[str] | None = None,
        lang: str | None = None,
        max_depth: int | None = None,
        use_presets: bool = True,
    ) -> bytes: ...

def from_html(
    html: str,
    *,
    max_depth: int | None = None,
    use_presets: bool = True,
) -> NodeTree: ...
def text_node(
    text: str,
    *,
    style: Mapping[str, Any] | None = None,
    tw: str | None = None,
    class_name: str | None = None,
    id: str | None = None,
    lang: str | None = None,
    dir: str | None = None,
    tag_name: str | None = None,
) -> NodeTree: ...
def container(
    children: Sequence[NodeTree | dict[str, Any]] | None = None,
    *,
    style: Mapping[str, Any] | None = None,
    tw: str | None = None,
    class_name: str | None = None,
    id: str | None = None,
    lang: str | None = None,
    dir: str | None = None,
    tag_name: str | None = None,
) -> NodeTree: ...
def image_node(
    src: str | bytes,
    *,
    width: float | None = None,
    height: float | None = None,
    style: Mapping[str, Any] | None = None,
    tw: str | None = None,
    class_name: str | None = None,
    id: str | None = None,
    tag_name: str | None = None,
) -> NodeTree: ...
def set_glyph_cache_max_bytes(bytes: int) -> None: ...
def render(
    source: NodeTree | dict[str, Any],
    *,
    width: int | None = None,
    height: int | None = None,
    format: Format = "png",
    quality: int | None = None,
    lossless: bool | None = None,
    stylesheets: Sequence[str] | None = None,
    images: Mapping[str, bytes] | Sequence[Mapping[str, Any]] | None = None,
    draw_debug_border: bool = False,
    device_pixel_ratio: float | None = None,
    time_ms: int | None = None,
    dithering: Dithering | None = None,
    font_families: Sequence[str] | None = None,
    lang: str | None = None,
    fonts: Sequence[bytes | Mapping[str, Any]] | None = None,
) -> bytes: ...
def render_html(
    html: str,
    *,
    width: int | None = None,
    height: int | None = None,
    format: Format = "png",
    quality: int | None = None,
    lossless: bool | None = None,
    stylesheets: Sequence[str] | None = None,
    images: Mapping[str, bytes] | Sequence[Mapping[str, Any]] | None = None,
    draw_debug_border: bool = False,
    device_pixel_ratio: float | None = None,
    time_ms: int | None = None,
    dithering: Dithering | None = None,
    font_families: Sequence[str] | None = None,
    lang: str | None = None,
    fonts: Sequence[bytes | Mapping[str, Any]] | None = None,
    max_depth: int | None = None,
    use_presets: bool = True,
) -> bytes: ...
def supports_free_threading() -> bool: ...
