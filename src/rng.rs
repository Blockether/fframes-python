//! `Rng`: the seeded `rand` 0.8 `StdRng` that Rust examples use, so that a Python port makes
//! the same random choices as the Rust original for the same seed.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyList;
use rand::rngs::StdRng;
use rand::seq::SliceRandom;
use rand::{Rng, SeedableRng};

/// `rand` 0.8 `StdRng::seed_from_u64(seed)`. Each draw names the Rust type of its range,
/// because `rand` samples each type differently.
#[pyclass(name = "Rng", module = "fframes")]
pub struct PyRng {
    inner: StdRng,
}

macro_rules! range {
    ($rng:expr, $t:ty, $lo:expr, $hi:expr, $inclusive:expr) => {{
        let (lo, hi): ($t, $t) = ($lo.extract()?, $hi.extract()?);
        if $inclusive {
            if lo > hi {
                return Err(PyValueError::new_err("empty range"));
            }
            $rng.gen_range(lo..=hi).into_pyobject_or_pyerr()
        } else {
            if lo >= hi {
                return Err(PyValueError::new_err("empty range"));
            }
            $rng.gen_range(lo..hi).into_pyobject_or_pyerr()
        }
    }};
}

trait IntoPy {
    fn into_pyobject_or_pyerr(self) -> PyResult<Py<PyAny>>;
}

impl<T> IntoPy for T
where
    T: for<'py> IntoPyObject<'py>,
{
    fn into_pyobject_or_pyerr(self) -> PyResult<Py<PyAny>> {
        Python::attach(|py| pyo3::IntoPyObjectExt::into_py_any(self, py))
    }
}

#[pymethods]
impl PyRng {
    #[new]
    fn new(seed: u64) -> Self {
        Self {
            inner: StdRng::seed_from_u64(seed),
        }
    }

    /// `rng.gen_range(lo..hi)` (`lo..=hi` with `inclusive=True`) for the Rust type `kind`:
    /// "f32", "f64", "i32", "u32", "i64", "u64" or "usize".
    #[pyo3(signature = (lo, hi, kind = "f64", inclusive = false))]
    fn range(
        &mut self,
        lo: &Bound<'_, PyAny>,
        hi: &Bound<'_, PyAny>,
        kind: &str,
        inclusive: bool,
    ) -> PyResult<Py<PyAny>> {
        let rng = &mut self.inner;
        match kind {
            "f32" => range!(rng, f32, lo, hi, inclusive),
            "f64" => range!(rng, f64, lo, hi, inclusive),
            "i32" => range!(rng, i32, lo, hi, inclusive),
            "u32" => range!(rng, u32, lo, hi, inclusive),
            "i64" => range!(rng, i64, lo, hi, inclusive),
            "u64" => range!(rng, u64, lo, hi, inclusive),
            "usize" => range!(rng, usize, lo, hi, inclusive),
            _ => Err(PyValueError::new_err(format!("unknown kind {kind:?}"))),
        }
    }

    /// `rng.gen_bool(p)`.
    fn bool(&mut self, p: f64) -> PyResult<bool> {
        if !(0.0..=1.0).contains(&p) {
            return Err(PyValueError::new_err("p must be in 0..=1"));
        }
        Ok(self.inner.gen_bool(p))
    }

    /// `items.shuffle(rng)`: a new list in shuffled order.
    fn shuffle<'py>(
        &mut self,
        py: Python<'py>,
        items: Vec<Py<PyAny>>,
    ) -> PyResult<Bound<'py, PyList>> {
        let mut items = items;
        items.shuffle(&mut self.inner);
        PyList::new(py, items)
    }

    /// `items.choose(rng)`: one item, or `None` for an empty list.
    fn choose(&mut self, py: Python<'_>, items: Vec<Py<PyAny>>) -> Option<Py<PyAny>> {
        items.choose(&mut self.inner).map(|item| item.clone_ref(py))
    }
}
