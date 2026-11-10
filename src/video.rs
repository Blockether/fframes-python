//! A Python object as an fframes `Video`, and its scenes as fframes `Scene`s.
//!
//! fframes calls `render_frame` from its worker threads. Each call takes the GIL. Duration,
//! audio and scenes are read once, when the video is built, so the timeline stays fixed.

use std::sync::Mutex;

use fframes::{AbortSignal, AudioMap, Color, FFramesContext, Frame, Scene, Scenes, Svgr, Video};
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::intern;
use pyo3::prelude::*;

use crate::frame::{PyContext, PyFrame};
use crate::svgr::PySvgr;
use crate::timing::{
    DurSpec, OverlapSpec, TrackSpec, audio_from_any, build_audio_map, duration_from_any,
    overlap_from_any,
};
use crate::values::color_from_any;

/// The first Python error of a render. It aborts the render and is raised after it.
#[derive(Debug, Default)]
pub struct Failure {
    error: Mutex<Option<PyErr>>,
    pub abort: AbortSignal,
}

impl Failure {
    pub fn record(&self, error: PyErr) {
        let mut slot = self
            .error
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner);
        if slot.is_none() {
            *slot = Some(error);
        }
        self.abort.abort();
    }

    pub fn is_failed(&self) -> bool {
        self.abort.is_aborted()
    }

    /// The recorded error, if any. A later render starts clean.
    pub fn take(&self) -> Option<PyErr> {
        self.error
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .take()
    }
}

/// An attribute that is a value or a method without arguments.
fn read<'py>(obj: &Bound<'py, PyAny>, name: &str) -> PyResult<Option<Bound<'py, PyAny>>> {
    match obj.getattr(name) {
        Ok(value) if value.is_callable() => value.call0().map(Some),
        Ok(value) => Ok(Some(value)),
        Err(err) if err.is_instance_of::<pyo3::exceptions::PyAttributeError>(obj.py()) => Ok(None),
        Err(err) => Err(err),
    }
}

fn class_name(obj: &Bound<'_, PyAny>) -> PyResult<String> {
    Ok(obj.get_type().name()?.to_cow()?.into_owned())
}

/// The result of a Python `render_frame` as a tree.
fn svgr_from_any(value: &Bound<'_, PyAny>) -> PyResult<Svgr<'static>> {
    if value.is_none() {
        return Ok(Svgr::default());
    }
    match value.cast::<PySvgr>() {
        Ok(svgr) => Ok(PySvgr::into_svgr(svgr.get().nodes.clone())),
        Err(_) => Err(PyTypeError::new_err(format!(
            "render_frame must return fframes.Svgr or None, not {}",
            class_name(value)?
        ))),
    }
}

fn call_render<'a>(
    obj: &Py<PyAny>,
    failure: &Failure,
    frame: Frame,
    ctx: &FFramesContext<'a, '_>,
) -> Svgr<'a> {
    if failure.is_failed() {
        return Svgr::default();
    }
    Python::attach(|py| {
        let result = (|| {
            let frame = Bound::new(py, PyFrame::new(frame))?;
            let context = Bound::new(py, PyContext::new(ctx))?;
            let out = obj
                .bind(py)
                .call_method1(intern!(py, "render_frame"), (frame, &context));
            context.borrow().invalidate();
            svgr_from_any(&out?)
        })();
        result.unwrap_or_else(|error| {
            clear_traceback_locals(py, &error);
            failure.record(error);
            Svgr::default()
        })
    })
}

/// Clears the locals of the frames in the tracebacks of `error` and its context chain. The error
/// is raised on the calling thread, and the locals hold this thread's unsendable `Frame` and
/// `Context`, which must be dropped here.
fn clear_traceback_locals(py: Python<'_>, error: &PyErr) {
    let Ok(clear_frames) = py
        .import(intern!(py, "traceback"))
        .and_then(|m| m.getattr(intern!(py, "clear_frames")))
    else {
        return;
    };
    let mut value = Some(error.value(py).clone().into_any());
    for _ in 0..32 {
        let Some(current) = value.take() else { break };
        if let Ok(traceback) = current.getattr(intern!(py, "__traceback__"))
            && !traceback.is_none()
        {
            let _ = clear_frames.call1((traceback,));
        }
        value = current
            .getattr(intern!(py, "__context__"))
            .ok()
            .filter(|next| !next.is_none());
    }
}

pub struct PyScene {
    obj: Py<PyAny>,
    name: &'static str,
    duration: DurSpec,
    overlap: OverlapSpec,
    audio: Vec<TrackSpec>,
    failure: std::sync::Arc<Failure>,
}

impl std::fmt::Debug for PyScene {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "PyScene({})", self.name)
    }
}

impl Scene for PyScene {
    fn duration(&self) -> fframes::Duration<'_> {
        self.duration.build()
    }

    fn render_frame<'a>(&'a self, frame: Frame, ctx: &FFramesContext<'a, '_>) -> Svgr<'a> {
        call_render(&self.obj, &self.failure, frame, ctx)
    }

    fn overlap(&self) -> fframes::Overlap {
        self.overlap.build()
    }

    fn audio(&self) -> AudioMap<'_> {
        build_audio_map(&self.audio)
    }

    fn name(&self) -> &'static str {
        self.name
    }
}

pub struct PyVideo {
    obj: Py<PyAny>,
    fps: usize,
    width: usize,
    height: usize,
    background: Color,
    duration: DurSpec,
    audio: Vec<TrackSpec>,
    scenes: Vec<PyScene>,
    has_render_frame: bool,
    pub failure: std::sync::Arc<Failure>,
}

fn positive(obj: &Bound<'_, PyAny>, name: &str, default: Option<usize>) -> PyResult<usize> {
    let value = match read(obj, name)? {
        Some(value) => value.extract::<usize>()?,
        None => default.ok_or_else(|| {
            PyTypeError::new_err(format!("the video must have the attribute {name:?}"))
        })?,
    };
    if value == 0 {
        return Err(PyValueError::new_err(format!("{name} must be positive")));
    }
    Ok(value)
}

impl PyVideo {
    /// Reads the video description of `obj` once.
    pub fn from_py(obj: &Bound<'_, PyAny>) -> PyResult<Self> {
        let failure = std::sync::Arc::new(Failure::default());
        let background = match read(obj, "background_color")? {
            Some(color) if !color.is_none() => color_from_any(&color)?,
            _ => Color::BLACK,
        };
        let mut scenes = Vec::new();
        if let Some(list) = read(obj, "scenes")?
            && !list.is_none()
        {
            for scene in list.try_iter()? {
                let scene = scene?;
                let name = match read(&scene, "name")? {
                    Some(name) if !name.is_none() => name.extract::<String>()?,
                    _ => class_name(&scene)?,
                };
                let duration = match read(&scene, "duration")? {
                    Some(duration) => duration_from_any(&duration)?,
                    None => {
                        return Err(PyTypeError::new_err(format!(
                            "scene {name:?} must have a duration"
                        )));
                    }
                };
                scenes.push(PyScene {
                    overlap: overlap_from_any(read(&scene, "overlap")?.as_ref())?,
                    audio: audio_from_any(read(&scene, "audio")?.as_ref())?,
                    obj: scene.unbind(),
                    name: Box::leak(name.into_boxed_str()),
                    duration,
                    failure: failure.clone(),
                });
            }
        }
        let has_render_frame = obj.hasattr("render_frame")?;
        if !has_render_frame && scenes.is_empty() {
            return Err(PyTypeError::new_err(
                "the video must have a render_frame(frame, ctx) method or scenes",
            ));
        }
        Ok(Self {
            fps: positive(obj, "fps", Some(30))?,
            width: positive(obj, "width", None)?,
            height: positive(obj, "height", None)?,
            background,
            duration: match read(obj, "duration")? {
                Some(duration) => duration_from_any(&duration)?,
                None => DurSpec::Auto,
            },
            audio: audio_from_any(read(obj, "audio")?.as_ref())?,
            scenes,
            has_render_frame,
            failure,
            obj: obj.clone().unbind(),
        })
    }

    /// Raises the first Python error of the last render.
    pub fn raise_failure(&self) -> PyResult<()> {
        match self.failure.take() {
            Some(error) => Err(error),
            None => Ok(()),
        }
    }
}

impl Video for PyVideo {
    const FPS: usize = 30;
    const WIDTH: usize = 1920;
    const HEIGHT: usize = 1080;

    fn fps(&self) -> usize {
        self.fps
    }

    fn width(&self) -> usize {
        self.width
    }

    fn height(&self) -> usize {
        self.height
    }

    fn background_color(&self) -> Color {
        self.background
    }

    fn duration(&self) -> fframes::Duration<'_> {
        self.duration.build()
    }

    fn audio(&self) -> AudioMap<'_> {
        build_audio_map(&self.audio)
    }

    fn define_scenes(&self) -> Scenes<'_> {
        if self.scenes.is_empty() {
            return Scenes::empty();
        }
        Scenes::from(
            self.scenes
                .iter()
                .map(|scene| scene as &dyn Scene)
                .collect::<Vec<_>>(),
        )
    }

    fn render_frame<'a>(&'a self, frame: Frame, ctx: &FFramesContext<'a, '_>) -> Svgr<'a> {
        if self.has_render_frame {
            call_render(&self.obj, &self.failure, frame, ctx)
        } else {
            ctx.render_scenes(&frame)
        }
    }
}
