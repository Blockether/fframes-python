//! Media that a frame reads: text layout, video frames, clips, audio spectra, subtitles,
//! Lottie animations and shaders.

use std::collections::HashSet;
use std::sync::{Arc, Mutex, PoisonError};

use fframes::{
    BreakLinesOpts, FontQuery, FontStretch, FontStyle, SampleSize, Shader, ShaderUniformValue,
    ShaderUniforms, TextAlign, TextOverflow, WindowFunction,
};
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyFloat, PyInt, PyTuple};

use crate::frame::PyFrame;
use crate::values::{PyColor, PyImage};

/// A `'static` copy of `value`. Each distinct string is stored once, so text options that
/// repeat every frame (font family, fill) cost nothing after the first frame.
pub fn intern(value: &str) -> &'static str {
    static STRINGS: Mutex<Option<HashSet<&'static str>>> = Mutex::new(None);
    let mut strings = STRINGS.lock().unwrap_or_else(PoisonError::into_inner);
    let strings = strings.get_or_insert_with(HashSet::new);
    if let Some(found) = strings.get(value) {
        return found;
    }
    let stored: &'static str = Box::leak(value.to_owned().into_boxed_str());
    strings.insert(stored);
    stored
}

pub fn font_style(name: &str) -> PyResult<FontStyle> {
    match name {
        "normal" => Ok(FontStyle::Normal),
        "italic" => Ok(FontStyle::Italic),
        "oblique" => Ok(FontStyle::Oblique),
        _ => Err(PyValueError::new_err(format!("unknown font style {name:?}"))),
    }
}

pub fn font_stretch(name: &str) -> PyResult<FontStretch> {
    Ok(match name.replace('_', "-").as_str() {
        "ultra-condensed" => FontStretch::UltraCondensed,
        "extra-condensed" => FontStretch::ExtraCondensed,
        "condensed" => FontStretch::Condensed,
        "semi-condensed" => FontStretch::SemiCondensed,
        "normal" => FontStretch::Normal,
        "semi-expanded" => FontStretch::SemiExpanded,
        "expanded" => FontStretch::Expanded,
        "extra-expanded" => FontStretch::ExtraExpanded,
        "ultra-expanded" => FontStretch::UltraExpanded,
        _ => return Err(PyValueError::new_err(format!("unknown font stretch {name:?}"))),
    })
}

/// A font from the keyword arguments of the text methods.
pub struct Font {
    pub family: String,
    pub size: usize,
    pub weight: u16,
    pub style: FontStyle,
    pub stretch: FontStretch,
}

impl Font {
    pub fn new(family: String, size: usize, weight: u16, style: &str, stretch: &str) -> PyResult<Self> {
        Ok(Self {
            family,
            size,
            weight,
            style: font_style(style)?,
            stretch: font_stretch(stretch)?,
        })
    }

    pub fn query(&self) -> FontQuery<'_> {
        FontQuery {
            family: &self.family,
            size: self.size,
            weight: self.weight,
            style: self.style,
            stretch: self.stretch,
        }
    }

    pub fn query_static(&self) -> FontQuery<'static> {
        FontQuery {
            family: intern(&self.family),
            size: self.size,
            weight: self.weight,
            style: self.style,
            stretch: self.stretch,
        }
    }
}

pub fn overflow(value: &str) -> TextOverflow<'_> {
    match value {
        "ellipsis" => TextOverflow::Ellipsis,
        "clip" => TextOverflow::Clip,
        marker => TextOverflow::Marker(marker),
    }
}

pub fn align(name: &str) -> PyResult<TextAlign> {
    match name {
        "left" => Ok(TextAlign::Left),
        "center" => Ok(TextAlign::Center),
        "right" => Ok(TextAlign::Right),
        _ => Err(PyValueError::new_err(format!("unknown text align {name:?}"))),
    }
}

/// Wrapping options with `'static` strings.
pub struct Wrap {
    pub font: Font,
    pub width: usize,
    pub line_height: f32,
    pub x: String,
    pub y: String,
    pub align: TextAlign,
    pub fill: String,
    pub dominant_baseline: String,
    pub text_anchor: String,
    pub opacity: f32,
}

impl Wrap {
    pub fn opts(&self) -> BreakLinesOpts<'static, &'static str, &'static str> {
        BreakLinesOpts {
            font: self.font.query_static(),
            width: self.width,
            line_height: self.line_height,
            x: intern(&self.x),
            y: intern(&self.y),
            align: self.align,
            fill: intern(&self.fill),
            dominant_baseline: intern(&self.dominant_baseline),
            text_anchor: intern(&self.text_anchor),
            opacity: self.opacity,
        }
    }
}

/// A number or a string as an SVG attribute string (`100`, `"50%"`).
pub fn attr_string(value: &Bound<'_, PyAny>) -> PyResult<String> {
    if value.is_instance_of::<PyInt>() || value.is_instance_of::<PyFloat>() {
        return Ok(value.str()?.to_string());
    }
    value.extract::<String>()
}

/// One wrapped line: its words and offsets.
#[pyclass(name = "TextLine", module = "fframes", frozen, get_all)]
pub struct PyTextLine {
    pub words: Vec<String>,
    pub width: usize,
    pub dx: usize,
    pub dy: usize,
}

#[pymethods]
impl PyTextLine {
    /// The words joined with spaces.
    #[getter]
    fn text(&self) -> String {
        self.words.join(" ")
    }
}

/// Text wrapped into lines by `frame.text_layout`.
#[pyclass(name = "TextLayout", module = "fframes", frozen)]
pub struct PyTextLayout {
    pub structure: fframes::WrappedTextStructure,
    pub wrap: Wrap,
}

#[pymethods]
impl PyTextLayout {
    #[getter]
    fn lines(&self) -> Vec<PyTextLine> {
        self.structure
            .lines
            .iter()
            .map(|line| PyTextLine {
                words: line.words.clone(),
                width: line.width,
                dx: line.dx,
                dy: line.dy,
            })
            .collect()
    }

    /// The height of all lines in pixels.
    #[getter]
    fn height(&self) -> usize {
        self.structure.occupied_height()
    }

    /// The `<text>` element with one `<tspan>` for each line.
    fn svgr(&self) -> crate::svgr::PySvgr {
        crate::svgr::PySvgr {
            nodes: self.structure.as_svgr(self.wrap.opts()).as_subtree(),
        }
    }

    fn __len__(&self) -> usize {
        self.structure.lines.len()
    }
}

/// A decoded frame of a video file.
#[pyclass(name = "VideoFrame", module = "fframes", frozen, get_all)]
pub struct PyVideoFrame {
    /// The frame as an image, resized when a size was asked for.
    pub image: Py<PyImage>,
    /// The size of the decoded frame.
    pub width: u32,
    pub height: u32,
    pub timestamp_seconds: f32,
    pub stream_fps: f32,
    pub stream_duration: f32,
}

/// Reads a synced frame into a `VideoFrame`, resized when `width` or `height` is given.
pub fn video_frame<'m>(
    py: Python<'_>,
    frame: &impl fframes::FFramesSyncedVideoFrame<'m>,
    width: Option<u32>,
    height: Option<u32>,
) -> PyResult<Option<PyVideoFrame>> {
    let image = match resize_to(width, height, (frame.width(), frame.height())) {
        Some((width, height)) => {
            match frame.into_resized_image(&fframes::media::FrameConvertOptions {
                resize: fframes::media::ResizeVideoFrame { width, height },
            }) {
                Some(image) => image,
                None => return Ok(None),
            }
        }
        None => frame.into_image(),
    };
    Ok(Some(PyVideoFrame {
        image: Py::new(py, PyImage { data: image.image })?,
        width: frame.width(),
        height: frame.height(),
        timestamp_seconds: frame.timestamp_seconds(),
        stream_fps: frame.stream_fps(),
        stream_duration: frame.stream_duration_in_seconds(),
    }))
}

/// The output size for `width`/`height` keywords, keeping the aspect of `frame` when only
/// one is given.
pub fn resize_to(width: Option<u32>, height: Option<u32>, source: (u32, u32)) -> Option<(u32, u32)> {
    let (sw, sh) = (source.0.max(1) as f64, source.1.max(1) as f64);
    match (width, height) {
        (None, None) => None,
        (Some(w), Some(h)) => Some((w.max(1), h.max(1))),
        (Some(w), None) => Some((w.max(1), ((w as f64) * sh / sw).round().max(1.0) as u32)),
        (None, Some(h)) => Some((((h as f64) * sw / sh).round().max(1.0) as u32, h.max(1))),
    }
}

/// A part of a video file placed on the timeline. Each method returns a changed copy.
#[pyclass(name = "Clip", module = "fframes", frozen)]
#[derive(Clone)]
pub struct PyClip {
    video: String,
    start: f64,
    end: Option<f64>,
    at: f32,
    speed: f32,
    reverse: bool,
    looping: bool,
}

impl PyClip {
    pub fn build(&self) -> fframes::Clip<'_> {
        let mut clip = match self.end {
            Some(end) => fframes::Clip::new(&self.video, self.start..end),
            None => fframes::Clip::new(&self.video, self.start..),
        }
        .at(self.at)
        .speed(self.speed);
        if self.reverse {
            clip = clip.reverse();
        }
        if self.looping {
            clip = clip.looping();
        }
        clip
    }
}

#[pymethods]
impl PyClip {
    /// `video` from `start` to `end` seconds of the file (`None`: to its end).
    #[new]
    #[pyo3(signature = (video, start = 0.0, end = None))]
    fn new(video: String, start: f64, end: Option<f64>) -> Self {
        Self {
            video,
            start,
            end,
            at: 0.0,
            speed: 1.0,
            reverse: false,
            looping: false,
        }
    }

    /// Starts the clip at `seconds` of the timeline.
    fn at(&self, seconds: f32) -> Self {
        Self { at: seconds, ..self.clone() }
    }

    fn speed(&self, speed: f32) -> Self {
        Self { speed, ..self.clone() }
    }

    fn reverse(&self) -> Self {
        Self { reverse: true, ..self.clone() }
    }

    fn looping(&self) -> Self {
        Self { looping: true, ..self.clone() }
    }

    /// Seconds that the clip lasts on the timeline.
    #[getter]
    fn seconds(&self) -> f64 {
        self.build().seconds()
    }

    fn frames(&self, fps: usize) -> usize {
        self.build().frames(fps)
    }

    /// The image of the clip at `frame`, or `None` outside the clip.
    #[pyo3(signature = (frame, ctx, width = None))]
    fn image(
        &self,
        py: Python<'_>,
        frame: &PyFrame,
        ctx: &crate::frame::PyContext,
        width: Option<u32>,
    ) -> PyResult<Option<PyImage>> {
        let ctx = ctx.get()?;
        let clip = self.build();
        let image = crate::gil::detached(py, || match width {
            Some(width) => clip.image_at_width(&frame.inner, ctx, width),
            None => clip.image(&frame.inner, ctx),
        });
        Ok(image.map(|image| PyImage { data: image.image }))
    }
}

pub fn sample_size(size: usize) -> PyResult<SampleSize> {
    Ok(match size {
        2 => SampleSize::S2,
        4 => SampleSize::S4,
        8 => SampleSize::S8,
        16 => SampleSize::S16,
        32 => SampleSize::S32,
        64 => SampleSize::S64,
        128 => SampleSize::S128,
        256 => SampleSize::S256,
        512 => SampleSize::S512,
        1024 => SampleSize::S1024,
        _ => {
            return Err(PyValueError::new_err(
                "sample_size must be a power of two from 2 to 1024",
            ));
        }
    })
}

pub fn window(name: Option<&str>) -> PyResult<Option<WindowFunction>> {
    match name {
        None => Ok(None),
        Some("hann") => Ok(Some(WindowFunction::Hann)),
        Some("hamming") => Ok(Some(WindowFunction::Hamming)),
        Some(other) => Err(PyValueError::new_err(format!(
            "window must be None, \"hann\" or \"hamming\", not {other:?}"
        ))),
    }
}

/// The spectrum with the low frequencies in the middle, mirrored to both sides.
#[pyfunction]
pub fn center_spectrum_low_frequencies(spectrum: Vec<f32>) -> Vec<f32> {
    fframes::center_spectrum_low_frequencies(&spectrum)
}

/// A GPU shader (SkSL or Shadertoy GLSL). `shader.draw(frame, uniforms)` gives an image to
/// use as `href` of `<image>`. Shaders draw only with `--renderer gpu` or `skia-cpu`.
#[pyclass(name = "Shader", module = "fframes", frozen)]
pub struct PyShader(Shader);

fn uniform(name: &str, value: &Bound<'_, PyAny>) -> PyResult<ShaderUniformValue> {
    if let Ok(color) = value.cast::<PyColor>() {
        let c = color.get().0;
        return Ok(ShaderUniformValue::Float4([
            c.r as f32 / 255.0,
            c.g as f32 / 255.0,
            c.b as f32 / 255.0,
            c.a as f32 / 255.0,
        ]));
    }
    if let Ok(image) = value.cast::<PyImage>() {
        return Ok(ShaderUniformValue::Image(image.get().data.clone()));
    }
    if value.is_instance_of::<PyInt>() && !value.is_instance_of::<pyo3::types::PyBool>() {
        return Ok(ShaderUniformValue::Int(value.extract()?));
    }
    if let Ok(x) = value.extract::<f32>() {
        return Ok(ShaderUniformValue::Float(x));
    }
    if let Ok(tuple) = value.cast::<PyTuple>() {
        let v: Vec<f32> = tuple.extract()?;
        return match v.as_slice() {
            [x, y] => Ok(ShaderUniformValue::Float2([*x, *y])),
            [x, y, z] => Ok(ShaderUniformValue::Float3([*x, *y, *z])),
            [x, y, z, w] => Ok(ShaderUniformValue::Float4([*x, *y, *z, *w])),
            _ => Err(PyValueError::new_err(format!(
                "uniform {name:?}: a tuple must have 2, 3 or 4 numbers"
            ))),
        };
    }
    Err(PyTypeError::new_err(format!(
        "uniform {name:?} must be a number, a tuple of 2-4 numbers, a Color or an Image"
    )))
}

#[pymethods]
impl PyShader {
    /// A shader from SkSL source with `half4 main(float2 coord)`.
    #[staticmethod]
    fn sksl(source: String) -> Self {
        Self(Shader::sksl(source))
    }

    /// A shader from Shadertoy GLSL source with `mainImage`.
    #[staticmethod]
    fn shadertoy(source: &str) -> Self {
        Self(Shader::shadertoy(source))
    }

    /// The SkSL that the shader runs.
    #[getter]
    fn source(&self) -> &str {
        self.0.sksl_source()
    }

    /// The shader at `frame` with `uniforms` (name to number, tuple, `Color` or `Image`).
    #[pyo3(signature = (frame, uniforms = None))]
    fn draw(&self, frame: &PyFrame, uniforms: Option<&Bound<'_, PyDict>>) -> PyResult<PyImage> {
        let mut values = ShaderUniforms::new();
        if let Some(uniforms) = uniforms {
            for (name, value) in uniforms.iter() {
                let name: String = name.extract()?;
                let value = uniform(&name, &value)?;
                values = values.set(name, value);
            }
        }
        Ok(PyImage {
            data: self.0.draw(&frame.inner, values).image,
        })
    }
}

pub fn image_arc(image: &fframes::media::ImageData<'_>) -> Arc<fframes::usvgr::PreloadedImageData> {
    image.image.clone()
}
