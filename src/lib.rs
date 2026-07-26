//! Python bindings for the Takumi rendering engine.

#![deny(clippy::unwrap_used, clippy::expect_used, clippy::panic)]
#![allow(clippy::too_many_arguments, clippy::useless_conversion)]

mod error;
mod node;
mod options;
mod renderer;

use pyo3::prelude::*;

use node::{container, from_html, image_node, text_node, NodeTree};
use renderer::{render, render_html, set_glyph_cache_max_bytes, Renderer};

/// Takumi native extension module.
#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
  m.add_class::<Renderer>()?;
  m.add_class::<NodeTree>()?;
  m.add_function(wrap_pyfunction!(from_html, m)?)?;
  m.add_function(wrap_pyfunction!(text_node, m)?)?;
  m.add_function(wrap_pyfunction!(container, m)?)?;
  m.add_function(wrap_pyfunction!(image_node, m)?)?;
  m.add_function(wrap_pyfunction!(render, m)?)?;
  m.add_function(wrap_pyfunction!(render_html, m)?)?;
  m.add_function(wrap_pyfunction!(set_glyph_cache_max_bytes, m)?)?;
  m.add("__version__", env!("CARGO_PKG_VERSION"))?;
  Ok(())
}
