//! Python `Renderer` class and module-level convenience functions.

use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use arc_swap::ArcSwap;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyList};
use takumi::prelude::*;
use takumi::{measure as measure_layout, render as render_tree, write_animation, write_image};
use takumi_bindings_common::{build_font_resource, default_fonts};
use takumi_core::resources::glyph_cache;
use takumi_core::resources::image::{ImageSource, ResourceCache};
use takumi_core::style::{FontFamily, FontStyle as CssFontStyle, FromCssStr, Lang, StyleSheet};

use crate::error::{to_py_err, PyRes};
use crate::node::{extract_node, from_html, to_py_object};
use crate::options::{
  parse_dithering, parse_font_families, parse_images, parse_lang, parse_scenes, parse_stylesheets,
  viewport, AnimationFormatKind, OutputFormatKind,
};

pub(crate) struct RendererState {
  fonts: ArcSwap<Fonts>,
  font_write: Mutex<()>,
  resource_cache: ResourceCache,
}

/// Reusable Takumi renderer with font and resource caches.
///
/// `frozen`: no `&mut self` methods; concurrent Python threads share one instance
/// safely via `Arc` + `ArcSwap` (fonts) + `Mutex` (font registration) + the engine's
/// thread-safe `ResourceCache` / glyph cache. Safe under free-threaded CPython.
#[pyclass(frozen, name = "Renderer", module = "pytakumi")]
pub struct Renderer {
  state: Arc<RendererState>,
}

#[pymethods]
impl Renderer {
  /// Create a renderer.
  ///
  /// Parameters
  /// ----------
  /// cache_max_bytes:
  ///     Shared budget for decoded images, SVG rasters, and parsed stylesheets.
  ///     Defaults to 16 MiB. Pass ``0`` to disable caching.
  #[new]
  #[pyo3(signature = (*, cache_max_bytes=None))]
  fn new(cache_max_bytes: Option<u64>) -> PyRes<Self> {
    let fonts = default_fonts().map_err(to_py_err)?;
    let resource_cache = match cache_max_bytes {
      Some(bytes) => ResourceCache::new(bytes),
      None => ResourceCache::default(),
    };
    Ok(Self {
      state: Arc::new(RendererState {
        fonts: ArcSwap::from_pointee(fonts),
        font_write: Mutex::new(()),
        resource_cache,
      }),
    })
  }

  /// Register a font from raw bytes (TTF / OTF / WOFF / WOFF2 / TTC).
  ///
  /// Returns a list of family dicts: ``{"name", "faces": [{"weight","style","width","index"}]}``.
  #[pyo3(signature = (data, *, name=None, weight=None, style=None, subset_of=None, generic=None))]
  fn register_font(
    &self,
    py: Python<'_>,
    data: Bound<'_, PyBytes>,
    name: Option<String>,
    weight: Option<f32>,
    style: Option<String>,
    subset_of: Option<String>,
    generic: Option<String>,
  ) -> PyRes<PyObject> {
    let bytes = data.as_bytes().to_vec();
    let css_style = match style {
      Some(s) => Some(CssFontStyle::from_css_str(&s).map_err(to_py_err)?),
      None => None,
    };

    let families = py.allow_threads(|| {
      let resource = build_font_resource(
        &bytes,
        name,
        weight,
        css_style,
        subset_of,
        generic,
      )
      .map_err(|e| e.to_string())?;

      // Decode off the write lock first when possible.
      let resource = resource.into_resolved().map_err(|e| e.to_string())?;

      let _guard = self
        .state
        .font_write
        .lock()
        .map_err(|_| "font registry lock poisoned".to_string())?;
      let mut fonts = (*self.state.fonts.load_full()).clone();
      let registered = fonts.register(resource).map_err(|e| e.to_string())?;
      self.state.fonts.store(Arc::new(fonts));
      Ok::<_, String>(registered)
    })
    .map_err(to_py_err)?;

    to_py_object(py, &families)
  }

  /// Render a node tree (dict or :class:`NodeTree`) to image bytes.
  #[pyo3(signature = (
    source,
    *,
    width=None,
    height=None,
    format="png",
    quality=None,
    lossless=None,
    stylesheets=None,
    images=None,
    draw_debug_border=false,
    device_pixel_ratio=None,
    time_ms=None,
    dithering=None,
    font_families=None,
    lang=None,
  ))]
  #[allow(clippy::too_many_arguments)]
  fn render(
    &self,
    py: Python<'_>,
    source: Bound<'_, PyAny>,
    width: Option<u32>,
    height: Option<u32>,
    format: &str,
    quality: Option<u8>,
    lossless: Option<bool>,
    stylesheets: Option<Vec<String>>,
    images: Option<Bound<'_, PyAny>>,
    draw_debug_border: bool,
    device_pixel_ratio: Option<f64>,
    time_ms: Option<i64>,
    dithering: Option<&str>,
    font_families: Option<Vec<String>>,
    lang: Option<String>,
  ) -> PyRes<PyObject> {
    let node = extract_node(&source)?;
    let format = OutputFormatKind::parse(Some(format))?;
    let dithering = parse_dithering(dithering)?;
    let lang = parse_lang(lang)?;
    let font_families = parse_font_families(font_families);
    let images = parse_images(&self.state.resource_cache, images)?;
    let sheet = parse_stylesheets(&self.state.resource_cache, stylesheets);
    let vp = viewport(width, height, device_pixel_ratio);
    let time_ms = time_ms.unwrap_or(0).max(0) as u64;

    let state = Arc::clone(&self.state);
    let bytes = py
      .allow_threads(|| {
        render_bytes(
          &state,
          node,
          vp,
          format,
          quality,
          lossless,
          sheet,
          images,
          draw_debug_border,
          time_ms,
          dithering,
          font_families,
          lang,
        )
      })
      .map_err(to_py_err)?;

    Ok(PyBytes::new(py, &bytes).into_any().unbind())
  }

  /// Render a node tree to an SVG document string.
  #[pyo3(signature = (
    source,
    *,
    width=None,
    height=None,
    stylesheets=None,
    images=None,
    time_ms=None,
    font_families=None,
    lang=None,
  ))]
  #[allow(clippy::too_many_arguments)]
  fn render_svg(
    &self,
    py: Python<'_>,
    source: Bound<'_, PyAny>,
    width: Option<u32>,
    height: Option<u32>,
    stylesheets: Option<Vec<String>>,
    images: Option<Bound<'_, PyAny>>,
    time_ms: Option<i64>,
    font_families: Option<Vec<String>>,
    lang: Option<String>,
  ) -> PyRes<String> {
    let node = extract_node(&source)?;
    let lang = parse_lang(lang)?;
    let font_families = parse_font_families(font_families);
    let images = parse_images(&self.state.resource_cache, images)?;
    let sheet = parse_stylesheets(&self.state.resource_cache, stylesheets);
    let vp = viewport(width, height, None);
    let time_ms = time_ms.unwrap_or(0).max(0) as u64;
    let state = Arc::clone(&self.state);

    py.allow_threads(|| {
      let fonts = state.fonts.load();
      let options = SvgOptions::builder()
        .viewport(vp)
        .node(node)
        .fonts(&fonts)
        .images(images)
        .stylesheet(sheet)
        .time_ms(time_ms)
        .font_families(font_families)
        .lang(lang)
        .build();
      takumi::render_svg(options).map_err(|e| e.to_string())
    })
    .map_err(to_py_err)
  }

  /// Measure layout without rasterizing. Returns a nested dict.
  #[pyo3(signature = (
    source,
    *,
    width=None,
    height=None,
    stylesheets=None,
    images=None,
    time_ms=None,
    font_families=None,
    lang=None,
  ))]
  #[allow(clippy::too_many_arguments)]
  fn measure(
    &self,
    py: Python<'_>,
    source: Bound<'_, PyAny>,
    width: Option<u32>,
    height: Option<u32>,
    stylesheets: Option<Vec<String>>,
    images: Option<Bound<'_, PyAny>>,
    time_ms: Option<i64>,
    font_families: Option<Vec<String>>,
    lang: Option<String>,
  ) -> PyRes<PyObject> {
    let node = extract_node(&source)?;
    let lang = parse_lang(lang)?;
    let font_families = parse_font_families(font_families);
    let images = parse_images(&self.state.resource_cache, images)?;
    let sheet = parse_stylesheets(&self.state.resource_cache, stylesheets);
    let vp = viewport(width, height, None);
    let time_ms = time_ms.unwrap_or(0).max(0) as u64;
    let state = Arc::clone(&self.state);

    let measured = py
      .allow_threads(|| {
        let fonts = state.fonts.load();
        let options = RenderOptions::builder()
          .viewport(vp)
          .node(node)
          .fonts(&fonts)
          .images(images)
          .stylesheet(sheet)
          .time_ms(time_ms)
          .font_families(font_families)
          .lang(lang)
          .build();
        measure_layout(options).map_err(|e| e.to_string())
      })
      .map_err(to_py_err)?;

    to_py_object(py, &measured)
  }

  /// Render a sequential animation (WebP / APNG / GIF).
  ///
  /// ``scenes`` is a list of ``{node, duration_ms}`` dicts or ``(node, duration_ms)`` tuples.
  #[pyo3(signature = (
    scenes,
    *,
    width,
    height,
    fps=30,
    format="webp",
    quality=None,
    lossless=None,
    stylesheets=None,
    images=None,
    draw_debug_border=false,
    device_pixel_ratio=None,
    font_families=None,
    lang=None,
  ))]
  #[allow(clippy::too_many_arguments)]
  fn render_animation(
    &self,
    py: Python<'_>,
    scenes: Bound<'_, PyList>,
    width: u32,
    height: u32,
    fps: u32,
    format: &str,
    quality: Option<u8>,
    lossless: Option<bool>,
    stylesheets: Option<Vec<String>>,
    images: Option<Bound<'_, PyAny>>,
    draw_debug_border: bool,
    device_pixel_ratio: Option<f64>,
    font_families: Option<Vec<String>>,
    lang: Option<String>,
  ) -> PyRes<PyObject> {
    let scene_nodes = parse_scenes(scenes)?;
    let format = AnimationFormatKind::parse(Some(format))?.into_animation(quality, lossless);
    let lang = parse_lang(lang)?;
    let font_families = parse_font_families(font_families);
    let images = parse_images(&self.state.resource_cache, images)?;
    let sheet = parse_stylesheets(&self.state.resource_cache, stylesheets);
    let vp = viewport(Some(width), Some(height), device_pixel_ratio);
    let state = Arc::clone(&self.state);

    let bytes = py
      .allow_threads(|| {
        let fonts = state.fonts.load();
        let mut sequential = Vec::with_capacity(scene_nodes.len());
        for (node, duration_ms) in scene_nodes {
          let options = RenderOptions::builder()
            .viewport(vp)
            .node(node)
            .fonts(&fonts)
            .images(images.clone())
            .stylesheet(Arc::clone(&sheet))
            .draw_debug_border(draw_debug_border)
            .font_families(font_families.clone())
            .lang(lang)
            .build();
          sequential.push(SequentialScene::builder().options(options).duration_ms(duration_ms).build());
        }
        let mut buffer = Vec::new();
        write_animation(&sequential, fps, format, &mut buffer).map_err(|e| e.to_string())?;
        Ok::<_, String>(buffer)
      })
      .map_err(to_py_err)?;

    Ok(PyBytes::new(py, &bytes).into_any().unbind())
  }

  /// Parse HTML and render in one call.
  #[pyo3(signature = (
    html,
    *,
    width=None,
    height=None,
    format="png",
    quality=None,
    lossless=None,
    stylesheets=None,
    images=None,
    draw_debug_border=false,
    device_pixel_ratio=None,
    time_ms=None,
    dithering=None,
    font_families=None,
    lang=None,
    max_depth=None,
    use_presets=true,
  ))]
  #[allow(clippy::too_many_arguments)]
  fn render_html(
    &self,
    py: Python<'_>,
    html: &str,
    width: Option<u32>,
    height: Option<u32>,
    format: &str,
    quality: Option<u8>,
    lossless: Option<bool>,
    stylesheets: Option<Vec<String>>,
    images: Option<Bound<'_, PyAny>>,
    draw_debug_border: bool,
    device_pixel_ratio: Option<f64>,
    time_ms: Option<i64>,
    dithering: Option<&str>,
    font_families: Option<Vec<String>>,
    lang: Option<String>,
    max_depth: Option<usize>,
    use_presets: bool,
  ) -> PyRes<PyObject> {
    let tree = from_html(html, max_depth, use_presets)?;
    self.render(
      py,
      Bound::new(py, tree)?.into_any(),
      width,
      height,
      format,
      quality,
      lossless,
      stylesheets,
      images,
      draw_debug_border,
      device_pixel_ratio,
      time_ms,
      dithering,
      font_families,
      lang,
    )
  }
}

#[allow(clippy::too_many_arguments)]
fn render_bytes(
  state: &RendererState,
  node: Node,
  vp: Viewport,
  format: OutputFormatKind,
  quality: Option<u8>,
  lossless: Option<bool>,
  sheet: Arc<StyleSheet>,
  images: HashMap<Arc<str>, ImageSource>,
  draw_debug_border: bool,
  time_ms: u64,
  dithering: DitheringAlgorithm,
  font_families: Option<FontFamily>,
  lang: Option<Lang>,
) -> std::result::Result<Vec<u8>, String> {
  let fonts = state.fonts.load();
  let image = render_tree(
    RenderOptions::builder()
      .viewport(vp)
      .node(node)
      .fonts(&fonts)
      .images(images)
      .stylesheet(sheet)
      .time_ms(time_ms)
      .dithering(dithering)
      .font_families(font_families)
      .lang(lang)
      .draw_debug_border(draw_debug_border)
      .build(),
  )
  .map_err(|e| e.to_string())?;

  if format == OutputFormatKind::Raw {
    return Ok(image.into_raw());
  }

  let mut buffer = Vec::new();
  let output_format = format
    .into_raster(quality, lossless)
    .ok_or_else(|| "raw format has no encoder".to_string())?;
  write_image(&image, &mut buffer, output_format).map_err(|e| e.to_string())?;
  Ok(buffer)
}

/// Set the process-wide glyph cache budget (bytes). Call before the first render.
/// ``0`` disables caching. Default is 8 MiB.
#[pyfunction]
pub fn set_glyph_cache_max_bytes(bytes: u64) {
  glyph_cache::set_glyph_cache_max_bytes(bytes as usize);
}

/// Module-level render using a process-local default renderer.
#[pyfunction]
#[pyo3(signature = (
  source,
  *,
  width=None,
  height=None,
  format="png",
  quality=None,
  lossless=None,
  stylesheets=None,
  images=None,
  draw_debug_border=false,
  device_pixel_ratio=None,
  time_ms=None,
  dithering=None,
  font_families=None,
  lang=None,
  fonts=None,
))]
#[allow(clippy::too_many_arguments)]
pub fn render(
  py: Python<'_>,
  source: Bound<'_, PyAny>,
  width: Option<u32>,
  height: Option<u32>,
  format: &str,
  quality: Option<u8>,
  lossless: Option<bool>,
  stylesheets: Option<Vec<String>>,
  images: Option<Bound<'_, PyAny>>,
  draw_debug_border: bool,
  device_pixel_ratio: Option<f64>,
  time_ms: Option<i64>,
  dithering: Option<&str>,
  font_families: Option<Vec<String>>,
  lang: Option<String>,
  fonts: Option<Bound<'_, PyList>>,
) -> PyRes<PyObject> {
  let renderer = Renderer::new(None)?;
  if let Some(fonts) = fonts {
    for item in fonts.iter() {
      register_font_item(&renderer, py, &item)?;
    }
  }
  renderer.render(
    py,
    source,
    width,
    height,
    format,
    quality,
    lossless,
    stylesheets,
    images,
    draw_debug_border,
    device_pixel_ratio,
    time_ms,
    dithering,
    font_families,
    lang,
  )
}

/// Module-level HTML render.
#[pyfunction]
#[pyo3(signature = (
  html,
  *,
  width=None,
  height=None,
  format="png",
  quality=None,
  lossless=None,
  stylesheets=None,
  images=None,
  draw_debug_border=false,
  device_pixel_ratio=None,
  time_ms=None,
  dithering=None,
  font_families=None,
  lang=None,
  fonts=None,
  max_depth=None,
  use_presets=true,
))]
#[allow(clippy::too_many_arguments)]
pub fn render_html(
  py: Python<'_>,
  html: &str,
  width: Option<u32>,
  height: Option<u32>,
  format: &str,
  quality: Option<u8>,
  lossless: Option<bool>,
  stylesheets: Option<Vec<String>>,
  images: Option<Bound<'_, PyAny>>,
  draw_debug_border: bool,
  device_pixel_ratio: Option<f64>,
  time_ms: Option<i64>,
  dithering: Option<&str>,
  font_families: Option<Vec<String>>,
  lang: Option<String>,
  fonts: Option<Bound<'_, PyList>>,
  max_depth: Option<usize>,
  use_presets: bool,
) -> PyRes<PyObject> {
  let renderer = Renderer::new(None)?;
  if let Some(fonts) = fonts {
    for item in fonts.iter() {
      register_font_item(&renderer, py, &item)?;
    }
  }
  renderer.render_html(
    py,
    html,
    width,
    height,
    format,
    quality,
    lossless,
    stylesheets,
    images,
    draw_debug_border,
    device_pixel_ratio,
    time_ms,
    dithering,
    font_families,
    lang,
    max_depth,
    use_presets,
  )
}

fn register_font_item(renderer: &Renderer, py: Python<'_>, item: &Bound<'_, PyAny>) -> PyRes<()> {
  // bytes, or {"data": bytes, "name"?: str, ...}
  if let Ok(data) = item.downcast::<PyBytes>() {
    renderer.register_font(py, data.clone(), None, None, None, None, None)?;
    return Ok(());
  }
  if let Ok(dict) = item.downcast::<pyo3::types::PyDict>() {
    let data = dict
      .get_item("data")?
      .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("font dict missing 'data'"))?;
    let data = data.downcast::<PyBytes>().map_err(|_| {
      pyo3::exceptions::PyTypeError::new_err("font dict 'data' must be bytes")
    })?;
    let name = dict
      .get_item("name")?
      .map(|v| v.extract::<String>())
      .transpose()?;
    let weight = dict
      .get_item("weight")?
      .map(|v| v.extract::<f32>())
      .transpose()?;
    let style = dict
      .get_item("style")?
      .map(|v| v.extract::<String>())
      .transpose()?;
    let subset_of = dict
      .get_item("subset_of")?
      .or(dict.get_item("subsetOf")?)
      .map(|v| v.extract::<String>())
      .transpose()?;
    let generic = dict
      .get_item("generic")?
      .map(|v| v.extract::<String>())
      .transpose()?;
    renderer.register_font(py, data.clone(), name, weight, style, subset_of, generic)?;
    return Ok(());
  }
  Err(pyo3::exceptions::PyTypeError::new_err(
    "fonts entries must be bytes or {data, name?, weight?, style?, subset_of?, generic?}",
  ))
}

