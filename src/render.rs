//! `fframes.cli`: the fframes command line (render, frame, strip, inspect, audio, ...).

use std::path::PathBuf;
use std::process::ExitCode;

use clap::Parser;
use fframes::cli::{Cli, NoArgs};
use fframes::{EncoderOptions, RenderOptions};
use fframes_skia_renderer::cli::SkiaRenderers;
use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::media::PyMedia;
use crate::video::PyVideo;

/// The libx264 settings of the fframes examples.
const DEFAULT_CODEC_PARAMS: [(&str, &str); 3] = [
    ("crf", "23"),
    ("preset", "ultrafast"),
    ("tune", "animation"),
];

/// Moves a value that is not `Send` into `Python::detach`. The value is used only by the
/// thread that runs the closure while the caller waits.
struct AssertSend<T>(T);
// SAFETY: see the type documentation; the Python objects inside are reached only through
// `Python::attach`.
unsafe impl<T> Send for AssertSend<T> {}

fn codec_params(params: Option<&Bound<'_, PyDict>>) -> PyResult<Option<Vec<(String, String)>>> {
    let Some(params) = params else {
        return Ok(None);
    };
    params
        .iter()
        .map(|(key, value)| Ok((key.str()?.to_string(), value.str()?.to_string())))
        .collect::<PyResult<Vec<_>>>()
        .map(Some)
}

/// Runs the fframes command line for `video` and returns its exit code.
///
/// `argv` defaults to `sys.argv`. The encoder settings apply to `render`; the defaults are
/// the ones of the fframes examples (libx264, crf 23, preset ultrafast, tune animation).
#[pyfunction]
#[pyo3(signature = (
    video,
    argv = None,
    *,
    media = None,
    load_system_fonts = true,
    default_font = "Arial".to_owned(),
    encoder = Some("libx264".to_owned()),
    codec_params = None,
    tmp_dir = None,
    default_output = None,
))]
#[allow(clippy::too_many_arguments)]
pub fn cli(
    py: Python<'_>,
    video: &Bound<'_, PyAny>,
    argv: Option<Vec<String>>,
    media: Option<PyRef<'_, PyMedia>>,
    load_system_fonts: bool,
    default_font: String,
    encoder: Option<String>,
    codec_params: Option<&Bound<'_, PyDict>>,
    tmp_dir: Option<PathBuf>,
    default_output: Option<PathBuf>,
) -> PyResult<i32> {
    let argv = match argv {
        Some(argv) => argv,
        None => py.import("sys")?.getattr("argv")?.extract()?,
    };
    let args = match Cli::<NoArgs>::try_parse_from(&argv) {
        Ok(args) => args,
        Err(error) => {
            let code = error.exit_code();
            py.detach(|| error.print())
                .map_err(|e| pyo3::exceptions::PyOSError::new_err(e.to_string()))?;
            return Ok(code);
        }
    };
    let video = PyVideo::from_py(video)?;
    let params = self::codec_params(codec_params)?;
    let params: Vec<(&str, &str)> = match &params {
        Some(params) => params
            .iter()
            .map(|(k, v)| (k.as_str(), v.as_str()))
            .collect(),
        None if encoder.as_deref() == Some("libx264") => DEFAULT_CODEC_PARAMS.to_vec(),
        None => Vec::new(),
    };
    let tmp_dir = tmp_dir.unwrap_or_else(|| std::env::temp_dir().join("fframes-python"));
    let options = RenderOptions {
        media: media
            .as_deref()
            .map(|media| media.provider() as &dyn fframes::MediaProvider<'_>),
        load_system_fonts,
        default_font: &default_font,
        tmp_files_directory: Some(&tmp_dir),
        abort_signal: Some(&video.failure.abort),
        video_encoder_options: EncoderOptions {
            preferred_encoder: encoder.as_deref(),
            codec_params: (!params.is_empty()).then_some(params.as_slice()),
            ..Default::default()
        },
        ..Default::default()
    };
    let mut runner = fframes::cli::new(&video, options)
        .args(args)
        .renderers(SkiaRenderers::default());
    if let Some(output) = default_output {
        runner = runner.default_output(output);
    }
    let runner = AssertSend(runner);
    let code = py.detach(move || {
        let runner = runner;
        runner.0.run()
    });
    video.raise_failure()?;
    Ok(if code == ExitCode::SUCCESS { 0 } else { 1 })
}
