//! `Captions`: timed captions from subtitle media (JSON or WebVTT), drawn as native SVG text.
//!
//! The component keeps its layout cache between frames. Word callbacks are Python callables
//! `(word, content) -> Svgr`; `word` is valid only during its callback.

use std::borrow::Cow;
use std::cell::{Cell, RefCell};

use fframes::captions::{
    CaptionClock, CaptionMetadata, CaptionMode, CaptionRect, CaptionWordScope, Captions, WordState,
};
use fframes::usvgr::svgtree::{
    Attribute, NestedNodeData, NestedNodeKind, StringStorage, SvgAttributeValue,
};
use pyo3::IntoPyObjectExt;
use pyo3::exceptions::{PyRuntimeError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

use crate::frame::{PyContext, PyFrame};
use crate::svgr::{Nodes, PySvgr};

fn own_str(value: StringStorage<'_>) -> StringStorage<'static> {
    match value {
        StringStorage::Borrowed(s) => StringStorage::new_owned(s),
        StringStorage::Owned(s) => StringStorage::Owned(s),
    }
}

fn own_value(value: SvgAttributeValue<'_>) -> SvgAttributeValue<'static> {
    match value {
        SvgAttributeValue::Float(f, s) => SvgAttributeValue::Float(f, own_str(s)),
        SvgAttributeValue::Length(v) => SvgAttributeValue::Length(v),
        SvgAttributeValue::Transform(v) => SvgAttributeValue::Transform(v),
        SvgAttributeValue::Color(v) => SvgAttributeValue::Color(v),
        SvgAttributeValue::StringStorage(s) => SvgAttributeValue::StringStorage(own_str(s)),
        SvgAttributeValue::ImageData(v) => SvgAttributeValue::ImageData(v),
        SvgAttributeValue::PathData(v) => SvgAttributeValue::PathData(Cow::Owned(v.into_owned())),
        SvgAttributeValue::StaticPath(v) => SvgAttributeValue::StaticPath(v),
    }
}

/// A deep copy of borrowed nodes that owns its strings.
pub fn own_nodes(nodes: Vec<Option<NestedNodeData<'_>>>) -> Nodes {
    nodes
        .into_iter()
        .map(|node| {
            node.map(|node| NestedNodeData {
                kind: match node.kind {
                    NestedNodeKind::Root => NestedNodeKind::Root,
                    NestedNodeKind::Element { tag_name } => NestedNodeKind::Element { tag_name },
                    NestedNodeKind::Text(s) => NestedNodeKind::Text(own_str(s)),
                },
                attrs: node
                    .attrs
                    .into_vec()
                    .into_iter()
                    .map(|a| Attribute {
                        name: a.name,
                        value: own_value(a.value),
                    })
                    .collect(),
                children: own_nodes(node.children),
                static_hash: node.static_hash,
            })
        })
        .collect()
}

fn mode_from(name: &str) -> PyResult<CaptionMode> {
    match name {
        "highlight" => Ok(CaptionMode::Highlight),
        "word" => Ok(CaptionMode::Word),
        "reveal" => Ok(CaptionMode::Reveal),
        "karaoke" => Ok(CaptionMode::Karaoke),
        _ => Err(PyValueError::new_err(format!(
            "unknown caption mode {name:?}: use highlight, word, reveal or karaoke"
        ))),
    }
}

fn metadata_dict(py: Python<'_>, metadata: &CaptionMetadata) -> PyResult<Py<PyAny>> {
    let dict = PyDict::new(py);
    for (key, value) in metadata.iter() {
        dict.set_item(key, json_value(py, value)?)?;
    }
    Ok(dict.into_any().unbind())
}

fn json_value(py: Python<'_>, value: &serde_json::Value) -> PyResult<Py<PyAny>> {
    use serde_json::Value;
    match value {
        Value::Null => Ok(py.None()),
        Value::Bool(b) => b.into_py_any(py),
        Value::Number(n) => match n.as_i64() {
            Some(i) => i.into_py_any(py),
            None => n.as_f64().unwrap_or(f64::NAN).into_py_any(py),
        },
        Value::String(s) => s.into_py_any(py),
        Value::Array(items) => {
            let list = PyList::empty(py);
            for item in items {
                list.append(json_value(py, item)?)?;
            }
            list.into_py_any(py)
        }
        Value::Object(map) => {
            let dict = PyDict::new(py);
            for (key, item) in map {
                dict.set_item(key, json_value(py, item)?)?;
            }
            dict.into_py_any(py)
        }
    }
}

/// One visible word in a caption callback. Drawing is in word-local coordinates: `(0, 0)` is
/// the top-left of the word's advance box. Valid only during the callback that received it.
#[pyclass(name = "CaptionWord", module = "fframes", unsendable)]
pub struct PyCaptionWord {
    scope: Cell<*const CaptionWordScope<'static, 'static>>,
}

impl PyCaptionWord {
    fn get(&self) -> PyResult<&CaptionWordScope<'_, '_>> {
        // SAFETY: the pointer comes from a live scope reference and is cleared before the
        // callback that received the word returns.
        unsafe { self.scope.get().cast::<CaptionWordScope<'_, '_>>().as_ref() }.ok_or_else(|| {
            PyRuntimeError::new_err("a caption word is valid only during its callback")
        })
    }
}

#[pymethods]
impl PyCaptionWord {
    #[getter]
    fn text(&self) -> PyResult<String> {
        Ok(self.get()?.word.text.to_owned())
    }
    /// The JSON `metadata` object of the timed word, as a dict.
    #[getter]
    fn metadata(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        metadata_dict(py, self.get()?.word.metadata)
    }
    /// The JSON `metadata` object of the cue, as a dict.
    #[getter]
    fn cue_metadata(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        metadata_dict(py, self.get()?.cue_metadata)
    }
    #[getter]
    fn width(&self) -> PyResult<f64> {
        Ok(self.get()?.width())
    }
    #[getter]
    fn height(&self) -> PyResult<f64> {
        Ok(self.get()?.height())
    }
    /// The word box in composition pixels: `(x, y, width, height)`.
    #[getter]
    fn rect(&self) -> PyResult<(f64, f64, f64, f64)> {
        let r = self.get()?.composition_rect;
        Ok((r.x, r.y, r.width, r.height))
    }
    /// "upcoming", "active" or "spoken".
    #[getter]
    fn state(&self) -> PyResult<&'static str> {
        Ok(match self.get()?.word.state {
            WordState::Upcoming => "upcoming",
            WordState::Active => "active",
            WordState::Spoken => "spoken",
        })
    }
    #[getter]
    fn is_active(&self) -> PyResult<bool> {
        Ok(self.get()?.is_active())
    }
    /// The part of the active word that was spoken, 0 to 1.
    #[getter]
    fn progress(&self) -> PyResult<f32> {
        Ok(self.get()?.word.progress)
    }
    /// Seconds since the timed word began, or `None` for untimed phrase text.
    #[getter]
    fn elapsed(&self) -> PyResult<Option<f64>> {
        Ok(self.get()?.elapsed())
    }
    /// Caption-clock seconds of the render.
    #[getter]
    fn time(&self) -> PyResult<f64> {
        Ok(self.get()?.time)
    }
    #[getter]
    fn start(&self) -> PyResult<Option<f64>> {
        Ok(self.get()?.word.start)
    }
    #[getter]
    fn end(&self) -> PyResult<Option<f64>> {
        Ok(self.get()?.word.end)
    }
    #[getter]
    fn cue_index(&self) -> PyResult<usize> {
        Ok(self.get()?.word.cue_index)
    }
    #[getter]
    fn token_index(&self) -> PyResult<usize> {
        Ok(self.get()?.word.token_index)
    }
    #[getter]
    fn word_index(&self) -> PyResult<Option<usize>> {
        Ok(self.get()?.word.word_index)
    }
    /// An SVG-safe id for your own definitions in this word.
    fn id(&self, key: &str) -> PyResult<String> {
        Ok(self.get()?.id(key))
    }
    /// `content` clipped to the word box.
    fn clip(&self, content: &PySvgr) -> PyResult<PySvgr> {
        let svg = self.get()?.clip(PySvgr::into_svgr(content.nodes.clone()));
        Ok(PySvgr {
            nodes: own_nodes(svg.as_subtree()),
        })
    }
    /// `content` shown only through the glyphs of the word.
    fn mask_text(&self, content: &PySvgr) -> PyResult<PySvgr> {
        let svg = self
            .get()?
            .mask_text(PySvgr::into_svgr(content.nodes.clone()));
        Ok(PySvgr {
            nodes: own_nodes(svg.as_subtree()),
        })
    }
}

/// Timed captions. Build once (module level or `__init__`), render every frame.
///
/// `Captions("speech.json", x, y, width, height)` reads subtitle media by name. The builder
/// methods change the component and return it.
#[pyclass(name = "Captions", module = "fframes")]
pub struct PyCaptions {
    inner: Option<Captions>,
}

impl PyCaptions {
    fn inner(&self) -> &Captions {
        self.inner.as_ref().expect("captions are always set")
    }
}

/// Applies a builder method of `Captions` in place.
fn update(
    mut slf: PyRefMut<'_, PyCaptions>,
    f: impl FnOnce(Captions) -> Captions,
) -> PyRefMut<'_, PyCaptions> {
    let inner = slf.inner.take().expect("captions are always set");
    slf.inner = Some(f(inner));
    slf
}

#[pymethods]
impl PyCaptions {
    #[new]
    fn new(media: String, x: f64, y: f64, width: f64, height: f64) -> Self {
        Self {
            inner: Some(Captions::from_media(
                media,
                CaptionRect::new(x, y, width, height),
            )),
        }
    }

    fn font(slf: PyRefMut<'_, Self>, family: String, size: usize) -> PyRefMut<'_, Self> {
        update(slf, |c| c.font(family, size))
    }
    fn font_weight(slf: PyRefMut<'_, Self>, weight: u16) -> PyRefMut<'_, Self> {
        update(slf, |c| c.font_weight(weight))
    }
    fn bounds(
        slf: PyRefMut<'_, Self>,
        x: f64,
        y: f64,
        width: f64,
        height: f64,
    ) -> PyRefMut<'_, Self> {
        update(slf, |c| c.bounds(CaptionRect::new(x, y, width, height)))
    }
    fn line_height(slf: PyRefMut<'_, Self>, multiplier: f64) -> PyRefMut<'_, Self> {
        update(slf, |c| c.line_height(multiplier))
    }
    /// "highlight" (default), "word", "reveal" or "karaoke".
    fn mode<'py>(slf: PyRefMut<'py, Self>, mode: &str) -> PyResult<PyRefMut<'py, Self>> {
        let mode = mode_from(mode)?;
        Ok(update(slf, |c| c.mode(mode)))
    }
    /// "scene" (default): scene-local time; "global": video time.
    fn clock<'py>(slf: PyRefMut<'py, Self>, clock: &str) -> PyResult<PyRefMut<'py, Self>> {
        let clock = match clock {
            "scene" => CaptionClock::Scene,
            "global" => CaptionClock::Global,
            _ => return Err(PyValueError::new_err("clock is \"scene\" or \"global\"")),
        };
        Ok(update(slf, |c| c.clock(clock)))
    }
    fn active_fill(slf: PyRefMut<'_, Self>, fill: String) -> PyRefMut<'_, Self> {
        update(slf, |c| c.active_fill(fill))
    }
    fn upcoming_fill(slf: PyRefMut<'_, Self>, fill: String) -> PyRefMut<'_, Self> {
        update(slf, |c| c.upcoming_fill(fill))
    }
    fn spoken_fill(slf: PyRefMut<'_, Self>, fill: String) -> PyRefMut<'_, Self> {
        update(slf, |c| c.spoken_fill(fill))
    }
    fn outline(slf: PyRefMut<'_, Self>, fill: String, width: f64) -> PyRefMut<'_, Self> {
        update(slf, |c| c.outline(fill, width))
    }
    fn active_background(
        slf: PyRefMut<'_, Self>,
        fill: String,
        padding: f64,
    ) -> PyRefMut<'_, Self> {
        update(slf, |c| c.active_background(fill, padding))
    }
    fn underline(slf: PyRefMut<'_, Self>, fill: String, width: f64) -> PyRefMut<'_, Self> {
        update(slf, |c| c.underline(fill, width))
    }

    /// The captions at `frame`, or at track second `at`.
    #[pyo3(signature = (frame, ctx, *, at = None))]
    fn render(&self, frame: &PyFrame, ctx: &PyContext, at: Option<f64>) -> PyResult<PySvgr> {
        self.draw(frame, ctx, at, None, false)
    }

    /// The captions, each visible word drawn by `draw(word, content) -> Svgr`.
    #[pyo3(signature = (frame, ctx, draw, *, at = None))]
    fn render_with(
        &self,
        frame: &PyFrame,
        ctx: &PyContext,
        draw: &Bound<'_, PyAny>,
        at: Option<f64>,
    ) -> PyResult<PySvgr> {
        self.draw(frame, ctx, at, Some(draw), false)
    }

    /// The captions, each active timed word drawn by `draw(word, content) -> Svgr`.
    #[pyo3(signature = (frame, ctx, draw, *, at = None))]
    fn highlight_with(
        &self,
        frame: &PyFrame,
        ctx: &PyContext,
        draw: &Bound<'_, PyAny>,
        at: Option<f64>,
    ) -> PyResult<PySvgr> {
        self.draw(frame, ctx, at, Some(draw), true)
    }
}

impl PyCaptions {
    fn draw(
        &self,
        frame: &PyFrame,
        ctx: &PyContext,
        at: Option<f64>,
        draw: Option<&Bound<'_, PyAny>>,
        active_only: bool,
    ) -> PyResult<PySvgr> {
        let ctx = ctx.get()?;
        let captions = self.inner();
        // A clone shares the caches of the frame and leaves the Python frame free for callbacks.
        let mut inner = frame.inner.clone();
        let error: RefCell<Option<PyErr>> = RefCell::new(None);
        let callback = |scope: &CaptionWordScope<'_, '_>, content: fframes::Svgr<'_>| {
            let Some(draw) = draw else {
                return own_nodes(content.as_subtree());
            };
            if (active_only && !scope.is_active()) || error.borrow().is_some() {
                return own_nodes(content.as_subtree());
            }
            let py = draw.py();
            let result = (|| {
                let word = Bound::new(
                    py,
                    PyCaptionWord {
                        scope: Cell::new((scope as *const CaptionWordScope<'_, '_>).cast()),
                    },
                )?;
                let content = PySvgr {
                    nodes: own_nodes(content.as_subtree()),
                };
                let out = draw.call1((&word, content));
                word.borrow().scope.set(std::ptr::null());
                let out = out?;
                if out.is_none() {
                    return Ok(Nodes::new());
                }
                match out.cast::<PySvgr>() {
                    Ok(svgr) => Ok(svgr.get().nodes.clone()),
                    Err(_) => Err(PyTypeError::new_err(
                        "a caption callback must return fframes.Svgr or None",
                    )),
                }
            })();
            result.unwrap_or_else(|e| {
                *error.borrow_mut() = Some(e);
                Nodes::new()
            })
        };
        let callback = |scope: &CaptionWordScope<'_, '_>, content: fframes::Svgr<'_>| {
            PySvgr::into_svgr(callback(scope, content))
        };
        let svg = match at {
            Some(at) => captions.render_at_with(at, &mut inner, ctx, callback),
            None => captions.render_with(&mut inner, ctx, callback),
        };
        if let Some(error) = error.into_inner() {
            return Err(error);
        }
        Ok(PySvgr {
            nodes: own_nodes(svg.as_subtree()),
        })
    }
}
