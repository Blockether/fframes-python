//! Values that go into templates and animations: colors, transforms, images and paths.

use std::str::FromStr;
use std::sync::Arc;

use fframes::usvgr::svgtree::svgrtypes;
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyString, PyTuple};

/// An sRGB color with alpha, `Color.hex("#ff8800")` or `Color(255, 136, 0)`.
#[pyclass(name = "Color", module = "fframes", frozen, eq, hash, from_py_object)]
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
pub struct PyColor(pub fframes::Color);

/// A color from a `Color` or a CSS color string (`"#fff"`, `"red"`, `"rgb(1, 2, 3)"`).
pub fn color_from_any(value: &Bound<'_, PyAny>) -> PyResult<fframes::Color> {
    if let Ok(color) = value.cast::<PyColor>() {
        return Ok(color.get().0);
    }
    if let Ok(text) = value.cast::<PyString>() {
        return parse_color(&text.to_cow()?);
    }
    if let Ok(tuple) = value.cast::<PyTuple>() {
        let parts: Vec<u8> = tuple.extract()?;
        return match parts.as_slice() {
            [r, g, b] => Ok(fframes::Color::rgb(*r, *g, *b)),
            [r, g, b, a] => Ok(fframes::Color::rgba(*r, *g, *b, *a)),
            _ => Err(PyValueError::new_err("a color tuple has 3 or 4 items")),
        };
    }
    Err(PyTypeError::new_err(format!(
        "expected a Color or a CSS color string, not {}",
        value.get_type().name()?
    )))
}

fn parse_color(text: &str) -> PyResult<fframes::Color> {
    let color = svgrtypes::Color::from_str(text.trim())
        .map_err(|_| PyValueError::new_err(format!("not a color: {text:?}")))?;
    Ok(fframes::Color::rgba(
        color.red,
        color.green,
        color.blue,
        color.alpha,
    ))
}

#[pymethods]
impl PyColor {
    #[new]
    #[pyo3(signature = (r, g, b, a = 255))]
    fn new(r: u8, g: u8, b: u8, a: u8) -> Self {
        Self(fframes::Color::rgba(r, g, b, a))
    }

    /// `#rgb`, `#rgba`, `#rrggbb` or `#rrggbbaa`, also any CSS color.
    #[staticmethod]
    fn hex(value: &str) -> PyResult<Self> {
        parse_color(value).map(Self)
    }

    /// Any CSS color, or a `Color` (returned as is).
    #[staticmethod]
    fn parse(value: &Bound<'_, PyAny>) -> PyResult<Self> {
        color_from_any(value).map(Self)
    }

    #[staticmethod]
    fn rgb(r: u8, g: u8, b: u8) -> Self {
        Self(fframes::Color::rgb(r, g, b))
    }

    #[staticmethod]
    fn rgba(r: u8, g: u8, b: u8, a: u8) -> Self {
        Self(fframes::Color::rgba(r, g, b, a))
    }

    fn with_alpha(&self, a: u8) -> Self {
        Self(self.0.with_alpha(a))
    }

    #[getter]
    fn r(&self) -> u8 {
        self.0.r
    }
    #[getter]
    fn g(&self) -> u8 {
        self.0.g
    }
    #[getter]
    fn b(&self) -> u8 {
        self.0.b
    }
    #[getter]
    fn a(&self) -> u8 {
        self.0.a
    }

    fn is_transparent(&self) -> bool {
        self.0.is_transparent()
    }

    fn is_opaque(&self) -> bool {
        self.0.is_opaque()
    }

    fn __str__(&self) -> String {
        self.0.to_string()
    }

    fn __repr__(&self) -> String {
        format!(
            "Color({}, {}, {}, {})",
            self.0.r, self.0.g, self.0.b, self.0.a
        )
    }

    #[classattr]
    const BLACK: PyColor = PyColor(fframes::Color::BLACK);
    #[classattr]
    const WHITE: PyColor = PyColor(fframes::Color::WHITE);
    #[classattr]
    const TRANSPARENT: PyColor = PyColor(fframes::Color::TRANSPARENT);
}

/// translate -> rotate -> scale -> skew, like fframes `Transform`. Animatable.
#[pyclass(name = "Transform", module = "fframes", frozen, eq, from_py_object)]
#[derive(Clone, Copy, PartialEq)]
pub struct PyTransform(pub fframes::Transform);

fn rotate_from(value: &Bound<'_, PyAny>) -> PyResult<fframes::Rotate> {
    if let Ok((angle, (x, y))) = value.extract::<(f64, (f64, f64))>() {
        return Ok(fframes::Rotate {
            angle,
            origin: Some((x, y)),
        });
    }
    Ok(fframes::Rotate {
        angle: value.extract()?,
        origin: None,
    })
}

fn scale_from(value: &Bound<'_, PyAny>) -> PyResult<fframes::Scale> {
    if let Ok((x, y)) = value.extract::<(f64, f64)>() {
        return Ok(fframes::Scale { x, y });
    }
    let factor: f64 = value.extract()?;
    Ok(fframes::Scale {
        x: factor,
        y: factor,
    })
}

#[pymethods]
impl PyTransform {
    /// `Transform(translate=(x, y), rotate=deg | (deg, (ox, oy)), scale=s | (sx, sy), skew=(x, y))`
    #[new]
    #[pyo3(signature = (*, translate = None, rotate = None, scale = None, skew = None))]
    fn new(
        translate: Option<(f64, f64)>,
        rotate: Option<&Bound<'_, PyAny>>,
        scale: Option<&Bound<'_, PyAny>>,
        skew: Option<(f64, f64)>,
    ) -> PyResult<Self> {
        let mut t = fframes::Transform::default();
        if let Some((x, y)) = translate {
            t.translate_x = x;
            t.translate_y = y;
        }
        if let Some(rotate) = rotate {
            t.rotate = rotate_from(rotate)?;
        }
        if let Some(scale) = scale {
            t.scale = scale_from(scale)?;
        }
        if let Some((x, y)) = skew {
            t.skew_x = x;
            t.skew_y = y;
        }
        Ok(Self(t))
    }

    #[staticmethod]
    fn translate(x: f64, y: f64) -> Self {
        Self(fframes::Transform::translate(x, y))
    }

    /// Degrees, around `origin` when given.
    #[staticmethod]
    #[pyo3(signature = (angle, origin = None))]
    fn rotate(angle: f64, origin: Option<(f64, f64)>) -> Self {
        Self(fframes::Transform {
            rotate: fframes::Rotate { angle, origin },
            ..Default::default()
        })
    }

    #[staticmethod]
    #[pyo3(signature = (x, y = None))]
    fn scale(x: f64, y: Option<f64>) -> Self {
        Self(fframes::Transform::scale((x, y.unwrap_or(x))))
    }

    #[staticmethod]
    fn skew(x: f64, y: f64) -> Self {
        Self(fframes::Transform::skew(x, y))
    }

    /// A copy with the given parts replaced.
    #[pyo3(signature = (*, translate = None, rotate = None, scale = None, skew = None))]
    fn replace(
        &self,
        translate: Option<(f64, f64)>,
        rotate: Option<&Bound<'_, PyAny>>,
        scale: Option<&Bound<'_, PyAny>>,
        skew: Option<(f64, f64)>,
    ) -> PyResult<Self> {
        let mut t = self.0;
        if let Some((x, y)) = translate {
            t.translate_x = x;
            t.translate_y = y;
        }
        if let Some(rotate) = rotate {
            t.rotate = rotate_from(rotate)?;
        }
        if let Some(scale) = scale {
            t.scale = scale_from(scale)?;
        }
        if let Some((x, y)) = skew {
            t.skew_x = x;
            t.skew_y = y;
        }
        Ok(Self(t))
    }

    #[getter]
    fn translate_x(&self) -> f64 {
        self.0.translate_x
    }
    #[getter]
    fn translate_y(&self) -> f64 {
        self.0.translate_y
    }
    #[getter]
    fn rotation(&self) -> f64 {
        self.0.rotate.angle
    }
    #[getter]
    fn rotation_origin(&self) -> Option<(f64, f64)> {
        self.0.rotate.origin
    }
    #[getter]
    fn scale_x(&self) -> f64 {
        self.0.scale.x
    }
    #[getter]
    fn scale_y(&self) -> f64 {
        self.0.scale.y
    }
    #[getter]
    fn skew_x(&self) -> f64 {
        self.0.skew_x
    }
    #[getter]
    fn skew_y(&self) -> f64 {
        self.0.skew_y
    }

    fn __str__(&self) -> String {
        self.0.to_string()
    }

    fn __repr__(&self) -> String {
        format!("Transform({:?})", self.0.to_string())
    }
}

/// An image to use as `href` of `<image>`: decoded once, drawn many times.
#[pyclass(name = "Image", module = "fframes", frozen)]
pub struct PyImage {
    pub data: Arc<fframes::usvgr::PreloadedImageData>,
}

#[pymethods]
impl PyImage {
    #[getter]
    fn width(&self) -> u32 {
        self.data.width
    }

    #[getter]
    fn height(&self) -> u32 {
        self.data.height
    }

    fn __repr__(&self) -> String {
        format!("Image({}x{})", self.data.width, self.data.height)
    }
}

/// Path geometry parsed once: `Path("M0 0 L10 10")` as `d={path}`.
#[pyclass(name = "Path", module = "fframes", frozen)]
pub struct PyPath {
    pub segments: Vec<svgrtypes::PathSegment>,
}

#[pymethods]
impl PyPath {
    #[new]
    fn new(d: &str) -> PyResult<Self> {
        let segments = svgrtypes::PathParser::from(d)
            .collect::<Result<Vec<_>, _>>()
            .map_err(|err| PyValueError::new_err(format!("invalid path data: {err}")))?;
        Ok(Self { segments })
    }

    fn __len__(&self) -> usize {
        self.segments.len()
    }
}
