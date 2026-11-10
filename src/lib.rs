//! Python bindings for fframes.

mod animation;
mod captions;
mod cli_options;
mod exif;
mod frame;
mod gil;
mod lottie;
mod media;
mod media_api;
mod render;
mod rng;
mod runtime;
mod svgr;
mod synth;
mod timing;
mod values;
mod video;
mod waves;

use pyo3::prelude::*;

#[pymodule]
fn _fframes(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<svgr::PySvgr>()?;
    m.add_class::<svgr::PyTemplate>()?;
    m.add_function(wrap_pyfunction!(svgr::svgr, m)?)?;
    m.add_function(wrap_pyfunction!(svgr::template, m)?)?;
    m.add_class::<values::PyColor>()?;
    m.add_class::<values::PyTransform>()?;
    m.add_class::<values::PyImage>()?;
    m.add_class::<values::PyPath>()?;
    m.add_class::<animation::PyEasing>()?;
    m.add_class::<animation::PyTimeline>()?;
    m.add_function(wrap_pyfunction!(animation::timeline, m)?)?;
    m.add_class::<timing::PyDuration>()?;
    m.add_class::<timing::PyTimestamp>()?;
    m.add_class::<timing::PyAudioTrack>()?;
    m.add_class::<frame::PyFrame>()?;
    m.add_class::<frame::PyContext>()?;
    m.add_class::<media::PyMedia>()?;
    m.add_class::<media_api::PyTextLine>()?;
    m.add_class::<media_api::PyTextLayout>()?;
    m.add_class::<media_api::PyVideoFrame>()?;
    m.add_class::<media_api::PyClip>()?;
    m.add_class::<media_api::PyShader>()?;
    m.add_function(wrap_pyfunction!(
        media_api::center_spectrum_low_frequencies,
        m
    )?)?;
    m.add_class::<runtime::PyAnimationRuntime>()?;
    m.add_class::<captions::PyCaptions>()?;
    m.add_class::<captions::PyCaptionWord>()?;
    m.add_function(wrap_pyfunction!(lottie::lottie_frame, m)?)?;
    m.add_class::<synth::PyNoise>()?;
    m.add_function(wrap_pyfunction!(synth::biquad, m)?)?;
    m.add_function(wrap_pyfunction!(synth::saw, m)?)?;
    m.add_function(wrap_pyfunction!(synth::f32_math, m)?)?;
    m.add_class::<rng::PyRng>()?;
    m.add_function(wrap_pyfunction!(exif::exif, m)?)?;
    m.add_function(wrap_pyfunction!(render::cli, m)?)?;
    m.add_function(wrap_pyfunction!(waves::wave_path, m)?)?;
    Ok(())
}
