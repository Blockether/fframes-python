//! `AnimationRuntime`: fframes `frame.animate_runtime`, for start seconds and values that
//! are known only while a frame renders.

use fframes::AnimateRuntimeInput;
use fframes::animation::AnimationRuntime;
use pyo3::IntoPyObjectExt;
use pyo3::exceptions::PyTypeError;
use pyo3::prelude::*;
use pyo3::types::{PyFloat, PyInt, PyTuple};

use crate::animation::easing_from_any;
use crate::frame::PyFrame;
use crate::values::PyTransform;

/// A resolved easing with a tween duration. Build it once (module level); call
/// `animate(frame, on_second, from_, to)` every frame.
#[pyclass(name = "AnimationRuntime", module = "fframes", frozen)]
pub struct PyAnimationRuntime {
    inner: AnimationRuntime,
}

fn run<T: fframes::animation::Animatable>(
    runtime: &AnimationRuntime,
    frame: &fframes::Frame,
    on_second: f32,
    from: T,
    to: T,
) -> T {
    frame.animate_runtime(AnimateRuntimeInput {
        on_second,
        from,
        to,
        animation_runtime: runtime,
    })
}

#[pymethods]
impl PyAnimationRuntime {
    /// `duration` seconds of `easing` (an `Easing` or its name). A spring ends when it settles,
    /// at most after `duration`.
    #[new]
    #[pyo3(signature = (duration, easing = None))]
    fn new(duration: f32, easing: Option<&Bound<'_, PyAny>>) -> PyResult<Self> {
        Ok(Self {
            inner: AnimationRuntime::new(duration, &easing_from_any(easing)?),
        })
    }

    /// The tween duration in seconds.
    #[getter]
    fn duration(&self) -> f32 {
        self.inner.get_duration()
    }

    /// The value at `frame` of a tween from `from_` to `to` that starts at `on_second`
    /// (scene seconds). Values: numbers, 2/3/4-tuples of numbers or transforms.
    fn animate(
        &self,
        py: Python<'_>,
        frame: &PyFrame,
        on_second: f32,
        from_: &Bound<'_, PyAny>,
        to: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
        let (rt, f) = (&self.inner, &frame.inner);
        if from_.is_instance_of::<PyFloat>() || from_.is_instance_of::<PyInt>() {
            return run(
                rt,
                f,
                on_second,
                from_.extract::<f32>()?,
                to.extract::<f32>()?,
            )
            .into_py_any(py);
        }
        if let Ok(from) = from_.cast::<PyTransform>() {
            let to = to.cast::<PyTransform>()?;
            return PyTransform(run(rt, f, on_second, from.get().0, to.get().0)).into_py_any(py);
        }
        if let Ok(tuple) = from_.cast::<PyTuple>() {
            return match tuple.len() {
                2 => run::<(f32, f32)>(rt, f, on_second, from_.extract()?, to.extract()?)
                    .into_py_any(py),
                3 => run::<(f32, f32, f32)>(rt, f, on_second, from_.extract()?, to.extract()?)
                    .into_py_any(py),
                4 => run::<(f32, f32, f32, f32)>(rt, f, on_second, from_.extract()?, to.extract()?)
                    .into_py_any(py),
                n => Err(PyTypeError::new_err(format!(
                    "a tuple value has 2, 3 or 4 numbers, not {n}"
                ))),
            };
        }
        Err(PyTypeError::new_err(format!(
            "can not animate {}: use numbers, tuples of numbers or Transform",
            from_.get_type().name()?
        )))
    }

    fn __repr__(&self) -> String {
        format!("AnimationRuntime(duration={})", self.inner.get_duration())
    }
}
