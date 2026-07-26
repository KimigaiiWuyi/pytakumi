//! Python bindings for the Takumi rendering engine.

#![deny(clippy::unwrap_used, clippy::expect_used, clippy::panic)]
#![allow(clippy::too_many_arguments, clippy::useless_conversion)]

mod error;
mod node;
mod options;
mod renderer;

use std::sync::Once;

use pyo3::prelude::*;

use node::{container, from_html, image_node, text_node, NodeTree};
use renderer::{render, render_html, set_glyph_cache_max_bytes, Renderer};

/// Default stack for workers. musl's pthread default is only 128 KiB — far too
/// small for release layout/raster when called from Python threads or Rayon.
const WORKER_STACK_BYTES: usize = 8 * 1024 * 1024;

fn worker_stack_bytes() -> usize {
  std::env::var("RUST_MIN_STACK")
    .ok()
    .and_then(|s| s.parse::<usize>().ok())
    .filter(|&n| n >= 512 * 1024)
    .unwrap_or(WORKER_STACK_BYTES)
}

/// Raise the **process-wide default** pthread stack (Linux glibc + musl).
///
/// Affects subsequent `pthread_create` (including Python threads when they use
/// the platform default). `RUST_MIN_STACK` alone does **not** change those.
#[cfg(target_os = "linux")]
fn ensure_default_pthread_stack(size: usize) {
  // SAFETY: one-time init before other threads; attr lifecycle is contained.
  unsafe {
    let mut attr: libc::pthread_attr_t = std::mem::zeroed();
    if libc::pthread_attr_init(&mut attr) != 0 {
      return;
    }
    // Ignore errors: some environments cap stack size.
    let _ = libc::pthread_attr_setstacksize(&mut attr, size);
    // GNU + musl: default attributes for subsequent pthread_create.
    // Edition 2024 requires `unsafe extern` for FFI blocks.
    #[cfg(any(target_env = "gnu", target_env = "musl"))]
    {
      unsafe extern "C" {
        fn pthread_setattr_default_np(attr: *const libc::pthread_attr_t) -> libc::c_int;
      }
      let _ = pthread_setattr_default_np(&attr);
    }
    let _ = libc::pthread_attr_destroy(&mut attr);
  }
}

#[cfg(not(target_os = "linux"))]
fn ensure_default_pthread_stack(_size: usize) {}

/// Configure stacks for Rayon + any later std::thread, and musl pthread default.
fn ensure_worker_stacks() {
  static INIT: Once = Once::new();
  INIT.call_once(|| {
    let stack = worker_stack_bytes();

    // SAFETY: module import is single-threaded from Python's perspective.
    if std::env::var_os("RUST_MIN_STACK").is_none() {
      unsafe {
        std::env::set_var("RUST_MIN_STACK", stack.to_string());
      }
    }

    ensure_default_pthread_stack(stack);

    // Explicit Rayon pool (ignores "already initialized").
    let _ = rayon::ThreadPoolBuilder::new()
      .stack_size(stack)
      .build_global();
  });
}

/// Takumi native extension module.
///
/// `gil_used = false` declares free-threaded (no-GIL) support: all exposed types
/// are `Send + Sync` with interior synchronization (see `Renderer` / `NodeTree`).
#[pymodule(gil_used = false)]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
  ensure_worker_stacks();

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
  // Module is declared thread-safe (`gil_used = false`); always True.
  m.add("supports_free_threading", true)?;
  Ok(())
}

// Compile-time gate: free-threaded CPython requires Send + Sync pyclasses.
#[allow(dead_code)]
fn _assert_thread_safe() {
  fn assert_send_sync<T: Send + Sync>() {}
  assert_send_sync::<Renderer>();
  assert_send_sync::<NodeTree>();
}
