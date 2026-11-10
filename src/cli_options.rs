//! Encoder, CPU backend and Skia options of `fframes.cli`, read from keyword arguments.

use std::ffi::CString;

use fframes::cli::Renderer;
use fframes::cpu::CpuRenderingBackend;
use fframes::ffmpeg_sys_fframes::{
    AVPixelFormat, AVSampleFormat, av_get_pix_fmt, av_get_sample_fmt,
};
use fframes::{EncoderOptions, YuvMatrix};
use fframes_skia_renderer::cli::SkiaRenderers;
use fframes_skia_renderer::{SkiaPipelineConcurrencyPolicy, SkiaPipelineConfig};
use pyo3::exceptions::{PyKeyError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyDict;

/// The `EncoderOptions` fields of a `video_options` or `audio_options` dict, owned.
#[derive(Default)]
pub struct EncoderSpec {
    pub encoder: Option<String>,
    pub params: Vec<(String, String)>,
    pixel_format: Option<AVPixelFormat>,
    sample_format: Option<AVSampleFormat>,
    color_matrix: Option<YuvMatrix>,
    bitrate: Option<i64>,
    qmin: Option<i32>,
    qmax: Option<i32>,
    qcompress: Option<f32>,
    max_qdiff: Option<i32>,
    gop_size: Option<i32>,
    sample_rate: Option<usize>,
}

fn c_name(name: &str) -> PyResult<CString> {
    CString::new(name).map_err(|e| PyValueError::new_err(e.to_string()))
}

fn pixel_format(name: &str) -> PyResult<AVPixelFormat> {
    // SAFETY: `av_get_pix_fmt` reads a NUL-terminated string and returns a value.
    let format = unsafe { av_get_pix_fmt(c_name(name)?.as_ptr()) };
    if format == AVPixelFormat::AV_PIX_FMT_NONE {
        return Err(PyValueError::new_err(format!(
            "unknown pixel format {name:?}"
        )));
    }
    Ok(format)
}

fn sample_format(name: &str) -> PyResult<AVSampleFormat> {
    // SAFETY: `av_get_sample_fmt` reads a NUL-terminated string and returns a value.
    let format = unsafe { av_get_sample_fmt(c_name(name)?.as_ptr()) };
    if format == AVSampleFormat::AV_SAMPLE_FMT_NONE {
        return Err(PyValueError::new_err(format!(
            "unknown sample format {name:?}"
        )));
    }
    Ok(format)
}

fn color_matrix(name: &str) -> PyResult<YuvMatrix> {
    match name {
        "bt601" => Ok(YuvMatrix::Bt601),
        "bt709" => Ok(YuvMatrix::Bt709),
        _ => Err(PyValueError::new_err(format!(
            "unknown color matrix {name:?}"
        ))),
    }
}

/// `{"key": value}` pairs as strings, for `codec_params`.
pub fn string_pairs(params: &Bound<'_, PyAny>) -> PyResult<Vec<(String, String)>> {
    params
        .cast::<PyDict>()?
        .iter()
        .map(|(key, value)| Ok((key.str()?.to_string(), value.str()?.to_string())))
        .collect()
}

impl EncoderSpec {
    pub fn from_py(options: Option<&Bound<'_, PyDict>>) -> PyResult<Self> {
        let mut spec = Self::default();
        let Some(options) = options else {
            return Ok(spec);
        };
        for (key, value) in options.iter() {
            let key: String = key.extract()?;
            match key.as_str() {
                "encoder" => spec.encoder = value.extract()?,
                "codec_params" => spec.params = string_pairs(&value)?,
                "pixel_format" => {
                    spec.pixel_format = Some(pixel_format(&value.extract::<String>()?)?)
                }
                "sample_format" => {
                    spec.sample_format = Some(sample_format(&value.extract::<String>()?)?)
                }
                "color_matrix" => {
                    spec.color_matrix = Some(color_matrix(&value.extract::<String>()?)?)
                }
                "bitrate" => spec.bitrate = value.extract()?,
                "qmin" => spec.qmin = Some(value.extract()?),
                "qmax" => spec.qmax = Some(value.extract()?),
                "qcompress" => spec.qcompress = Some(value.extract()?),
                "max_qdiff" => spec.max_qdiff = Some(value.extract()?),
                "gop_size" => spec.gop_size = Some(value.extract()?),
                "sample_rate" => spec.sample_rate = Some(value.extract()?),
                _ => {
                    return Err(PyKeyError::new_err(format!(
                        "unknown encoder option {key:?}"
                    )));
                }
            }
        }
        Ok(spec)
    }

    /// The options, with `encoder` and `params` that the caller resolved.
    pub fn options<'a>(
        &self,
        encoder: Option<&'a str>,
        params: &'a [(&'a str, &'a str)],
    ) -> EncoderOptions<'a> {
        let defaults = EncoderOptions::default();
        EncoderOptions {
            preferred_encoder: encoder,
            codec_params: (!params.is_empty()).then_some(params),
            pixel_format: self.pixel_format.unwrap_or(defaults.pixel_format),
            sample_format: self.sample_format.unwrap_or(defaults.sample_format),
            color_matrix: self.color_matrix.unwrap_or(defaults.color_matrix),
            bitrate: self.bitrate.or(defaults.bitrate),
            qmin: self.qmin.unwrap_or(defaults.qmin),
            qmax: self.qmax.unwrap_or(defaults.qmax),
            qcompress: self.qcompress.unwrap_or(defaults.qcompress),
            max_qdiff: self.max_qdiff.unwrap_or(defaults.max_qdiff),
            gop_size: self.gop_size.unwrap_or(defaults.gop_size),
            sample_rate: self.sample_rate.unwrap_or(defaults.sample_rate),
            ..defaults
        }
    }
}

/// The CPU backend from `cache_capacity`, `concurrency` and `text_cache_capacity`.
pub fn backend(
    cache_capacity: Option<usize>,
    concurrency: Option<usize>,
    text_cache_capacity: Option<usize>,
) -> CpuRenderingBackend {
    let defaults = CpuRenderingBackend::default();
    CpuRenderingBackend {
        cache_capacity: cache_capacity.unwrap_or(defaults.cache_capacity),
        concurrency: concurrency.unwrap_or(defaults.concurrency),
        text_cache_capacity: text_cache_capacity.unwrap_or(defaults.text_cache_capacity),
    }
}

/// The Skia renderers: `renderer` renders without `--renderer` ("cpu", "skia-cpu", "gpu";
/// `None` for the CPU backend), on `gpu_contexts` contexts with `buffer_queue_size` frames.
pub fn skia(
    renderer: Option<&str>,
    gpu_contexts: Option<usize>,
    buffer_queue_size: Option<usize>,
) -> PyResult<SkiaRenderers> {
    let default = match renderer {
        None => None,
        Some("cpu") => Some(Renderer::Cpu),
        Some("skia-cpu") => Some(Renderer::SkiaCpu),
        Some("gpu") => Some(Renderer::Gpu),
        Some(other) => return Err(PyValueError::new_err(format!("unknown renderer {other:?}"))),
    };
    let defaults = SkiaPipelineConfig::default();
    Ok(SkiaRenderers {
        default,
        pipeline: SkiaPipelineConfig {
            buffer_queue_size: buffer_queue_size.unwrap_or(defaults.buffer_queue_size),
            concurrency_policy: gpu_contexts.map_or(
                defaults.concurrency_policy,
                SkiaPipelineConcurrencyPolicy::Concurrency,
            ),
            ..defaults
        },
    })
}
