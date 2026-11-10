//! `fframes.cli`: the fframes command line (render, frame, strip, inspect, audio, ...).

use std::path::PathBuf;
use std::process::ExitCode;

use clap::Parser;
use fframes::RenderOptions;
use fframes::cli::{Cli, NoArgs};
use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::cli_options::{self, EncoderSpec};
use crate::media::PyMedia;
use crate::video::PyVideo;

/// The libx264 settings of the fframes examples.
const DEFAULT_CODEC_PARAMS: [(&str, &str); 3] =
    [("crf", "23"), ("preset", "ultrafast"), ("tune", "animation")];

/// Moves a value that is not `Send` into `Python::detach`. The value is used only by the
/// thread that runs the closure while the caller waits.
struct AssertSend<T>(T);
// SAFETY: see the type documentation; the Python objects inside are reached only through
// `Python::attach`.
unsafe impl<T> Send for AssertSend<T> {}

/// Runs the fframes command line for `video` and returns its exit code.
///
/// `argv` defaults to `sys.argv`. The encoder settings apply to `render`; the defaults are
/// the ones of the fframes examples (libx264, crf 23, preset ultrafast, tune animation).
/// `video_options` and `audio_options` set the other `EncoderOptions` fields (pixel_format,
/// sample_format, color_matrix, bitrate, qmin, qmax, qcompress, max_qdiff, gop_size,
/// sample_rate; `audio_options` also encoder and codec_params). `cache_capacity`,
/// `concurrency` and `text_cache_capacity` configure the CPU backend; `renderer` is what
/// renders without `--renderer`, on `gpu_contexts` GPU contexts.
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
    video_options = None,
    audio_options = None,
    cache_capacity = None,
    concurrency = None,
    text_cache_capacity = None,
    renderer = None,
    gpu_contexts = None,
    buffer_queue_size = None,
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
    video_options: Option<&Bound<'_, PyDict>>,
    audio_options: Option<&Bound<'_, PyDict>>,
    cache_capacity: Option<usize>,
    concurrency: Option<usize>,
    text_cache_capacity: Option<usize>,
    renderer: Option<&str>,
    gpu_contexts: Option<usize>,
    buffer_queue_size: Option<usize>,
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
    let params = codec_params.map(|p| cli_options::string_pairs(p.as_any())).transpose()?;
    let params: Vec<(&str, &str)> = match &params {
        Some(params) => params.iter().map(|(k, v)| (k.as_str(), v.as_str())).collect(),
        None if encoder.as_deref() == Some("libx264") => DEFAULT_CODEC_PARAMS.to_vec(),
        None => Vec::new(),
    };
    let video_spec = EncoderSpec::from_py(video_options)?;
    let audio_spec = EncoderSpec::from_py(audio_options)?;
    let audio_params: Vec<(&str, &str)> =
        audio_spec.params.iter().map(|(k, v)| (k.as_str(), v.as_str())).collect();
    let renderers = cli_options::skia(renderer, gpu_contexts, buffer_queue_size)?;
    let options = RenderOptions {
        media: media
            .as_deref()
            .map(|media| media.provider() as &dyn fframes::MediaProvider<'_>),
        load_system_fonts,
        default_font: &default_font,
        // Without `tmp_dir` each render gets its own directory, so renders that run at the
        // same time do not overwrite each other's segments.
        tmp_files_directory: tmp_dir.as_ref(),
        abort_signal: Some(&video.failure.abort),
        video_encoder_options: video_spec.options(encoder.as_deref(), &params),
        audio_encoder_options: audio_spec.options(audio_spec.encoder.as_deref(), &audio_params),
        ..Default::default()
    };
    let mut runner = fframes::cli::new(&video, options)
        .args(args)
        .backend(cli_options::backend(cache_capacity, concurrency, text_cache_capacity))
        .renderers(renderers);
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
