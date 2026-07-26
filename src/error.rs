//! Error mapping from Takumi into Python exceptions.

use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;

/// Convert any displayable error into a Python exception.
pub(crate) fn to_py_err(err: impl std::fmt::Display) -> PyErr {
  let message = err.to_string();
  if message.contains("exceeded")
    || message.contains("invalid")
    || message.contains("Unknown")
    || message.contains("must have")
    || message.contains("unsupported")
    || message.contains("Unsupported")
    || message.contains("parse")
    || message.contains("Parse")
  {
    PyValueError::new_err(message)
  } else {
    PyRuntimeError::new_err(message)
  }
}

/// Result alias that maps into `PyErr`.
pub(crate) type PyRes<T> = Result<T, PyErr>;
