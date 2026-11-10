//! Generated audio: sample buffers for `Media(audio=...)` and the DSP blocks to make them fast.
//!
//! Buffers are `bytes` of little-endian `f32` (`numpy_array.astype("<f4").tobytes()`) or
//! sequences of numbers. The recursive parts of a synthesizer (noise, filters) run here;
//! the rest is plain numpy.

use std::borrow::Cow;
use std::f32::consts::TAU;

use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyTuple};

/// The samples of a buffer: `bytes` of little-endian `f32` or a sequence of numbers.
pub fn samples(obj: &Bound<'_, PyAny>) -> PyResult<Vec<f32>> {
    if let Ok(bytes) = obj.cast::<PyBytes>() {
        let bytes = bytes.as_bytes();
        if bytes.len() % 4 != 0 {
            return Err(PyValueError::new_err(
                "sample bytes must be a whole number of f32",
            ));
        }
        return Ok(bytes
            .as_chunks::<4>()
            .0
            .iter()
            .map(|b| f32::from_le_bytes(*b))
            .collect());
    }
    obj.extract::<Vec<f32>>().map_err(|_| {
        PyTypeError::new_err("samples must be bytes of little-endian f32 or a sequence of numbers")
    })
}

fn to_bytes<'py>(py: Python<'py>, values: &[f32]) -> Bound<'py, PyBytes> {
    PyBytes::new_with(py, values.len() * 4, |out| {
        for (chunk, value) in out.as_chunks_mut::<4>().0.iter_mut().zip(values) {
            chunk.copy_from_slice(&value.to_le_bytes());
        }
        Ok(())
    })
    .expect("filling bytes cannot fail")
}

/// Audio of `Media(audio=...)`: mono samples, or a `(left, right)` tuple of equal length.
pub fn audio_data(
    obj: &Bound<'_, PyAny>,
    sample_rate: u32,
) -> PyResult<fframes::media::PreloadedAudioData<'static>> {
    let (left, right) = match obj.cast::<PyTuple>() {
        Ok(pair) if pair.len() == 2 => {
            let (left, right) = (samples(&pair.get_item(0)?)?, samples(&pair.get_item(1)?)?);
            if left.len() != right.len() {
                return Err(PyValueError::new_err("left and right need the same length"));
            }
            (left, Some(right))
        }
        _ => (samples(obj)?, None),
    };
    Ok(fframes::media::PreloadedAudioData {
        samples: Cow::Owned(left),
        sample_rate,
        right: right.map(Cow::Owned),
    })
}

/// White noise in -1..1 from a xorshift32 state. Values continue across calls.
#[pyclass(name = "Noise", module = "fframes")]
pub struct PyNoise {
    state: u32,
}

#[pymethods]
impl PyNoise {
    #[new]
    fn new(seed: u32) -> PyResult<Self> {
        if seed == 0 {
            return Err(PyValueError::new_err("the seed of Noise must not be 0"));
        }
        Ok(Self { state: seed })
    }

    /// The next `n` values as `bytes` of little-endian f32.
    fn take<'py>(&mut self, py: Python<'py>, n: usize) -> Bound<'py, PyBytes> {
        let values: Vec<f32> = (0..n)
            .map(|_| {
                self.state ^= self.state << 13;
                self.state ^= self.state >> 17;
                self.state ^= self.state << 5;
                (self.state as f32 / u32::MAX as f32) * 2.0 - 1.0
            })
            .collect();
        to_bytes(py, &values)
    }
}

/// `samples` through an RBJ biquad: `kind` is "low", "high" or "band". `freq` is one cutoff
/// in Hz or a buffer with one cutoff per sample. Returns `bytes` of little-endian f32.
#[pyfunction]
#[pyo3(signature = (kind, samples, freq, q, sample_rate = 48_000.0))]
pub fn biquad<'py>(
    py: Python<'py>,
    kind: &str,
    samples: &Bound<'py, PyAny>,
    freq: &Bound<'py, PyAny>,
    q: f32,
    sample_rate: f32,
) -> PyResult<Bound<'py, PyBytes>> {
    let kind = match kind {
        "low" => Kind::Low,
        "high" => Kind::High,
        "band" => Kind::Band,
        _ => {
            return Err(PyValueError::new_err(
                "kind must be 'low', 'high' or 'band'",
            ));
        }
    };
    let input = self::samples(samples)?;
    let freqs = match freq.extract::<f32>() {
        Ok(freq) => vec![freq],
        Err(_) => self::samples(freq)?,
    };
    if freqs.len() != 1 && freqs.len() != input.len() {
        return Err(PyValueError::new_err(
            "freq needs one value or one per sample",
        ));
    }
    let output = py.detach(|| {
        let mut filter = Biquad::default();
        filter.set(kind, freqs[0], q, sample_rate);
        input
            .iter()
            .enumerate()
            .map(|(i, x)| {
                if freqs.len() > 1 {
                    filter.set(kind, freqs[i], q, sample_rate);
                }
                filter.run(*x)
            })
            .collect::<Vec<f32>>()
    });
    Ok(to_bytes(py, &output))
}

/// One value or one per sample: a number or a buffer.
fn values_or_one(obj: &Bound<'_, PyAny>) -> PyResult<Vec<f32>> {
    match obj.extract::<f32>() {
        Ok(value) => Ok(vec![value]),
        Err(_) => samples(obj),
    }
}

/// `n` samples of a saw oscillator without aliasing (polyBLEP) from `phase` (0..1), in f32
/// like the Rust examples. `freq` is one frequency in Hz or one per sample.
#[pyfunction]
#[pyo3(signature = (freq, n, phase = 0.0, sample_rate = 48_000.0))]
pub fn saw<'py>(
    py: Python<'py>,
    freq: &Bound<'py, PyAny>,
    n: usize,
    phase: f32,
    sample_rate: f32,
) -> PyResult<Bound<'py, PyBytes>> {
    let freqs = values_or_one(freq)?;
    if freqs.len() != 1 && freqs.len() != n {
        return Err(PyValueError::new_err("freq needs one value or n values"));
    }
    let output = py.detach(|| {
        let mut phase = phase;
        (0..n)
            .map(|i| {
                let dt = freqs[if freqs.len() == 1 { 0 } else { i }] / sample_rate;
                phase += dt;
                if phase >= 1.0 {
                    phase -= 1.0;
                }
                let t = phase;
                let blep = if t < dt {
                    let t = t / dt;
                    t + t - t * t - 1.0
                } else if t > 1.0 - dt {
                    let t = (t - 1.0) / dt;
                    t * t + t + t + 1.0
                } else {
                    0.0
                };
                2.0 * t - 1.0 - blep
            })
            .collect::<Vec<f32>>()
    });
    Ok(to_bytes(py, &output))
}

/// Rust `f32` math over buffers, bit for bit the same as `f32::sin` and the others:
/// `op` is "sin", "cos", "exp", "tanh" (of `x`), "powf" (`x` to the power `y`) or "sin_cos"
/// (`f32::sin_cos` of `x`: sine and cosine of each value, in turns). The compiler can join a
/// sine and a cosine of one value into one `sincos` call, whose results are not always those
/// of "sin" and "cos". `x` and `y` are numbers or buffers of one length. Returns `bytes` of
/// little-endian f32.
#[pyfunction]
#[pyo3(signature = (op, x, y = None))]
pub fn f32_math<'py>(
    py: Python<'py>,
    op: &str,
    x: &Bound<'py, PyAny>,
    y: Option<&Bound<'py, PyAny>>,
) -> PyResult<Bound<'py, PyBytes>> {
    let x = values_or_one(x)?;
    if op == "sin_cos" {
        if y.is_some() {
            return Err(PyValueError::new_err("only powf takes y"));
        }
        let output = x
            .iter()
            .flat_map(|v| {
                let (s, c) = v.sin_cos();
                [s, c]
            })
            .collect::<Vec<f32>>();
        return Ok(to_bytes(py, &output));
    }
    let unary: Option<fn(f32) -> f32> = match op {
        "sin" => Some(f32::sin),
        "cos" => Some(f32::cos),
        "exp" => Some(f32::exp),
        "tanh" => Some(f32::tanh),
        "powf" => None,
        _ => {
            return Err(PyValueError::new_err(format!(
                "unknown op {op:?}: use sin, cos, exp, tanh, powf or sin_cos"
            )));
        }
    };
    let output = match (unary, y) {
        (Some(f), None) => x.iter().map(|v| f(*v)).collect::<Vec<f32>>(),
        (None, Some(y)) => {
            let y = values_or_one(y)?;
            let n = x.len().max(y.len());
            if (x.len() != 1 && x.len() != n) || (y.len() != 1 && y.len() != n) {
                return Err(PyValueError::new_err("x and y need one length"));
            }
            let at = |v: &[f32], i: usize| v[if v.len() == 1 { 0 } else { i }];
            (0..n).map(|i| at(&x, i).powf(at(&y, i))).collect()
        }
        _ => return Err(PyValueError::new_err("only powf takes y")),
    };
    Ok(to_bytes(py, &output))
}

#[derive(Clone, Copy)]
enum Kind {
    Low,
    High,
    Band,
}

#[derive(Default)]
struct Biquad {
    b: [f32; 3],
    a: [f32; 2],
    x: [f32; 2],
    y: [f32; 2],
}

impl Biquad {
    fn set(&mut self, kind: Kind, freq: f32, q: f32, rate: f32) {
        let w = TAU * freq.clamp(10.0, rate * 0.45) / rate;
        let (sin, cos) = w.sin_cos();
        let alpha = sin / (2.0 * q);
        let a0 = 1.0 + alpha;
        let b = match kind {
            Kind::Low => [(1.0 - cos) / 2.0, 1.0 - cos, (1.0 - cos) / 2.0],
            Kind::High => [
                f32::midpoint(1.0, cos),
                -(1.0 + cos),
                f32::midpoint(1.0, cos),
            ],
            Kind::Band => [alpha, 0.0, -alpha],
        };
        self.b = b.map(|v| v / a0);
        self.a = [-2.0 * cos / a0, (1.0 - alpha) / a0];
    }

    fn run(&mut self, x: f32) -> f32 {
        let y = self.b[0] * x + self.b[1] * self.x[0] + self.b[2] * self.x[1]
            - self.a[0] * self.y[0]
            - self.a[1] * self.y[1];
        self.x = [x, self.x[0]];
        self.y = [y, self.y[0]];
        y
    }
}

/// The phase (0..1) of an oscillator after each of `n` steps: `phase = (phase + step).fract()`
/// in f32. `step` is one phase step (frequency / sample rate) or one per sample.
#[pyfunction]
#[pyo3(signature = (step, n, phase = 0.0))]
pub fn phasor<'py>(
    py: Python<'py>,
    step: &Bound<'py, PyAny>,
    n: usize,
    phase: f32,
) -> PyResult<Bound<'py, PyBytes>> {
    let steps = values_or_one(step)?;
    if steps.len() != 1 && steps.len() != n {
        return Err(PyValueError::new_err("step needs one value or n values"));
    }
    let output = py.detach(|| {
        let mut phase = phase;
        (0..n)
            .map(|i| {
                phase = (phase + steps[if steps.len() == 1 { 0 } else { i }]).fract();
                phase
            })
            .collect::<Vec<f32>>()
    });
    Ok(to_bytes(py, &output))
}

/// `n` samples of a sine oscillator from `phase` (0..1): each sample is `sin(phase * TAU)`,
/// then `phase = (phase + freq / sample_rate).fract()`, in f32. `freq` is one frequency in
/// Hz or one per sample.
#[pyfunction]
#[pyo3(signature = (freq, n, phase = 0.0, sample_rate = 48_000.0))]
pub fn sine<'py>(
    py: Python<'py>,
    freq: &Bound<'py, PyAny>,
    n: usize,
    phase: f32,
    sample_rate: f32,
) -> PyResult<Bound<'py, PyBytes>> {
    let freqs = values_or_one(freq)?;
    if freqs.len() != 1 && freqs.len() != n {
        return Err(PyValueError::new_err("freq needs one value or n values"));
    }
    let output = py.detach(|| {
        let mut phase = phase;
        (0..n)
            .map(|i| {
                let y = (phase * TAU).sin();
                phase = (phase + freqs[if freqs.len() == 1 { 0 } else { i }] / sample_rate).fract();
                y
            })
            .collect::<Vec<f32>>()
    });
    Ok(to_bytes(py, &output))
}

/// A one-pole smoother: `value += (target - value) * coef` for each sample, from `value`.
/// Returns the value after each step.
#[pyfunction]
#[pyo3(signature = (target, coef, value = 0.0))]
pub fn one_pole<'py>(
    py: Python<'py>,
    target: &Bound<'py, PyAny>,
    coef: f32,
    value: f32,
) -> PyResult<Bound<'py, PyBytes>> {
    let target = samples(target)?;
    let output = py.detach(|| {
        let mut value = value;
        target
            .iter()
            .map(|t| {
                value += (t - value) * coef;
                value
            })
            .collect::<Vec<f32>>()
    });
    Ok(to_bytes(py, &output))
}

/// `n` samples of a Karplus-Strong string: the delay line starts as `excitation`, and each
/// read replaces a value with the midpoint of it and the next value, times `damping`.
#[pyfunction]
pub fn karplus_strong<'py>(
    py: Python<'py>,
    excitation: &Bound<'py, PyAny>,
    n: usize,
    damping: f32,
) -> PyResult<Bound<'py, PyBytes>> {
    let mut buf = samples(excitation)?;
    if buf.is_empty() {
        return Err(PyValueError::new_err("excitation must not be empty"));
    }
    let output = py.detach(|| {
        let len = buf.len();
        let mut i = 0;
        (0..n)
            .map(|_| {
                let j = if i + 1 == len { 0 } else { i + 1 };
                let y = buf[i];
                buf[i] = f32::midpoint(buf[i], buf[j]) * damping;
                i = j;
                y
            })
            .collect::<Vec<f32>>()
    });
    Ok(to_bytes(py, &output))
}

/// A Freeverb comb filter with a delay of `size` samples: returns the delayed value of each
/// sample. The low pass `store = y * (1 - damp) + store * damp` feeds back with `feedback`,
/// and the input enters scaled by `gain`.
#[pyfunction]
#[pyo3(signature = (samples, size, feedback, damp, gain = 0.015))]
pub fn comb<'py>(
    py: Python<'py>,
    samples: &Bound<'py, PyAny>,
    size: usize,
    feedback: f32,
    damp: f32,
    gain: f32,
) -> PyResult<Bound<'py, PyBytes>> {
    let input = self::samples(samples)?;
    if size == 0 {
        return Err(PyValueError::new_err("size must be at least 1"));
    }
    let output = py.detach(|| {
        let mut buf = vec![0.0f32; size];
        let mut idx = 0;
        let mut store = 0.0f32;
        input
            .iter()
            .map(|x| {
                let y = buf[idx];
                store = y * (1.0 - damp) + store * damp;
                buf[idx] = x * gain + store * feedback;
                idx = if idx + 1 == size { 0 } else { idx + 1 };
                y
            })
            .collect::<Vec<f32>>()
    });
    Ok(to_bytes(py, &output))
}

/// A Freeverb all-pass filter with a delay of `size` samples: `y = -x + b` and the delay
/// line takes `x + b * feedback`, where `b` is the delayed value.
#[pyfunction]
#[pyo3(signature = (samples, size, feedback = 0.5))]
pub fn allpass<'py>(
    py: Python<'py>,
    samples: &Bound<'py, PyAny>,
    size: usize,
    feedback: f32,
) -> PyResult<Bound<'py, PyBytes>> {
    let input = self::samples(samples)?;
    if size == 0 {
        return Err(PyValueError::new_err("size must be at least 1"));
    }
    let output = py.detach(|| {
        let mut buf = vec![0.0f32; size];
        let mut idx = 0;
        input
            .iter()
            .map(|x| {
                let b = buf[idx];
                let y = -*x + b;
                buf[idx] = *x + b * feedback;
                idx = if idx + 1 == size { 0 } else { idx + 1 };
                y
            })
            .collect::<Vec<f32>>()
    });
    Ok(to_bytes(py, &output))
}
