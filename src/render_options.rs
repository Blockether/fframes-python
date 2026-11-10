//! The render settings of `fframes.cli` beyond the codec: the default renderer, the Skia
//! pipeline, the audio master bus and the encoder rate control.

use fframes::cli::Renderer;
use fframes::{AudioMixOptions, EncoderOptions, LimiterOptions};
use fframes_skia_renderer::cli::SkiaRenderers;
use fframes_skia_renderer::{SkiaPipelineConcurrencyPolicy, SkiaPipelineConfig};
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict};

/// The Skia renderers with `renderer` ("cpu", "skia-cpu", "gpu" or None for the CPU backend)
/// as the default of `--renderer`.
pub fn renderers(
    renderer: Option<&str>,
    gpu_contexts: Option<&Bound<'_, PyAny>>,
    buffer_queue_size: Option<usize>,
) -> PyResult<SkiaRenderers> {
    let default = match renderer {
        None => None,
        Some("cpu") => Some(Renderer::Cpu),
        Some("skia-cpu") => Some(Renderer::SkiaCpu),
        Some("gpu") => Some(Renderer::Gpu),
        Some(other) => {
            return Err(PyValueError::new_err(format!(
                "renderer must be 'cpu', 'skia-cpu', 'gpu' or None, not {other:?}"
            )));
        }
    };
    let mut pipeline = SkiaPipelineConfig::default();
    if let Some(contexts) = gpu_contexts.filter(|value| !value.is_none()) {
        pipeline.concurrency_policy = if contexts.extract::<&str>().ok() == Some("max") {
            SkiaPipelineConcurrencyPolicy::MaxPerformance
        } else {
            match contexts.extract::<usize>() {
                Ok(1) => SkiaPipelineConcurrencyPolicy::OnePipeline,
                Ok(n) if n > 1 => SkiaPipelineConcurrencyPolicy::Concurrency(n),
                _ => {
                    return Err(PyValueError::new_err(
                        "gpu_contexts must be 'max' or a positive int",
                    ));
                }
            }
        };
    }
    if let Some(size) = buffer_queue_size {
        pipeline.buffer_queue_size = size;
    }
    Ok(SkiaRenderers { default, pipeline })
}

/// The master bus: `limiter` is None or True (the default limiter), False (no limiter) or a
/// dict with `ceiling_db`, `lookahead_ms` and `release_ms`.
pub fn audio_mix(
    master_gain_db: f32,
    limiter: Option<&Bound<'_, PyAny>>,
) -> PyResult<AudioMixOptions> {
    let limiter = if let Some(limiter) = limiter.filter(|value| !value.is_none()) {
        limiter_options(limiter)?
    } else {
        Some(LimiterOptions::default())
    };
    Ok(AudioMixOptions {
        master_gain_db,
        limiter,
        ..Default::default()
    })
}

fn limiter_options(limiter: &Bound<'_, PyAny>) -> PyResult<Option<LimiterOptions>> {
    Ok(if let Ok(on) = limiter.cast::<PyBool>() {
        on.is_true().then(LimiterOptions::default)
    } else if let Ok(dict) = limiter.cast::<PyDict>() {
        let mut options = LimiterOptions::default();
        for (key, value) in dict.iter() {
            let value: f32 = value.extract()?;
            match key.extract::<&str>()? {
                "ceiling_db" => options.ceiling_db = value,
                "lookahead_ms" => options.lookahead_ms = value,
                "release_ms" => options.release_ms = value,
                other => {
                    return Err(PyValueError::new_err(format!(
                        "unknown limiter option {other:?}"
                    )));
                }
            }
        }
        Some(options)
    } else {
        return Err(PyTypeError::new_err(
            "limiter must be a bool, None or a dict",
        ));
    })
}

/// Sets the rate control of `options` from a dict with `qmin`, `qmax`, `qcompress`,
/// `max_qdiff` and `gop_size`.
pub fn rate_control(
    options: &mut EncoderOptions<'_>,
    values: Option<&Bound<'_, PyDict>>,
) -> PyResult<()> {
    let Some(values) = values else {
        return Ok(());
    };
    for (key, value) in values.iter() {
        match key.extract::<&str>()? {
            "qmin" => options.qmin = value.extract()?,
            "qmax" => options.qmax = value.extract()?,
            "qcompress" => options.qcompress = value.extract()?,
            "max_qdiff" => options.max_qdiff = value.extract()?,
            "gop_size" => options.gop_size = value.extract()?,
            other => {
                return Err(PyValueError::new_err(format!(
                    "unknown rate control option {other:?}"
                )));
            }
        }
    }
    Ok(())
}
