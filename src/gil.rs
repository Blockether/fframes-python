//! Runs blocking fframes calls (video decoding) without the GIL, so the other render
//! workers can run Python while one of them waits for a frame.

use pyo3::prelude::*;

/// Moves a value that is not `Send` across `Python::detach`. The closure runs on the
/// calling thread, which waits, and it does not touch Python objects.
struct AssertSend<T>(T);
// SAFETY: see the type documentation.
unsafe impl<T> Send for AssertSend<T> {}

/// `f()` with the GIL released. `f` must not use Python objects.
pub fn detached<T, F: FnOnce() -> T>(py: Python<'_>, f: F) -> T {
    let f = AssertSend(f);
    let out = py.detach(move || {
        let f = f;
        AssertSend((f.0)())
    });
    out.0
}
