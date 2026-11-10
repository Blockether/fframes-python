//! `Easing` and `timeline(...)`: keyframe animations evaluated by `frame.animate(timeline)`.

use fframes::animation::{Easing, KeyFrame, KeyFramesAnimation};
use pyo3::IntoPyObjectExt;
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyFloat, PyInt, PyString, PyTuple};

use crate::values::{PyColor, PyTransform, color_from_any};

/// How a value moves between two keyframes.
#[pyclass(name = "Easing", module = "fframes", frozen, from_py_object)]
#[derive(Clone, Copy)]
pub struct PyEasing(pub Easing);

#[pymethods]
impl PyEasing {
    #[classattr]
    const LINEAR: PyEasing = PyEasing(Easing::Linear);
    #[classattr]
    const EASE_IN: PyEasing = PyEasing(Easing::EaseIn);
    #[classattr]
    const EASE_OUT: PyEasing = PyEasing(Easing::EaseOut);
    #[classattr]
    const EASE_IN_OUT: PyEasing = PyEasing(Easing::EaseInOut);

    /// CSS `cubic-bezier(x1, y1, x2, y2)`.
    #[staticmethod]
    fn cubic_bezier(x1: f32, y1: f32, x2: f32, y2: f32) -> Self {
        Self(Easing::CubicBezier(x1, y1, x2, y2))
    }

    /// Spring physics; the tween lasts until the spring settles.
    #[staticmethod]
    #[pyo3(signature = (mass = 1.0, stiffness = 100.0, damping = 10.0))]
    fn spring(mass: f32, stiffness: f32, damping: f32) -> Self {
        Self(Easing::Spring {
            mass,
            stiffness,
            damping,
        })
    }

    fn __repr__(&self) -> String {
        format!("Easing.{:?}", self.0)
    }
}

/// An easing from an `Easing` or a name: "linear", "ease-in", "ease-out", "ease-in-out".
pub fn easing_from_any(value: Option<&Bound<'_, PyAny>>) -> PyResult<Easing> {
    let Some(value) = value else {
        return Ok(Easing::Linear);
    };
    if value.is_none() {
        return Ok(Easing::Linear);
    }
    if let Ok(easing) = value.cast::<PyEasing>() {
        return Ok(easing.get().0);
    }
    if let Ok(name) = value.cast::<PyString>() {
        let name = name.to_cow()?.to_ascii_lowercase().replace('_', "-");
        return match name.as_str() {
            "linear" => Ok(Easing::Linear),
            "ease-in" | "easein" => Ok(Easing::EaseIn),
            "ease-out" | "easeout" => Ok(Easing::EaseOut),
            "ease-in-out" | "easeinout" => Ok(Easing::EaseInOut),
            "spring" => Ok(Easing::Spring {
                mass: 1.0,
                stiffness: 100.0,
                damping: 10.0,
            }),
            _ => Err(PyValueError::new_err(format!("unknown easing {name:?}"))),
        };
    }
    Err(PyTypeError::new_err("easing must be an Easing or its name"))
}

/// The animated value type of a timeline.
pub enum Animation {
    Number(KeyFramesAnimation<f32>),
    Pair(KeyFramesAnimation<(f32, f32)>),
    Triple(KeyFramesAnimation<(f32, f32, f32)>),
    Quad(KeyFramesAnimation<(f32, f32, f32, f32)>),
    Color(KeyFramesAnimation<fframes::Color>),
    Transform(KeyFramesAnimation<fframes::Transform>),
}

/// One `(start, end, from, to, easing)` keyframe before typing.
struct RawKey<'py> {
    start: f32,
    end: Option<f32>,
    from: Bound<'py, PyAny>,
    to: Bound<'py, PyAny>,
    easing: Easing,
}

fn build<T, F>(keys: &[RawKey<'_>], convert: F) -> PyResult<KeyFramesAnimation<T>>
where
    T: fframes::animation::Animatable + Copy + Default,
    F: Fn(&Bound<'_, PyAny>) -> PyResult<T>,
{
    let mut frames = Vec::with_capacity(keys.len());
    for key in keys {
        frames.push(KeyFrame {
            start: key.start,
            end: key.end,
            from: convert(&key.from)?,
            to: convert(&key.to)?,
            easing: &key.easing,
        });
    }
    Ok(KeyFramesAnimation::new(frames))
}

fn number(value: &Bound<'_, PyAny>) -> PyResult<f32> {
    value.extract::<f32>()
}

impl Animation {
    fn from_keys(keys: &[RawKey<'_>]) -> PyResult<Self> {
        let first = &keys
            .first()
            .ok_or_else(|| PyValueError::new_err("a timeline needs at least one keyframe"))?
            .from;
        if first.is_instance_of::<PyFloat>() || first.is_instance_of::<PyInt>() {
            return Ok(Self::Number(build(keys, number)?));
        }
        if first.is_instance_of::<PyColor>() || first.is_instance_of::<PyString>() {
            return Ok(Self::Color(build(keys, color_from_any)?));
        }
        if let Ok(transform) = first.cast::<PyTransform>() {
            let _ = transform;
            return Ok(Self::Transform(build(keys, |v| {
                Ok(v.cast::<PyTransform>()?.get().0)
            })?));
        }
        if let Ok(tuple) = first.cast::<PyTuple>() {
            return match tuple.len() {
                2 => Ok(Self::Pair(build(keys, |v| v.extract())?)),
                3 => Ok(Self::Triple(build(keys, |v| v.extract())?)),
                4 => Ok(Self::Quad(build(keys, |v| v.extract())?)),
                n => Err(PyValueError::new_err(format!(
                    "a tuple value has 2, 3 or 4 numbers, not {n}"
                ))),
            };
        }
        Err(PyTypeError::new_err(format!(
            "can not animate {}: use numbers, tuples of numbers, Color or Transform",
            first.get_type().name()?
        )))
    }

    /// The value of the animation for `frame` (`looped` repeats it).
    pub fn eval(
        &self,
        py: Python<'_>,
        frame: &fframes::Frame,
        looped: bool,
    ) -> PyResult<Py<PyAny>> {
        macro_rules! run {
            ($a:expr) => {
                if looped {
                    frame.animate_loop($a)
                } else {
                    frame.animate($a)
                }
            };
        }
        match self {
            Self::Number(a) => run!(a).into_py_any(py),
            Self::Pair(a) => run!(a).into_py_any(py),
            Self::Triple(a) => run!(a).into_py_any(py),
            Self::Quad(a) => run!(a).into_py_any(py),
            Self::Color(a) => PyColor(run!(a)).into_py_any(py),
            Self::Transform(a) => PyTransform(run!(a)).into_py_any(py),
        }
    }

    pub fn total_duration(&self) -> f32 {
        match self {
            Self::Number(a) => a.total_duration,
            Self::Pair(a) => a.total_duration,
            Self::Triple(a) => a.total_duration,
            Self::Quad(a) => a.total_duration,
            Self::Color(a) => a.total_duration,
            Self::Transform(a) => a.total_duration,
        }
    }
}

/// Keyframes of one value. Build it once (module level), animate it every frame.
#[pyclass(name = "Timeline", module = "fframes", frozen)]
pub struct PyTimeline {
    pub animation: Animation,
}

#[pymethods]
impl PyTimeline {
    /// Seconds from the first keyframe to the end of the last one.
    #[getter]
    fn duration(&self) -> f32 {
        self.animation.total_duration()
    }
}

fn raw_key<'py>(item: &Bound<'py, PyAny>) -> PyResult<RawKey<'py>> {
    let tuple = item.cast::<PyTuple>().map_err(|_| {
        PyTypeError::new_err(
            "a keyframe is (at, from, to[, easing]) where at is a second or (start, end)",
        )
    })?;
    if !(3..=4).contains(&tuple.len()) {
        return Err(PyValueError::new_err(
            "a keyframe is (at, from, to[, easing])",
        ));
    }
    let at = tuple.get_item(0)?;
    let (start, end) = if let Ok((start, end)) = at.extract::<(f32, f32)>() {
        (start, Some(end))
    } else {
        (at.extract::<f32>()?, None)
    };
    let easing = if tuple.len() == 4 {
        Some(tuple.get_item(3)?)
    } else {
        None
    };
    Ok(RawKey {
        start,
        end,
        from: tuple.get_item(1)?,
        to: tuple.get_item(2)?,
        easing: easing_from_any(easing.as_ref())?,
    })
}

/// `timeline((0, 0.0, 1.0, Easing.EASE_OUT), ((2, 3), 1.0, 0.0))`: keyframes `(at, from, to[,
/// easing])`, `at` a start second or `(start, end)`. Values: numbers, 2/3/4-tuples, colors
/// (Color or CSS strings) or transforms. Mirrors fframes `timeline!`.
#[pyfunction]
#[pyo3(signature = (*keyframes))]
pub fn timeline(keyframes: &Bound<'_, PyTuple>) -> PyResult<PyTimeline> {
    let items: Vec<Bound<'_, PyAny>> =
        if keyframes.len() == 1 && !keyframes.get_item(0)?.is_instance_of::<PyTuple>() {
            keyframes
                .get_item(0)?
                .try_iter()?
                .collect::<PyResult<_>>()?
        } else {
            keyframes.iter().collect()
        };
    let keys = items.iter().map(raw_key).collect::<PyResult<Vec<_>>>()?;
    Ok(PyTimeline {
        animation: Animation::from_keys(&keys)?,
    })
}
