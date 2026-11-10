//! `fframes.wave_path`: a smooth closed SVG path through audio levels, for spectrum waves.

use std::fmt::Write;

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

/// The two Bezier control points of each segment of a smooth curve through `points`, found
/// with the Thomas algorithm (<https://www.particleincell.com/2012/bezier-splines/>).
fn control_points(points: &[f32]) -> (Vec<f32>, Vec<f32>) {
    let n = points.len() - 1;
    let mut p1 = vec![0.0; n + 1];
    let mut p2 = vec![0.0; n + 1];
    let mut a = vec![0.0; n + 1];
    let mut b = vec![0.0; n + 1];
    let mut c = vec![0.0; n + 1];
    let mut r = vec![0.0; n + 1];

    b[0] = 2.0;
    c[0] = 1.0;
    r[0] = points[0] + 2.0 * points[1];
    for i in 1..n {
        a[i] = 1.0;
        b[i] = 4.0;
        c[i] = 1.0;
        r[i] = 4.0 * points[i] + 2.0 * points[i + 1];
    }
    a[n - 1] = 2.0;
    b[n - 1] = 7.0;
    c[n - 1] = 0.0;
    r[n - 1] = 8.0 * points[n - 1] + points[n];

    for i in 1..n {
        let m = a[i] / b[i - 1];
        b[i] -= m * c[i - 1];
        r[i] -= m * r[i - 1];
    }
    p1[n - 1] = r[n - 1] / b[n - 1];
    for i in (0..n).rev() {
        p1[i] = (r[i] - c[i] * p1[i + 1]) / b[i];
    }
    for i in 0..n - 1 {
        p2[i] = 2.0 * points[i + 1] - p1[i + 1];
    }
    p2[n - 1] = f32::midpoint(points[n], p1[n - 1]);
    (p1, p2)
}

/// The `d` of a closed path through `levels`: point `i` is at `x = i * x_step` and
/// `y = baseline - min(level * y_scale, max_height)`, with a 0 level added at each end.
#[pyfunction]
#[pyo3(signature = (levels, x_step, y_scale, *, max_height = 600.0, baseline = 1080.0))]
pub fn wave_path(
    levels: Vec<f32>,
    x_step: usize,
    y_scale: f32,
    max_height: f32,
    baseline: f32,
) -> PyResult<String> {
    if levels.is_empty() {
        return Err(PyValueError::new_err("wave_path needs at least one level"));
    }
    let (xs, ys): (Vec<f32>, Vec<f32>) = std::iter::once(0.0)
        .chain(levels)
        .chain(std::iter::once(0.0))
        .enumerate()
        .map(|(i, level)| ((i * x_step) as f32, (level * y_scale).min(max_height)))
        .unzip();
    let (x1, x2) = control_points(&xs);
    let (y1, y2) = control_points(&ys);
    let mut path = String::new();
    for (index, (x, y)) in xs.into_iter().zip(ys).enumerate() {
        // Writing to a `String` can not fail.
        let _ = if index == 0 {
            write!(path, " M {} {}", x, baseline - y)
        } else {
            let i = index - 1;
            write!(
                path,
                " C {} {} {} {} {} {}",
                x1[i],
                baseline - y1[i],
                x2[i],
                baseline - y2[i],
                x,
                baseline - y
            )
        };
    }
    path.push_str(" z");
    Ok(path)
}
