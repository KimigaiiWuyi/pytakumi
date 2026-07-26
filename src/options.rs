//! Shared render option parsing.

use std::collections::HashMap;
use std::sync::Arc;

use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyAnyMethods, PyDict, PyList};
use takumi::prelude::*;
use takumi_bindings_common::stylesheet;
use takumi_core::resources::image::{ImageCacheMode, ImageSource, ResourceCache};
use takumi_core::style::{FontFamily, Lang, StyleSheet};

use crate::error::{to_py_err, PyRes};
use crate::node::py_to_json;

#[derive(Clone, Copy, PartialEq, Eq)]
pub(crate) enum OutputFormatKind {
  Png,
  Jpeg,
  WebP,
  Ico,
  Raw,
}

impl OutputFormatKind {
  pub(crate) fn parse(value: Option<&str>) -> PyRes<Self> {
    match value.unwrap_or("png").to_ascii_lowercase().as_str() {
      "png" => Ok(Self::Png),
      "jpeg" | "jpg" => Ok(Self::Jpeg),
      "webp" => Ok(Self::WebP),
      "ico" => Ok(Self::Ico),
      "raw" => Ok(Self::Raw),
      other => Err(PyValueError::new_err(format!(
        "unknown output format {other:?}; expected png, jpeg, webp, ico, or raw"
      ))),
    }
  }

  pub(crate) fn into_raster(
    self,
    quality: Option<u8>,
    lossless: Option<bool>,
  ) -> Option<OutputFormat> {
    match self {
      Self::Png => Some(OutputFormat::Png),
      Self::Jpeg => Some(OutputFormat::Jpeg {
        quality: quality.map_or_else(Quality::default, Quality::new),
      }),
      Self::WebP => {
        let lossless = lossless.unwrap_or(quality.is_none());
        if lossless {
          Some(OutputFormat::WebPLossless)
        } else {
          Some(OutputFormat::WebP {
            quality: quality.map_or_else(Quality::default, Quality::new),
          })
        }
      }
      Self::Ico => Some(OutputFormat::Ico),
      Self::Raw => None,
    }
  }
}

#[derive(Clone, Copy)]
pub(crate) enum AnimationFormatKind {
  WebP,
  Apng,
  Gif,
}

impl AnimationFormatKind {
  pub(crate) fn parse(value: Option<&str>) -> PyRes<Self> {
    match value.unwrap_or("webp").to_ascii_lowercase().as_str() {
      "webp" => Ok(Self::WebP),
      "apng" | "png" => Ok(Self::Apng),
      "gif" => Ok(Self::Gif),
      other => Err(PyValueError::new_err(format!(
        "unknown animation format {other:?}; expected webp, apng, or gif"
      ))),
    }
  }

  pub(crate) fn into_animation(
    self,
    quality: Option<u8>,
    lossless: Option<bool>,
  ) -> AnimationFormat {
    match self {
      Self::WebP => {
        let lossless = lossless.unwrap_or(quality.is_none());
        AnimationFormat::WebP(
          AnimatedWebpOptions::builder()
            .lossless(lossless)
            .quality(quality.unwrap_or(75))
            .build(),
        )
      }
      Self::Apng => AnimationFormat::Apng(AnimatedPngOptions::default()),
      Self::Gif => AnimationFormat::Gif(AnimatedGifOptions::default()),
    }
  }
}

pub(crate) fn parse_dithering(value: Option<&str>) -> PyRes<DitheringAlgorithm> {
  match value.unwrap_or("none").to_ascii_lowercase().as_str() {
    "none" => Ok(DitheringAlgorithm::None),
    "ordered-bayer" | "ordered_bayer" | "bayer" => Ok(DitheringAlgorithm::OrderedBayer),
    "floyd-steinberg" | "floyd_steinberg" | "floyd" => Ok(DitheringAlgorithm::FloydSteinberg),
    other => Err(PyValueError::new_err(format!(
      "unknown dithering {other:?}; expected none, ordered-bayer, or floyd-steinberg"
    ))),
  }
}

pub(crate) fn parse_lang(lang: Option<String>) -> PyRes<Option<Lang>> {
  match lang {
    Some(tag) => Ok(Some(Lang::parse(&tag).map_err(to_py_err)?)),
    None => Ok(None),
  }
}

pub(crate) fn parse_font_families(families: Option<Vec<String>>) -> Option<FontFamily> {
  families.map(FontFamily::from_names)
}

pub(crate) fn parse_stylesheets(
  cache: &ResourceCache,
  stylesheets: Option<Vec<String>>,
) -> Arc<StyleSheet> {
  stylesheet(cache, stylesheets, Vec::new())
}

/// Parse `images` as a list of `{src, data, cache?}` dicts or a `src -> bytes` mapping.
pub(crate) fn parse_images(
  cache: &ResourceCache,
  images: Option<Bound<'_, PyAny>>,
) -> PyRes<HashMap<Arc<str>, ImageSource>> {
  let Some(images) = images else {
    return Ok(HashMap::new());
  };

  let mut out = HashMap::new();

  if let Ok(dict) = images.downcast::<PyDict>() {
    for (key, value) in dict.iter() {
      let src: String = key.extract()?;
      let bytes: Vec<u8> = value.extract().map_err(|_| {
        PyTypeError::new_err(format!(
          "images[{src:?}] value must be bytes (raw image data)"
        ))
      })?;
      let decoded = cache
        .get_or_decode(&bytes, ImageCacheMode::Auto)
        .map_err(to_py_err)?;
      out.insert(Arc::from(src), decoded);
    }
    return Ok(out);
  }

  if let Ok(list) = images.downcast::<PyList>() {
    for item in list.iter() {
      let dict = item.downcast::<PyDict>().map_err(|_| {
        PyTypeError::new_err("each images entry must be a dict with src and data")
      })?;
      let src: String = dict
        .get_item("src")?
        .ok_or_else(|| PyValueError::new_err("images entry missing 'src'"))?
        .extract()?;
      let data = dict
        .get_item("data")?
        .ok_or_else(|| PyValueError::new_err("images entry missing 'data'"))?;
      let bytes: Vec<u8> = data
        .extract()
        .map_err(|_| PyTypeError::new_err(format!("images[{src:?}].data must be bytes")))?;
      let mode = match dict.get_item("cache")? {
        Some(v) => {
          let s: String = v.extract()?;
          match s.to_ascii_lowercase().as_str() {
            "auto" => ImageCacheMode::Auto,
            "none" => ImageCacheMode::None,
            other => {
              return Err(PyValueError::new_err(format!(
                "unknown image cache mode {other:?}"
              )));
            }
          }
        }
        None => ImageCacheMode::Auto,
      };
      let decoded = cache.get_or_decode(&bytes, mode).map_err(to_py_err)?;
      out.insert(Arc::from(src), decoded);
    }
    return Ok(out);
  }

  Err(PyTypeError::new_err(
    "images must be a dict[str, bytes] or a list of {src, data} dicts",
  ))
}

pub(crate) fn viewport(width: Option<u32>, height: Option<u32>, dpr: Option<f64>) -> Viewport {
  Viewport::new((width, height)).with_device_pixel_ratio(dpr.unwrap_or(1.0) as f32)
}

/// Animation scene: `{node, duration_ms}` or a 2-tuple `(node, duration_ms)`.
pub(crate) fn parse_scenes(scenes: Bound<'_, PyList>) -> PyRes<Vec<(Node, u32)>> {
  let mut out = Vec::with_capacity(scenes.len());
  for item in scenes.iter() {
    if let Ok(dict) = item.downcast::<PyDict>() {
      let node_obj = dict
        .get_item("node")?
        .ok_or_else(|| PyValueError::new_err("scene missing 'node'"))?;
      let duration: u32 = dict
        .get_item("duration_ms")?
        .or(dict.get_item("durationMs")?)
        .ok_or_else(|| PyValueError::new_err("scene missing 'duration_ms'"))?
        .extract()?;
      out.push((crate::node::extract_node(&node_obj)?, duration));
      continue;
    }
    if let Ok(tuple) = item.extract::<(Bound<'_, PyAny>, u32)>() {
      out.push((crate::node::extract_node(&tuple.0)?, tuple.1));
      continue;
    }
    return Err(PyTypeError::new_err(
      "each scene must be {node, duration_ms} or (node, duration_ms)",
    ));
  }
  Ok(out)
}

#[allow(dead_code)]
pub(crate) fn parse_style_dict(style: Bound<'_, PyDict>) -> PyRes<Style> {
  let value = py_to_json(&style)?;
  serde_json::from_value(value).map_err(to_py_err)
}
