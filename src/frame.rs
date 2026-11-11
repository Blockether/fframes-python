//! `Frame` and `Context`: what `render_frame(frame, ctx)` receives.

use std::cell::Cell;

use fframes::{FFramesContext, FFramesMode, Frame};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;

use crate::animation::PyTimeline;
use crate::media_api::{self, Font, PyTextLayout, PyVideoFrame, Wrap};
use crate::svgr::{Nodes, PySvgr};
use crate::values::PyImage;

/// The current frame: its index, time and caches.
#[pyclass(name = "Frame", module = "fframes", unsendable)]
pub struct PyFrame {
    pub inner: Frame,
}

impl PyFrame {
    pub fn new(inner: Frame) -> Self {
        Self { inner }
    }
}

#[pymethods]
impl PyFrame {
    /// A free-standing frame, e.g. to sample timelines when a video is built.
    #[new]
    #[pyo3(signature = (index, global_index = None, fps = 30))]
    fn py_new(index: usize, global_index: Option<usize>, fps: usize) -> Self {
        Self::new(Frame::new(index, global_index.unwrap_or(index), fps))
    }

    /// The frame index in the current scene (in the video outside scenes).
    #[getter]
    fn index(&self) -> usize {
        self.inner.index
    }

    /// The frame index in the whole video.
    #[getter]
    fn global_index(&self) -> usize {
        self.inner.global_index
    }

    #[getter]
    fn fps(&self) -> usize {
        self.inner.fps
    }

    /// The time of the frame in seconds, in the current scene.
    #[getter]
    fn seconds(&self) -> f32 {
        self.inner.seconds()
    }

    fn frame_to_second(&self, frame: usize) -> f32 {
        self.inner.frame_to_second(frame)
    }

    fn second_to_frame(&self, second: f32) -> usize {
        self.inner.second_to_frame(second)
    }

    /// The value of `timeline` at this frame.
    fn animate(&self, py: Python<'_>, timeline: &Bound<'_, PyTimeline>) -> PyResult<Py<PyAny>> {
        timeline.get().animation.eval(py, &self.inner, false)
    }

    /// The value of `timeline` at this frame, repeating the timeline.
    fn animate_loop(
        &self,
        py: Python<'_>,
        timeline: &Bound<'_, PyTimeline>,
    ) -> PyResult<Py<PyAny>> {
        timeline.get().animation.eval(py, &self.inner, true)
    }

    /// The width in pixels of `text` in a font of the media, or `None` if the font is missing.
    #[pyo3(signature = (ctx, text, *, family = "Arial".to_owned(), size = 16, weight = 500, style = "normal", stretch = "normal"))]
    #[allow(clippy::too_many_arguments)]
    fn text_width(
        &mut self,
        py: Python<'_>,
        ctx: &PyContext,
        text: &str,
        family: String,
        size: usize,
        weight: u16,
        style: &str,
        stretch: &str,
    ) -> PyResult<Option<usize>> {
        let font = Font::new(family, size, weight, style, stretch)?;
        let (ctx, inner) = (ctx.get()?, &mut self.inner);
        Ok(crate::gil::detached(py, || {
            inner.text_width(ctx, font.query(), text)
        }))
    }

    /// `text` shortened to `max_width` pixels. `overflow` is "ellipsis", "clip" or a marker.
    #[pyo3(signature = (ctx, text, max_width, *, family = "Arial".to_owned(), size = 16, weight = 500, style = "normal", stretch = "normal", overflow = "ellipsis"))]
    #[allow(clippy::too_many_arguments)]
    fn text_fit(
        &mut self,
        py: Python<'_>,
        ctx: &PyContext,
        text: &str,
        max_width: usize,
        family: String,
        size: usize,
        weight: u16,
        style: &str,
        stretch: &str,
        overflow: &str,
    ) -> PyResult<Option<String>> {
        let font = Font::new(family, size, weight, style, stretch)?;
        let (ctx, inner) = (ctx.get()?, &mut self.inner);
        let overflow = media_api::overflow(overflow);
        Ok(crate::gil::detached(py, || {
            inner
                .text_fit(ctx, font.query(), text, max_width, overflow)
                .map(std::borrow::Cow::into_owned)
        }))
    }

    /// `text` wrapped into lines of at most `width` pixels, or `None` if the font is missing.
    #[pyo3(signature = (ctx, text, *, width, family = "Arial".to_owned(), size = 16, weight = 500, style = "normal", stretch = "normal", line_height = 1.1, x = None, y = None, align = "left", fill = "".to_owned(), dominant_baseline = "auto".to_owned(), text_anchor = "start".to_owned(), opacity = 1.0))]
    #[allow(clippy::too_many_arguments)]
    fn text_layout(
        &mut self,
        py: Python<'_>,
        ctx: &PyContext,
        text: &str,
        width: usize,
        family: String,
        size: usize,
        weight: u16,
        style: &str,
        stretch: &str,
        line_height: f32,
        x: Option<&Bound<'_, PyAny>>,
        y: Option<&Bound<'_, PyAny>>,
        align: &str,
        fill: String,
        dominant_baseline: String,
        text_anchor: String,
        opacity: f32,
    ) -> PyResult<Option<PyTextLayout>> {
        let wrap = Wrap {
            font: Font::new(family, size, weight, style, stretch)?,
            width,
            line_height,
            x: x.map(media_api::attr_string)
                .transpose()?
                .unwrap_or_default(),
            y: y.map(media_api::attr_string)
                .transpose()?
                .unwrap_or_default(),
            align: media_api::align(align)?,
            fill,
            dominant_baseline,
            text_anchor,
            opacity,
        };
        let (ctx, inner) = (ctx.get()?, &mut self.inner);
        let structure = crate::gil::detached(py, || {
            inner.text_break_lines_structure(ctx, text, wrap.opts())
        });
        Ok(structure.map(|structure| PyTextLayout { structure, wrap }))
    }

    /// The synced frame of the video file `file`: frame `index` of this video shows the file at
    /// `(seconds - start_from) * speed`. `None` before `start_from` or after the file ends.
    #[pyo3(signature = (ctx, file, *, start_from = 0.0, looping = false, speed = 1.0, width = None, height = None))]
    #[allow(clippy::too_many_arguments)]
    fn video_frame(
        &self,
        py: Python<'_>,
        ctx: &PyContext,
        file: &str,
        start_from: f32,
        looping: bool,
        speed: f32,
        width: Option<u32>,
        height: Option<u32>,
    ) -> PyResult<Option<PyVideoFrame>> {
        let input = fframes::SyncVideoFrameInput {
            start_from,
            looping,
            speed,
            ..Default::default()
        };
        let (ctx, inner) = (ctx.get()?, &self.inner);
        crate::gil::detached(py, || {
            let frame = inner.get_synced_video_frame(ctx, file, &input)?;
            media_api::DecodedFrame::new(&*frame, width, height)
        })
        .map(|frame| frame.into_py(py))
        .transpose()
    }

    /// The frame at `seconds` of the video file `file`, wherever this frame is.
    #[pyo3(signature = (ctx, file, seconds, *, width = None, height = None))]
    fn video_frame_at(
        &self,
        py: Python<'_>,
        ctx: &PyContext,
        file: &str,
        seconds: f64,
        width: Option<u32>,
        height: Option<u32>,
    ) -> PyResult<Option<PyVideoFrame>> {
        let (ctx, inner) = (ctx.get()?, &self.inner);
        crate::gil::detached(py, || {
            let frame = inner.video_frame_at(ctx, file, seconds, None)?;
            media_api::DecodedFrame::new(&*frame, width, height)
        })
        .map(|frame| frame.into_py(py))
        .transpose()
    }

    /// The spectrum of the audio `audio` at this frame: `sample_size / 2` levels.
    #[pyo3(signature = (ctx, audio, *, sample_size = 512, smooth_level = 0, window = None))]
    fn visualize_audio(
        &self,
        py: Python<'_>,
        ctx: &PyContext,
        audio: &str,
        sample_size: usize,
        smooth_level: usize,
        window: Option<&str>,
    ) -> PyResult<Vec<f32>> {
        let data = ctx
            .get()?
            .get_audio(audio)
            .ok_or_else(|| PyValueError::new_err(format!("no audio {audio:?} in the media")))?;
        let input = fframes::VisualizeFrameInput {
            audio: data,
            sample_size: media_api::sample_size(sample_size)?,
            smooth_level,
            window: media_api::window(window)?,
        };
        let inner = &self.inner;
        Ok(crate::gil::detached(py, || {
            inner.visualize_audio_frame(input)
        }))
    }

    /// The subtitle text of `file` at this frame, or `None`.
    fn subtitle_phrase(&self, ctx: &PyContext, file: &str) -> PyResult<Option<String>> {
        Ok(ctx
            .get()?
            .get_subtitles(file)
            .and_then(|subtitles| self.inner.get_subtitle_phrase(subtitles))
            .map(str::to_owned))
    }

    /// The Lottie animation `file` of the media, started at `start` seconds of this frame's
    /// timeline and fit into the box `x, y, width, height`.
    #[pyo3(signature = (ctx, file, *, start = 0.0, speed = 1.0, looping = false, x = 0.0, y = 0.0, width = None, height = None))]
    #[allow(clippy::too_many_arguments)]
    fn play_lottie(
        &self,
        py: Python<'_>,
        ctx: &PyContext,
        file: &str,
        start: f32,
        speed: f32,
        looping: bool,
        x: f32,
        y: f32,
        width: Option<f32>,
        height: Option<f32>,
    ) -> PyResult<PySvgr> {
        let options = fframes::LottieOptions {
            start,
            speed,
            looping,
            x,
            y,
            width,
            height,
        };
        let (ctx, inner) = (ctx.get()?, &self.inner);
        Ok(PySvgr {
            nodes: crate::gil::detached(py, || inner.play_lottie(ctx, file, options).as_subtree()),
        })
    }

    /// This frame with scene index `index`; its time and shader clock follow the index.
    fn with_index(&self, index: usize) -> Self {
        let mut inner = self.inner.clone();
        inner.index = index;
        Self::new(inner)
    }

    /// This frame with the index of the whole video.
    #[allow(clippy::wrong_self_convention)]
    fn into_global(&self) -> Self {
        Self::new(self.inner.clone().into_global())
    }

    fn __repr__(&self) -> String {
        format!(
            "Frame(index={}, global_index={}, fps={})",
            self.inner.index, self.inner.global_index, self.inner.fps
        )
    }
}

/// The render context. It is valid only during the `render_frame` call that received it.
#[pyclass(name = "Context", module = "fframes", unsendable)]
pub struct PyContext {
    ptr: Cell<*const FFramesContext<'static, 'static>>,
}

impl PyContext {
    pub fn new(ctx: &FFramesContext<'_, '_>) -> Self {
        Self {
            ptr: Cell::new((ctx as *const FFramesContext<'_, '_>).cast()),
        }
    }

    pub fn invalidate(&self) {
        self.ptr.set(std::ptr::null());
    }

    pub fn get(&self) -> PyResult<&FFramesContext<'_, '_>> {
        // SAFETY: the pointer is set from a live reference and cleared before the
        // `render_frame` call that owns that reference returns. The lifetimes shrink to
        // this borrow; values that leave it own their data (`Arc` images, cloned trees).
        unsafe { self.ptr.get().cast::<FFramesContext<'_, '_>>().as_ref() }.ok_or_else(|| {
            PyRuntimeError::new_err("the context is valid only during its render_frame call")
        })
    }
}

#[pymethods]
impl PyContext {
    /// The output width, after `scale`.
    #[getter]
    fn width(&self) -> PyResult<usize> {
        Ok(self.get()?.current_video_size.width)
    }

    /// The output height, after `scale`.
    #[getter]
    fn height(&self) -> PyResult<usize> {
        Ok(self.get()?.current_video_size.height)
    }

    #[getter]
    fn fps(&self) -> PyResult<usize> {
        Ok(self.get()?.time_base.fps)
    }

    #[getter]
    fn sample_rate(&self) -> PyResult<usize> {
        Ok(self.get()?.time_base.sample_rate)
    }

    #[getter]
    fn duration_in_frames(&self) -> PyResult<usize> {
        Ok(self.get()?.duration_in_frames)
    }

    /// "renderer", "editor" or "editor-timeline-preview".
    #[getter]
    fn mode(&self) -> PyResult<&'static str> {
        Ok(match self.get()?.mode {
            FFramesMode::Renderer => "renderer",
            FFramesMode::Editor => "editor",
            FFramesMode::EditorTimelinePreview => "editor-timeline-preview",
        })
    }

    /// The image `name` of the media folder, or `None`.
    fn image(&self, name: &str) -> PyResult<Option<PyImage>> {
        Ok(self.get()?.get_image(name).map(|image| PyImage {
            data: image.image.clone(),
        }))
    }

    /// `svgr` rasterized to a `width` x `height` image, or `None` without a rasterizer.
    fn render_svgr(
        &self,
        py: Python<'_>,
        svgr: &PySvgr,
        width: u32,
        height: u32,
    ) -> PyResult<Option<PyImage>> {
        let tree = PySvgr::into_svgr(svgr.nodes.clone());
        let ctx = self.get()?;
        // Rasterizes without the GIL, so that the frame threads run in parallel.
        Ok(py
            .detach(|| ctx.render_svgr(tree, width, height))
            .map(|image| PyImage { data: image.image }))
    }

    /// The frames of the scenes that play at `frame`.
    fn render_scenes(&self, frame: &PyFrame) -> PyResult<PySvgr> {
        let nodes = self.get()?.render_scenes(&frame.inner).as_subtree();
        // SAFETY: the scenes of a Python video are `PyScene`s, whose trees own their data
        // (`PySvgr::into_svgr` builds them from `'static` nodes).
        let nodes: Nodes = unsafe { std::mem::transmute(nodes) };
        Ok(PySvgr { nodes })
    }
}
