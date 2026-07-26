//! Node tree helpers: HTML parse + Python object deserialization.

use std::str::FromStr;

use pyo3::exceptions::PyTypeError;
use pyo3::prelude::*;
use pyo3::types::{PyAnyMethods, PyDict, PyList, PyString};
use serde::Serialize;
use takumi::prelude::*;

use crate::error::{to_py_err, PyRes};

/// Opaque handle around a Takumi [`Node`] tree.
///
/// Prefer this over raw dicts when the tree was produced by [`from_html`] so
/// styles and presets stay intact without a JSON round-trip.
#[pyclass(name = "NodeTree", module = "pytakumi")]
#[derive(Clone)]
pub struct NodeTree {
  pub(crate) node: Node,
}

#[pymethods]
impl NodeTree {
  /// Human-readable summary (node kind only).
  fn __repr__(&self) -> String {
    let kind = match &self.node.kind {
      NodeKind::Container { children } => format!("container(children={})", children.len()),
      NodeKind::Text(data) => {
        let preview: String = data.text.chars().take(32).collect();
        format!("text({preview:?})")
      }
      NodeKind::Image(_) => "image".to_string(),
      _ => "node".to_string(),
    };
    format!("NodeTree({kind})")
  }
}

/// Parse an HTML fragment into a [`NodeTree`].
#[pyfunction]
#[pyo3(signature = (html, *, max_depth=None, use_presets=true))]
pub fn from_html(html: &str, max_depth: Option<usize>, use_presets: bool) -> PyRes<NodeTree> {
  let depth = max_depth.unwrap_or(DEFAULT_MAX_DEPTH);
  let options = if use_presets {
    FromHtmlOptions::builder().max_depth(depth).build()
  } else {
    FromHtmlOptions::builder()
      .presets(StylePresets::empty())
      .max_depth(depth)
      .build()
  };
  let node = Node::from_html(html, options).map_err(to_py_err)?;
  Ok(NodeTree { node })
}

/// Build a text node.
#[pyfunction]
#[pyo3(signature = (text, *, style=None, tw=None, class_name=None, id=None, lang=None, dir=None, tag_name=None))]
pub fn text_node(
  text: String,
  style: Option<Bound<'_, PyDict>>,
  tw: Option<String>,
  class_name: Option<String>,
  id: Option<String>,
  lang: Option<String>,
  dir: Option<String>,
  tag_name: Option<String>,
) -> PyRes<NodeTree> {
  let node = apply_meta(
    Node::text(text),
    style,
    tw,
    class_name,
    id,
    lang,
    dir,
    tag_name,
  )?;
  Ok(NodeTree { node })
}

/// Build a container node. Children may be [`NodeTree`] instances or dicts.
#[pyfunction]
#[pyo3(signature = (children=None, *, style=None, tw=None, class_name=None, id=None, lang=None, dir=None, tag_name=None))]
pub fn container(
  children: Option<Bound<'_, PyList>>,
  style: Option<Bound<'_, PyDict>>,
  tw: Option<String>,
  class_name: Option<String>,
  id: Option<String>,
  lang: Option<String>,
  dir: Option<String>,
  tag_name: Option<String>,
) -> PyRes<NodeTree> {
  let mut child_nodes = Vec::new();
  if let Some(list) = children {
    for item in list.iter() {
      child_nodes.push(extract_node(&item)?);
    }
  }
  let node = apply_meta(
    Node::container(child_nodes),
    style,
    tw,
    class_name,
    id,
    lang,
    dir,
    tag_name,
  )?;
  Ok(NodeTree { node })
}

/// Build an image node. `src` is a URL string or raw image bytes.
#[pyfunction]
#[pyo3(signature = (src, *, width=None, height=None, style=None, tw=None, class_name=None, id=None, tag_name=None))]
pub fn image_node(
  src: Bound<'_, PyAny>,
  width: Option<f32>,
  height: Option<f32>,
  style: Option<Bound<'_, PyDict>>,
  tw: Option<String>,
  class_name: Option<String>,
  id: Option<String>,
  tag_name: Option<String>,
) -> PyRes<NodeTree> {
  let data = if let Ok(url) = src.extract::<String>() {
    ImageData {
      src: ImageSourceInput::Url(url.into()),
      width,
      height,
    }
  } else if let Ok(bytes) = src.extract::<Vec<u8>>() {
    ImageData {
      src: ImageSourceInput::Buffer(bytes),
      width,
      height,
    }
  } else {
    return Err(PyTypeError::new_err(
      "image src must be a URL string or bytes",
    ));
  };
  let node = apply_meta(
    Node::image(data),
    style,
    tw,
    class_name,
    id,
    None,
    None,
    tag_name,
  )?;
  Ok(NodeTree { node })
}

fn apply_meta(
  mut node: Node,
  style: Option<Bound<'_, PyDict>>,
  tw: Option<String>,
  class_name: Option<String>,
  id: Option<String>,
  lang: Option<String>,
  dir: Option<String>,
  tag_name: Option<String>,
) -> PyRes<Node> {
  if let Some(class_name) = class_name {
    node = node.with_class_name(class_name);
  }
  if let Some(id) = id {
    node = node.with_id(id);
  }
  if let Some(tag_name) = tag_name {
    node = node.with_tag_name(tag_name);
  }
  if let Some(tw) = tw {
    let tw = TailwindValues::from_str(&tw).map_err(to_py_err)?;
    node = node.with_tw(tw);
  }
  if let Some(style) = style {
    let value = py_to_json(&style)?;
    let style: Style = serde_json::from_value(value).map_err(to_py_err)?;
    node = node.with_style(style);
  }
  if let Some(lang) = lang {
    let lang = Lang::parse(&lang).map_err(to_py_err)?;
    node = node.with_lang(lang);
  }
  if let Some(dir) = dir {
    let dir = Direction::from_css_str(&dir).map_err(to_py_err)?;
    node = node.with_dir(dir);
  }
  Ok(node)
}

/// Deserialize a Takumi node from a Python object (dict or [`NodeTree`]).
pub(crate) fn extract_node(obj: &Bound<'_, PyAny>) -> PyRes<Node> {
  if let Ok(tree) = obj.extract::<PyRef<NodeTree>>() {
    return Ok(tree.node.clone());
  }
  let value = py_to_json(obj)?;
  serde_json::from_value(value).map_err(to_py_err)
}

/// Convert a Python object to `serde_json::Value`.
pub(crate) fn py_to_json(obj: &Bound<'_, PyAny>) -> PyRes<serde_json::Value> {
  if obj.is_none() {
    return Ok(serde_json::Value::Null);
  }
  if let Ok(b) = obj.extract::<bool>() {
    return Ok(serde_json::Value::Bool(b));
  }
  if let Ok(i) = obj.extract::<i64>() {
    return Ok(serde_json::json!(i));
  }
  if let Ok(f) = obj.extract::<f64>() {
    if f.fract() == 0.0 && f >= i64::MIN as f64 && f <= i64::MAX as f64 {
      return Ok(serde_json::json!(f as i64));
    }
    return Ok(serde_json::json!(f));
  }
  if let Ok(s) = obj.extract::<String>() {
    return Ok(serde_json::Value::String(s));
  }
  if obj.is_instance_of::<pyo3::types::PyBytes>()
    && let Ok(bytes) = obj.extract::<Vec<u8>>()
  {
    let arr = bytes
      .into_iter()
      .map(|b| serde_json::Value::Number(b.into()))
      .collect();
    return Ok(serde_json::Value::Array(arr));
  }
  if let Ok(list) = obj.downcast::<PyList>() {
    let mut out = Vec::with_capacity(list.len());
    for item in list.iter() {
      out.push(py_to_json(&item)?);
    }
    return Ok(serde_json::Value::Array(out));
  }
  if let Ok(dict) = obj.downcast::<PyDict>() {
    let mut map = serde_json::Map::new();
    for (key, value) in dict.iter() {
      let key = if let Ok(s) = key.extract::<String>() {
        s
      } else if let Ok(s) = key.downcast::<PyString>() {
        s.to_string_lossy().into_owned()
      } else {
        return Err(PyTypeError::new_err(
          "dict keys must be strings when building a Takumi node",
        ));
      };
      map.insert(key, py_to_json(&value)?);
    }
    return Ok(serde_json::Value::Object(map));
  }
  pythonize::depythonize(obj).map_err(to_py_err)
}

/// Convert a serializable Rust value into a Python object.
pub(crate) fn to_py_object<T: Serialize>(py: Python<'_>, value: &T) -> PyRes<PyObject> {
  let obj = pythonize::pythonize(py, value).map_err(to_py_err)?;
  Ok(obj.unbind())
}
