//! `lottie_frame`: one frame of a Lottie file of the media, in its own coordinates.

use pyo3::prelude::*;

use crate::frame::PyContext;
use crate::svgr::PySvgr;

/// The Lottie animation `file` at `seconds` from its start, in its own units, or an empty
/// tree if the media has no such file. `Frame.play_lottie` also places and times it.
#[pyfunction]
pub fn lottie_frame(ctx: &PyContext, file: &str, seconds: f32) -> PyResult<PySvgr> {
    let svgr = ctx
        .get()?
        .get_lottie(file)
        .map_or_else(fframes::Svgr::empty, |lottie| lottie.render_at(seconds));
    Ok(PySvgr {
        nodes: svgr.as_subtree(),
    })
}
