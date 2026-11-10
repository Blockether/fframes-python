//! `fframes.three_d`: 3D scenes with the building blocks of three.js, rendered into an
//! `Image` for an `<image>` of the frame.
//!
//! Build a template `Scene` once and keep the node ids of the animated parts. In each frame,
//! `scene.clone()` (the clones share the geometry), set the transforms with the `set_*`
//! methods and render the clone with a `Renderer`. The render runs without the GIL.

// Python methods take `&self`, also the `to_*` conversions of `Copy` values.
#![allow(clippy::wrong_self_convention)]

use std::sync::Arc;

use fframes::media::{ImageData, ImageMetadata};
use fframes::three_d as td;
use fframes::three_d::{Mat3, Mat4, Quat, Vec2, Vec3, Vec4};
use pyo3::exceptions::{PyIndexError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyFloat, PyInt, PyString, PyTuple};

use crate::values::PyImage;

fn type_error(what: &str, value: &Bound<'_, PyAny>) -> PyErr {
    let name = value
        .get_type()
        .name()
        .map_or_else(|_| "?".to_owned(), |n| n.to_string());
    PyTypeError::new_err(format!("expected {what}, not {name}"))
}

/// A `Vec3` or a sequence of 3 numbers.
pub fn vec3(value: &Bound<'_, PyAny>) -> PyResult<Vec3> {
    if let Ok(v) = value.cast::<PyVec3>() {
        return Ok(v.get().0);
    }
    let parts: Vec<f32> = value
        .extract()
        .map_err(|_| type_error("a Vec3 or (x, y, z)", value))?;
    match parts.as_slice() {
        [x, y, z] => Ok(Vec3::new(*x, *y, *z)),
        _ => Err(PyValueError::new_err("a vector has 3 numbers")),
    }
}

/// A sequence of 2 numbers.
fn vec2(value: &Bound<'_, PyAny>) -> PyResult<Vec2> {
    let (x, y): (f32, f32) = value
        .extract()
        .map_err(|_| type_error("(x, y)", value))?;
    Ok(Vec2::new(x, y))
}

fn vec2s(value: &Bound<'_, PyAny>) -> PyResult<Vec<Vec2>> {
    value.try_iter()?.map(|p| vec2(&p?)).collect()
}

fn vec3s(value: &Bound<'_, PyAny>) -> PyResult<Vec<Vec3>> {
    value.try_iter()?.map(|p| vec3(&p?)).collect()
}

/// An `Rgb`, an sRGB hex number (`0xff8800`), a CSS `#rrggbb` string or linear `(r, g, b)`.
pub fn rgb(value: &Bound<'_, PyAny>) -> PyResult<td::Rgb> {
    if let Ok(c) = value.cast::<PyRgb>() {
        return Ok(c.get().0);
    }
    if value.is_instance_of::<PyInt>() {
        return Ok(td::Rgb::hex(value.extract()?));
    }
    if let Ok(text) = value.cast::<PyString>() {
        return Ok(td::Rgb::parse(&text.to_cow()?));
    }
    if value.is_instance_of::<PyTuple>() || value.is_instance_of::<pyo3::types::PyList>() {
        let (r, g, b): (f32, f32, f32) = value.extract()?;
        return Ok(td::Rgb::linear(r, g, b));
    }
    Err(type_error("an Rgb, a hex number or a color string", value))
}

fn f32_bytes(data: &[u8], what: &str) -> PyResult<Vec<f32>> {
    if !data.len().is_multiple_of(4) {
        return Err(PyValueError::new_err(format!("{what}: float32 bytes")));
    }
    Ok(data
        .as_chunks::<4>()
        .0
        .iter()
        .map(|b| f32::from_ne_bytes(*b))
        .collect())
}

fn image_data(image: &PyImage) -> ImageData<'static> {
    let data = Arc::clone(&image.data);
    let metadata = ImageMetadata {
        width: data.width,
        height: data.height,
    };
    ImageData::new_from_raw_data(data, String::new(), metadata)
}

/// Converts degrees to radians in f32, as the Rust examples do.
#[pyfunction]
pub fn deg(degrees: f32) -> f32 {
    td::deg(degrees)
}

/// A rotation from Euler angles in radians, in X, Y, Z order (three.js `"XYZ"`).
#[pyfunction]
pub fn euler(x: f32, y: f32, z: f32) -> PyQuat {
    PyQuat(td::euler(x, y, z))
}

/// Hermite interpolation from 0 to 1 while `x` goes from `edge0` to `edge1`, in f32.
#[pyfunction]
pub fn smoothstep(edge0: f32, edge1: f32, x: f32) -> f32 {
    td::math::smoothstep(edge0, edge1, x)
}

macro_rules! f32_fns {
    ($($(#[$doc:meta])* $name:ident($($arg:ident),+) => $body:expr;)+) => {
        $(
            $(#[$doc])*
            #[pyfunction]
            pub fn $name($($arg: f32),+) -> f32 {
                $body
            }
        )+
    };
}

// f32 math with the exact results of the Rust examples (numpy's float32 sin and cos differ
// from the platform libm in the last bit).
f32_fns! {
    sin(x) => x.sin();
    cos(x) => x.cos();
    tan(x) => x.tan();
    asin(x) => x.asin();
    acos(x) => x.acos();
    atan(x) => x.atan();
    atan2(y, x) => y.atan2(x);
    exp(x) => x.exp();
    ln(x) => x.ln();
    sqrt(x) => x.sqrt();
    powf(x, y) => x.powf(y);
}

// ---------------------------------------------------------------- math

/// A 3D vector of f32, glam `Vec3`. Arguments also take `(x, y, z)` tuples.
#[pyclass(name = "Vec3", module = "fframes.three_d", frozen, from_py_object)]
#[derive(Clone, Copy)]
pub struct PyVec3(pub Vec3);

#[pymethods]
impl PyVec3 {
    #[new]
    #[pyo3(signature = (x = 0.0, y = 0.0, z = 0.0))]
    fn new(x: f32, y: f32, z: f32) -> Self {
        Self(Vec3::new(x, y, z))
    }
    #[getter]
    fn x(&self) -> f32 {
        self.0.x
    }
    #[getter]
    fn y(&self) -> f32 {
        self.0.y
    }
    #[getter]
    fn z(&self) -> f32 {
        self.0.z
    }
    fn with_x(&self, x: f32) -> Self {
        Self(Vec3::new(x, self.0.y, self.0.z))
    }
    fn with_y(&self, y: f32) -> Self {
        Self(Vec3::new(self.0.x, y, self.0.z))
    }
    fn with_z(&self, z: f32) -> Self {
        Self(Vec3::new(self.0.x, self.0.y, z))
    }
    fn __add__(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(self.0 + vec3(other)?))
    }
    fn __radd__(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(vec3(other)? + self.0))
    }
    fn __sub__(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(self.0 - vec3(other)?))
    }
    fn __rsub__(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(vec3(other)? - self.0))
    }
    /// `v * number` or `v * other` (per component).
    fn __mul__(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        if other.is_instance_of::<PyFloat>() || other.is_instance_of::<PyInt>() {
            return Ok(Self(self.0 * other.extract::<f32>()?));
        }
        Ok(Self(self.0 * vec3(other)?))
    }
    fn __rmul__(&self, other: f32) -> Self {
        Self(other * self.0)
    }
    fn __truediv__(&self, other: f32) -> Self {
        Self(self.0 / other)
    }
    fn __neg__(&self) -> Self {
        Self(-self.0)
    }
    fn __eq__(&self, other: &Bound<'_, PyAny>) -> bool {
        vec3(other).is_ok_and(|o| o == self.0)
    }
    fn __hash__(&self) -> u64 {
        let [x, y, z] = self.0.to_array().map(f32::to_bits);
        (u64::from(x) << 42) ^ (u64::from(y) << 21) ^ u64::from(z)
    }
    fn __len__(&self) -> usize {
        3
    }
    fn __getitem__(&self, i: isize) -> PyResult<f32> {
        let i = if i < 0 { i + 3 } else { i };
        match i {
            0 => Ok(self.0.x),
            1 => Ok(self.0.y),
            2 => Ok(self.0.z),
            _ => Err(PyIndexError::new_err("Vec3 index out of range")),
        }
    }
    fn __repr__(&self) -> String {
        format!("Vec3({}, {}, {})", self.0.x, self.0.y, self.0.z)
    }
    fn dot(&self, other: &Bound<'_, PyAny>) -> PyResult<f32> {
        Ok(self.0.dot(vec3(other)?))
    }
    fn cross(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(self.0.cross(vec3(other)?)))
    }
    fn length(&self) -> f32 {
        self.0.length()
    }
    fn length_squared(&self) -> f32 {
        self.0.length_squared()
    }
    fn distance(&self, other: &Bound<'_, PyAny>) -> PyResult<f32> {
        Ok(self.0.distance(vec3(other)?))
    }
    fn normalize(&self) -> Self {
        Self(self.0.normalize())
    }
    fn normalize_or(&self, fallback: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(self.0.normalize_or(vec3(fallback)?)))
    }
    fn normalize_or_zero(&self) -> Self {
        Self(self.0.normalize_or_zero())
    }
    fn lerp(&self, other: &Bound<'_, PyAny>, t: f32) -> PyResult<Self> {
        Ok(Self(self.0.lerp(vec3(other)?, t)))
    }
    fn abs(&self) -> Self {
        Self(self.0.abs())
    }
    fn min(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(self.0.min(vec3(other)?)))
    }
    fn max(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(self.0.max(vec3(other)?)))
    }
    fn angle_between(&self, other: &Bound<'_, PyAny>) -> PyResult<f32> {
        Ok(self.0.angle_between(vec3(other)?))
    }
    fn to_tuple(&self) -> (f32, f32, f32) {
        self.0.into()
    }
    #[classattr]
    const ZERO: PyVec3 = PyVec3(Vec3::ZERO);
    #[classattr]
    const ONE: PyVec3 = PyVec3(Vec3::ONE);
    #[classattr]
    const X: PyVec3 = PyVec3(Vec3::X);
    #[classattr]
    const Y: PyVec3 = PyVec3(Vec3::Y);
    #[classattr]
    const Z: PyVec3 = PyVec3(Vec3::Z);
    #[classattr]
    const NEG_X: PyVec3 = PyVec3(Vec3::NEG_X);
    #[classattr]
    const NEG_Y: PyVec3 = PyVec3(Vec3::NEG_Y);
    #[classattr]
    const NEG_Z: PyVec3 = PyVec3(Vec3::NEG_Z);
}

/// A rotation of f32, glam `Quat`. `q * other_q` composes, `q * vec` rotates.
#[pyclass(name = "Quat", module = "fframes.three_d", frozen, from_py_object)]
#[derive(Clone, Copy)]
pub struct PyQuat(pub Quat);

#[pymethods]
impl PyQuat {
    #[new]
    #[pyo3(signature = (x = 0.0, y = 0.0, z = 0.0, w = 1.0))]
    fn new(x: f32, y: f32, z: f32, w: f32) -> Self {
        Self(Quat::from_xyzw(x, y, z, w))
    }
    #[classattr]
    const IDENTITY: PyQuat = PyQuat(Quat::IDENTITY);
    #[staticmethod]
    fn from_axis_angle(axis: &Bound<'_, PyAny>, angle: f32) -> PyResult<Self> {
        Ok(Self(Quat::from_axis_angle(vec3(axis)?, angle)))
    }
    #[staticmethod]
    fn from_scaled_axis(v: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(Quat::from_scaled_axis(vec3(v)?)))
    }
    #[staticmethod]
    fn from_rotation_x(angle: f32) -> Self {
        Self(Quat::from_rotation_x(angle))
    }
    #[staticmethod]
    fn from_rotation_y(angle: f32) -> Self {
        Self(Quat::from_rotation_y(angle))
    }
    #[staticmethod]
    fn from_rotation_z(angle: f32) -> Self {
        Self(Quat::from_rotation_z(angle))
    }
    #[staticmethod]
    fn from_rotation_arc(start: &Bound<'_, PyAny>, end: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(Quat::from_rotation_arc(vec3(start)?, vec3(end)?)))
    }
    /// The rotation of a matrix with the columns `x`, `y`, `z`.
    #[staticmethod]
    fn from_cols(
        x: &Bound<'_, PyAny>,
        y: &Bound<'_, PyAny>,
        z: &Bound<'_, PyAny>,
    ) -> PyResult<Self> {
        Ok(Self(Quat::from_mat3(&Mat3::from_cols(
            vec3(x)?,
            vec3(y)?,
            vec3(z)?,
        ))))
    }
    #[staticmethod]
    fn euler(x: f32, y: f32, z: f32) -> Self {
        Self(td::euler(x, y, z))
    }
    fn __mul__(&self, other: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        let py = other.py();
        if let Ok(q) = other.cast::<PyQuat>() {
            return Ok(Py::new(py, Self(self.0 * q.get().0))?.into_any());
        }
        Ok(Py::new(py, PyVec3(self.0 * vec3(other)?))?.into_any())
    }
    fn inverse(&self) -> Self {
        Self(self.0.inverse())
    }
    fn normalize(&self) -> Self {
        Self(self.0.normalize())
    }
    fn slerp(&self, other: &PyQuat, t: f32) -> Self {
        Self(self.0.slerp(other.0, t))
    }
    fn angle_between(&self, other: &PyQuat) -> f32 {
        self.0.angle_between(other.0)
    }
    fn to_axis_angle(&self) -> (PyVec3, f32) {
        let (axis, angle) = self.0.to_axis_angle();
        (PyVec3(axis), angle)
    }
    fn to_tuple(&self) -> (f32, f32, f32, f32) {
        self.0.into()
    }
    fn __repr__(&self) -> String {
        format!("Quat({}, {}, {}, {})", self.0.x, self.0.y, self.0.z, self.0.w)
    }
}

/// A 4x4 transform of f32, glam `Mat4`. `m * other_m` composes.
#[pyclass(name = "Mat4", module = "fframes.three_d", frozen, from_py_object)]
#[derive(Clone, Copy)]
pub struct PyMat4(pub Mat4);

#[pymethods]
impl PyMat4 {
    #[classattr]
    const IDENTITY: PyMat4 = PyMat4(Mat4::IDENTITY);
    #[staticmethod]
    fn from_translation(v: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(Mat4::from_translation(vec3(v)?)))
    }
    #[staticmethod]
    fn from_quat(q: &PyQuat) -> Self {
        Self(Mat4::from_quat(q.0))
    }
    #[staticmethod]
    fn from_rotation_x(angle: f32) -> Self {
        Self(Mat4::from_rotation_x(angle))
    }
    #[staticmethod]
    fn from_rotation_y(angle: f32) -> Self {
        Self(Mat4::from_rotation_y(angle))
    }
    #[staticmethod]
    fn from_rotation_z(angle: f32) -> Self {
        Self(Mat4::from_rotation_z(angle))
    }
    #[staticmethod]
    fn from_scale(v: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(Mat4::from_scale(vec3(v)?)))
    }
    #[staticmethod]
    fn from_rotation_translation(q: &PyQuat, v: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(Mat4::from_rotation_translation(q.0, vec3(v)?)))
    }
    #[staticmethod]
    fn from_scale_rotation_translation(
        s: &Bound<'_, PyAny>,
        q: &PyQuat,
        v: &Bound<'_, PyAny>,
    ) -> PyResult<Self> {
        Ok(Self(Mat4::from_scale_rotation_translation(
            vec3(s)?,
            q.0,
            vec3(v)?,
        )))
    }
    /// The matrix with the columns `x`, `y`, `z` (3D) and `w` (translation).
    #[staticmethod]
    fn from_cols(
        x: &Bound<'_, PyAny>,
        y: &Bound<'_, PyAny>,
        z: &Bound<'_, PyAny>,
        w: &Bound<'_, PyAny>,
    ) -> PyResult<Self> {
        Ok(Self(Mat4::from_cols(
            vec3(x)?.extend(0.0),
            vec3(y)?.extend(0.0),
            vec3(z)?.extend(0.0),
            vec3(w)?.extend(1.0),
        )))
    }
    fn __mul__(&self, other: &PyMat4) -> Self {
        Self(self.0 * other.0)
    }
    fn inverse(&self) -> Self {
        Self(self.0.inverse())
    }
    fn transform_point3(&self, p: &Bound<'_, PyAny>) -> PyResult<PyVec3> {
        Ok(PyVec3(self.0.transform_point3(vec3(p)?)))
    }
    fn transform_vector3(&self, v: &Bound<'_, PyAny>) -> PyResult<PyVec3> {
        Ok(PyVec3(self.0.transform_vector3(vec3(v)?)))
    }
    fn to_scale_rotation_translation(&self) -> (PyVec3, PyQuat, PyVec3) {
        let (s, r, t) = self.0.to_scale_rotation_translation();
        (PyVec3(s), PyQuat(r), PyVec3(t))
    }
    /// Column `i` (0 to 3) without its fourth row.
    fn col(&self, i: usize) -> PyResult<PyVec3> {
        if i > 3 {
            return Err(PyIndexError::new_err("Mat4 column 0..4"));
        }
        Ok(PyVec3(self.0.col(i).truncate()))
    }
    #[getter]
    fn x_axis(&self) -> PyVec3 {
        PyVec3(self.0.x_axis.truncate())
    }
    #[getter]
    fn y_axis(&self) -> PyVec3 {
        PyVec3(self.0.y_axis.truncate())
    }
    #[getter]
    fn z_axis(&self) -> PyVec3 {
        PyVec3(self.0.z_axis.truncate())
    }
    #[getter]
    fn w_axis(&self) -> PyVec3 {
        PyVec3(self.0.w_axis.truncate())
    }
    fn to_cols_array(&self) -> Vec<f32> {
        self.0.to_cols_array().to_vec()
    }
    fn __repr__(&self) -> String {
        format!("Mat4({:?})", self.0.to_cols_array())
    }
}

/// A linear RGB color for 3D. Constructors take sRGB, as three.js does.
#[pyclass(name = "Rgb", module = "fframes.three_d", frozen, from_py_object)]
#[derive(Clone, Copy)]
pub struct PyRgb(pub td::Rgb);

#[pymethods]
impl PyRgb {
    /// Linear components, without conversion.
    #[new]
    fn new(r: f32, g: f32, b: f32) -> Self {
        Self(td::Rgb::linear(r, g, b))
    }
    #[staticmethod]
    fn hex(hex: u32) -> Self {
        Self(td::Rgb::hex(hex))
    }
    #[staticmethod]
    fn srgb8(r: u8, g: u8, b: u8) -> Self {
        Self(td::Rgb::srgb8(r, g, b))
    }
    #[staticmethod]
    fn srgb(r: f32, g: f32, b: f32) -> Self {
        Self(td::Rgb::srgb(r, g, b))
    }
    #[staticmethod]
    fn hsl(hue: f32, saturation: f32, lightness: f32) -> Self {
        Self(td::Rgb::hsl(hue, saturation, lightness))
    }
    #[staticmethod]
    fn parse(css: &str) -> Self {
        Self(td::Rgb::parse(css))
    }
    #[classattr]
    const WHITE: PyRgb = PyRgb(td::Rgb::WHITE);
    #[classattr]
    const BLACK: PyRgb = PyRgb(td::Rgb::BLACK);
    #[getter]
    fn r(&self) -> f32 {
        self.0.r()
    }
    #[getter]
    fn g(&self) -> f32 {
        self.0.g()
    }
    #[getter]
    fn b(&self) -> f32 {
        self.0.b()
    }
    fn lerp(&self, other: &Bound<'_, PyAny>, t: f32) -> PyResult<Self> {
        Ok(Self(self.0.lerp(rgb(other)?, t)))
    }
    fn __mul__(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        if other.is_instance_of::<PyFloat>() || other.is_instance_of::<PyInt>() {
            return Ok(Self(self.0 * other.extract::<f32>()?));
        }
        Ok(Self(self.0 * rgb(other)?))
    }
    fn __add__(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(self.0 + rgb(other)?))
    }
    /// The 8-bit sRGB components, clamped.
    fn to_srgb8(&self) -> (u8, u8, u8) {
        let [r, g, b] = self.0.to_srgb8();
        (r, g, b)
    }
    fn __repr__(&self) -> String {
        format!("Rgb({}, {}, {})", self.0.r(), self.0.g(), self.0.b())
    }
}

// ---------------------------------------------------------------- building blocks

/// A shape: vertices and triangles. All clones share it.
#[pyclass(name = "Geometry", module = "fframes.three_d", frozen)]
pub struct PyGeometry(pub Arc<td::Geometry>);

impl PyGeometry {
    fn of(geometry: td::Geometry) -> Self {
        Self(Arc::new(geometry))
    }

    fn map(&self, f: impl FnOnce(td::Geometry) -> td::Geometry) -> Self {
        Self::of(f((*self.0).clone()))
    }
}

#[pymethods]
impl PyGeometry {
    #[staticmethod]
    fn cuboid(width: f32, height: f32, depth: f32) -> Self {
        Self::of(td::Geometry::cuboid(width, height, depth))
    }
    #[staticmethod]
    fn rounded_box(width: f32, height: f32, depth: f32, radius: f32, segments: u32) -> Self {
        Self::of(td::Geometry::rounded_box(
            width, height, depth, radius, segments,
        ))
    }
    #[staticmethod]
    fn sphere(radius: f32, width_segments: u32, height_segments: u32) -> Self {
        Self::of(td::Geometry::sphere(radius, width_segments, height_segments))
    }
    #[staticmethod]
    fn sphere_partial(
        radius: f32,
        width_segments: u32,
        height_segments: u32,
        theta_start: f32,
        theta_length: f32,
    ) -> Self {
        Self::of(td::Geometry::sphere_partial(
            radius,
            width_segments,
            height_segments,
            theta_start,
            theta_length,
        ))
    }
    #[staticmethod]
    fn cylinder(radius_top: f32, radius_bottom: f32, height: f32, radial_segments: u32) -> Self {
        Self::of(td::Geometry::cylinder(
            radius_top,
            radius_bottom,
            height,
            radial_segments,
        ))
    }
    #[staticmethod]
    fn cylinder_open(
        radius_top: f32,
        radius_bottom: f32,
        height: f32,
        radial_segments: u32,
    ) -> Self {
        Self::of(td::Geometry::cylinder_open(
            radius_top,
            radius_bottom,
            height,
            radial_segments,
        ))
    }
    #[staticmethod]
    fn cone(radius: f32, height: f32, radial_segments: u32) -> Self {
        Self::of(td::Geometry::cone(radius, height, radial_segments))
    }
    #[staticmethod]
    fn capsule(radius: f32, length: f32, cap_segments: u32, radial_segments: u32) -> Self {
        Self::of(td::Geometry::capsule(
            radius,
            length,
            cap_segments,
            radial_segments,
        ))
    }
    #[staticmethod]
    fn torus(radius: f32, tube: f32, radial_segments: u32, tubular_segments: u32) -> Self {
        Self::of(td::Geometry::torus(
            radius,
            tube,
            radial_segments,
            tubular_segments,
        ))
    }
    #[staticmethod]
    fn torus_arc(
        radius: f32,
        tube: f32,
        radial_segments: u32,
        tubular_segments: u32,
        arc: f32,
    ) -> Self {
        Self::of(td::Geometry::torus_arc(
            radius,
            tube,
            radial_segments,
            tubular_segments,
            arc,
        ))
    }
    #[staticmethod]
    fn plane(width: f32, height: f32) -> Self {
        Self::of(td::Geometry::plane(width, height))
    }
    #[staticmethod]
    fn floor(width: f32, depth: f32) -> Self {
        Self::of(td::Geometry::floor(width, depth))
    }
    #[staticmethod]
    fn floor_segments(width: f32, depth: f32, width_segments: u32, depth_segments: u32) -> Self {
        Self::of(td::Geometry::floor_segments(
            width,
            depth,
            width_segments,
            depth_segments,
        ))
    }
    #[staticmethod]
    fn circle(radius: f32, segments: u32) -> Self {
        Self::of(td::Geometry::circle(radius, segments))
    }
    #[staticmethod]
    fn ring(inner: f32, outer: f32, segments: u32) -> Self {
        Self::of(td::Geometry::ring(inner, outer, segments))
    }
    #[staticmethod]
    fn icosahedron(radius: f32, detail: u32) -> Self {
        Self::of(td::Geometry::icosahedron(radius, detail))
    }
    /// A surface of revolution of `points` (x, y) around Y.
    #[staticmethod]
    fn lathe(points: &Bound<'_, PyAny>, segments: u32) -> PyResult<Self> {
        Ok(Self::of(td::Geometry::lathe(&vec2s(points)?, segments)))
    }
    /// The outline `shape` of (x, y) points, extruded `depth` along Z.
    #[staticmethod]
    #[pyo3(signature = (shape, depth, bevel, bevel_segments = None, holes = None))]
    fn extrude(
        shape: &Bound<'_, PyAny>,
        depth: f32,
        bevel: f32,
        bevel_segments: Option<u32>,
        holes: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Self> {
        let outer = vec2s(shape)?;
        Ok(Self::of(match (holes, bevel_segments) {
            (Some(holes), segments) => {
                let holes = holes
                    .try_iter()?
                    .map(|h| vec2s(&h?))
                    .collect::<PyResult<Vec<_>>>()?;
                let shape = td::Shape { outer, holes };
                td::Geometry::extrude_shape(&shape, depth, bevel, segments.unwrap_or(3))
            }
            (None, Some(segments)) => {
                td::Geometry::extrude_segments(&outer, depth, bevel, segments)
            }
            (None, None) => td::Geometry::extrude(&outer, depth, bevel),
        }))
    }
    /// A tube of `radius` along the points of `path`.
    #[staticmethod]
    fn tube(path: &Bound<'_, PyAny>, radius: f32, radial_segments: u32) -> PyResult<Self> {
        Ok(Self::of(td::Geometry::tube(
            &vec3s(path)?,
            radius,
            radial_segments,
        )))
    }
    /// The points of a regular polygon with `sides` corners.
    #[staticmethod]
    fn polygon(radius: f32, sides: u32) -> Vec<(f32, f32)> {
        td::Geometry::polygon(radius, sides)
            .into_iter()
            .map(Into::into)
            .collect()
    }
    /// `text` in the font `font` (TTF or OTF bytes), extruded `depth` along Z.
    #[staticmethod]
    fn text(font: &[u8], text: &str, size: f32, depth: f32, bevel: f32) -> PyResult<Self> {
        td::Geometry::text(font, text, size, depth, bevel)
            .map(Self::of)
            .map_err(|e| PyValueError::new_err(e.to_string()))
    }
    /// One `Glyph` per letter of `text`: char, origin (x, y), advance and geometry.
    #[staticmethod]
    fn text_glyphs(
        font: &[u8],
        text: &str,
        size: f32,
        depth: f32,
        bevel: f32,
    ) -> PyResult<Vec<PyGlyph>> {
        let glyphs = td::Geometry::text_glyphs(font, text, size, depth, bevel)
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
        Ok(glyphs
            .into_iter()
            .map(|g| PyGlyph {
                ch: g.ch.to_string(),
                origin: g.origin.into(),
                advance: g.advance,
                geometry: Arc::new(g.geometry),
            })
            .collect())
    }
    /// The outlines of each letter: a list of (char, origin, advance, shapes), where each
    /// shape is (outer points, [hole points]).
    #[staticmethod]
    #[allow(clippy::type_complexity)]
    fn text_shapes(
        font: &[u8],
        text: &str,
        size: f32,
        letter_spacing: f32,
    ) -> PyResult<Vec<(String, (f32, f32), f32, Vec<(Vec<(f32, f32)>, Vec<Vec<(f32, f32)>>)>)>>
    {
        let glyphs = td::Geometry::text_shapes(font, text, size, letter_spacing)
            .map_err(|e| PyValueError::new_err(e.to_string()))?;
        let points = |p: &[Vec2]| p.iter().map(|&v| v.into()).collect::<Vec<(f32, f32)>>();
        Ok(glyphs
            .into_iter()
            .map(|g| {
                let shapes = g
                    .shapes
                    .iter()
                    .map(|s| (points(&s.outer), s.holes.iter().map(|h| points(h)).collect()))
                    .collect();
                (g.ch.to_string(), g.origin.into(), g.advance, shapes)
            })
            .collect())
    }
    /// All `parts` in one geometry.
    #[staticmethod]
    fn merge(parts: Vec<PyRef<'_, PyGeometry>>) -> Self {
        Self::of(td::Geometry::merge(parts.iter().map(|g| (*g.0).clone())))
    }
    fn transform(&self, m: &PyMat4) -> Self {
        self.map(|g| g.transform(m.0))
    }
    fn translate(&self, x: f32, y: f32, z: f32) -> Self {
        self.map(|g| g.translate(x, y, z))
    }
    fn rotate(&self, rotation: &PyQuat) -> Self {
        self.map(|g| g.rotate(rotation.0))
    }
    fn rotate_x(&self, angle: f32) -> Self {
        self.map(|g| g.rotate_x(angle))
    }
    fn rotate_y(&self, angle: f32) -> Self {
        self.map(|g| g.rotate_y(angle))
    }
    fn rotate_z(&self, angle: f32) -> Self {
        self.map(|g| g.rotate_z(angle))
    }
    fn scale(&self, x: f32, y: f32, z: f32) -> Self {
        self.map(|g| g.scale(x, y, z))
    }
    fn smooth(&self, crease_degrees: f32) -> Self {
        self.map(|g| g.smooth(crease_degrees))
    }
    fn flat(&self) -> Self {
        self.map(td::Geometry::flat)
    }
    fn with_color(&self, color: &Bound<'_, PyAny>) -> PyResult<Self> {
        let color = rgb(color)?;
        Ok(self.map(|g| g.with_color(color)))
    }
    /// The geometry with one linear RGBA color per vertex: float32 bytes, 4 per vertex.
    fn with_vertex_colors(&self, rgba: &[u8]) -> PyResult<Self> {
        let values = f32_bytes(rgba, "with_vertex_colors")?;
        if values.len() != self.0.positions.len() * 4 {
            return Err(PyValueError::new_err("with_vertex_colors: 4 floats per vertex"));
        }
        let colors = values
            .as_chunks::<4>()
            .0
            .iter()
            .map(|c| Vec4::from_array(*c))
            .collect();
        Ok(self.map(|mut g| {
            g.colors = colors;
            g
        }))
    }
    /// The vertex positions as float32 bytes, 3 per vertex.
    fn positions(&self, py: Python<'_>) -> Py<PyBytes> {
        let mut out = Vec::with_capacity(self.0.positions.len() * 12);
        for p in &self.0.positions {
            for c in p.to_array() {
                out.extend_from_slice(&c.to_ne_bytes());
            }
        }
        PyBytes::new(py, &out).unbind()
    }
    /// The bounds as (min, max).
    fn bounds(&self) -> (PyVec3, PyVec3) {
        let b = self.0.bounds();
        (PyVec3(b.min), PyVec3(b.max))
    }
    fn vertex_count(&self) -> usize {
        self.0.vertex_count()
    }
    fn triangle_count(&self) -> usize {
        self.0.triangle_count()
    }
}

/// One extruded letter of `Geometry.text_glyphs`.
#[pyclass(name = "Glyph", module = "fframes.three_d", frozen)]
pub struct PyGlyph {
    #[pyo3(get)]
    pub ch: String,
    #[pyo3(get)]
    pub origin: (f32, f32),
    #[pyo3(get)]
    pub advance: f32,
    geometry: Arc<td::Geometry>,
}

#[pymethods]
impl PyGlyph {
    #[getter]
    fn geometry(&self) -> PyGeometry {
        PyGeometry(Arc::clone(&self.geometry))
    }
}

/// An image on a surface, with mipmaps.
#[pyclass(name = "Texture", module = "fframes.three_d", frozen)]
pub struct PyTexture(pub Arc<td::Texture>);

#[pymethods]
impl PyTexture {
    /// An fframes `Image`, for example `ctx.render_svgr(...)` or a 3D render.
    #[staticmethod]
    fn from_image(image: &PyImage) -> Self {
        Self(Arc::new(td::Texture::from_image(&image_data(image))))
    }
    /// Rows of straight RGBA8 (`bytes`). `srgb` is true for colors, false for data maps.
    #[staticmethod]
    #[pyo3(signature = (width, height, rgba, srgb = true))]
    fn from_rgba8(width: u32, height: u32, rgba: &[u8], srgb: bool) -> Self {
        Self(Arc::new(td::Texture::from_rgba8(width, height, rgba, srgb)))
    }
    /// Decodes PNG, JPEG or WebP bytes. `srgb` false decodes a data map.
    #[staticmethod]
    #[pyo3(signature = (data, srgb = true))]
    fn decode(data: &[u8], srgb: bool) -> PyResult<Self> {
        let texture = if srgb {
            td::Texture::decode(data)
        } else {
            td::Texture::decode_linear(data)
        };
        texture
            .map(|t| Self(Arc::new(t)))
            .map_err(|e| PyValueError::new_err(e.to_string()))
    }
    fn repeat(&self, u: f32, v: f32) -> Self {
        Self(Arc::new((*self.0).clone().repeat(u, v)))
    }
    #[getter]
    fn width(&self) -> u32 {
        self.0.width
    }
    #[getter]
    fn height(&self) -> u32 {
        self.0.height
    }
}

/// How a surface looks: color, metal, roughness, glow, maps.
#[pyclass(name = "Material", module = "fframes.three_d", frozen)]
#[derive(Clone)]
pub struct PyMaterial(pub td::Material);

impl PyMaterial {
    fn with(&self, f: impl FnOnce(td::Material) -> td::Material) -> Self {
        Self(f(self.0.clone()))
    }
}

#[pymethods]
impl PyMaterial {
    #[staticmethod]
    fn standard(color: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(td::Material::standard(rgb(color)?)))
    }
    #[staticmethod]
    fn metal(color: &Bound<'_, PyAny>, roughness: f32) -> PyResult<Self> {
        Ok(Self(td::Material::metal(rgb(color)?, roughness)))
    }
    #[staticmethod]
    fn unlit(color: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(td::Material::unlit(rgb(color)?)))
    }
    #[staticmethod]
    fn glow(color: &Bound<'_, PyAny>, intensity: f32) -> PyResult<Self> {
        Ok(Self(td::Material::glow(rgb(color)?, intensity)))
    }
    #[staticmethod]
    fn shadow_catcher(opacity: f32) -> Self {
        Self(td::Material::shadow_catcher(opacity))
    }
    #[staticmethod]
    fn normals() -> Self {
        Self(td::Material::normals())
    }
    fn color(&self, color: &Bound<'_, PyAny>) -> PyResult<Self> {
        let color = rgb(color)?;
        Ok(self.with(|m| m.color(color)))
    }
    fn metalness(&self, value: f32) -> Self {
        self.with(|m| m.metalness(value))
    }
    fn roughness(&self, value: f32) -> Self {
        self.with(|m| m.roughness(value))
    }
    fn emissive(&self, color: &Bound<'_, PyAny>, intensity: f32) -> PyResult<Self> {
        let color = rgb(color)?;
        Ok(self.with(|m| m.emissive(color, intensity)))
    }
    fn clearcoat(&self, amount: f32) -> Self {
        self.with(|m| m.clearcoat(amount))
    }
    fn env_intensity(&self, value: f32) -> Self {
        self.with(|m| m.env_intensity(value))
    }
    fn reflection(&self, amount: f32) -> Self {
        self.with(|m| m.reflection(amount))
    }
    fn opacity(&self, value: f32) -> Self {
        self.with(|m| m.opacity(value))
    }
    fn additive(&self) -> Self {
        self.with(td::Material::additive)
    }
    fn transparent(&self) -> Self {
        self.with(td::Material::transparent)
    }
    fn double_sided(&self) -> Self {
        self.with(td::Material::double_sided)
    }
    fn flat(&self) -> Self {
        self.with(td::Material::flat)
    }
    fn no_fog(&self) -> Self {
        self.with(td::Material::no_fog)
    }
    fn map(&self, texture: &PyTexture) -> Self {
        let texture = Arc::clone(&texture.0);
        self.with(|m| m.map(texture))
    }
    fn emissive_map(&self, texture: &PyTexture) -> Self {
        let texture = Arc::clone(&texture.0);
        self.with(|m| m.emissive_map(texture))
    }
    fn normal_map(&self, texture: &PyTexture) -> Self {
        let texture = Arc::clone(&texture.0);
        self.with(|m| m.normal_map(texture))
    }
    fn normal_scale(&self, scale: f32) -> Self {
        self.with(|m| m.normal_scale(scale))
    }
    fn ao_map(&self, texture: &PyTexture) -> Self {
        let texture = Arc::clone(&texture.0);
        self.with(|m| m.ao_map(texture))
    }
}

/// A light source.
#[pyclass(name = "Light", module = "fframes.three_d", frozen)]
#[derive(Clone)]
pub struct PyLight(pub td::Light);

#[pymethods]
impl PyLight {
    #[staticmethod]
    fn ambient(color: &Bound<'_, PyAny>, intensity: f32) -> PyResult<Self> {
        Ok(Self(td::Light::ambient(rgb(color)?, intensity)))
    }
    #[staticmethod]
    fn hemisphere(
        sky: &Bound<'_, PyAny>,
        ground: &Bound<'_, PyAny>,
        intensity: f32,
    ) -> PyResult<Self> {
        Ok(Self(td::Light::hemisphere(rgb(sky)?, rgb(ground)?, intensity)))
    }
    /// Parallel light from the direction `source`, without shadows.
    #[staticmethod]
    fn directional(
        color: &Bound<'_, PyAny>,
        intensity: f32,
        source: &Bound<'_, PyAny>,
    ) -> PyResult<Self> {
        Ok(Self(td::Light::directional(
            rgb(color)?,
            intensity,
            vec3(source)?,
        )))
    }
    /// A directional light with soft shadows.
    #[staticmethod]
    fn sun(color: &Bound<'_, PyAny>, intensity: f32, source: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(td::Light::sun(rgb(color)?, intensity, vec3(source)?)))
    }
    #[staticmethod]
    fn point(color: &Bound<'_, PyAny>, intensity: f32, distance: f32) -> PyResult<Self> {
        Ok(Self(td::Light::point(rgb(color)?, intensity, distance)))
    }
    #[staticmethod]
    fn spot(color: &Bound<'_, PyAny>, intensity: f32, angle: f32, penumbra: f32) -> PyResult<Self> {
        Ok(Self(td::Light::spot(rgb(color)?, intensity, angle, penumbra)))
    }
    /// The light with a shadow map (directional lights only).
    #[pyo3(signature = (*, map_size = 2048, softness = 1.5, strength = 1.0, bias = 1.5, bounds = None))]
    fn with_shadow(
        &self,
        map_size: u32,
        softness: f32,
        strength: f32,
        bias: f32,
        bounds: Option<(PyVec3, PyVec3)>,
    ) -> Self {
        let shadow = td::Shadow {
            map_size,
            softness,
            strength,
            bias,
            bounds: bounds.map(|(min, max)| td::Aabb::from_points([min.0, max.0])),
        };
        Self(self.0.clone().with_shadow(shadow))
    }
    fn pointing(&self, direction: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(self.0.clone().pointing(vec3(direction)?)))
    }
}

/// The light from around the scene for reflections.
#[pyclass(name = "Environment", module = "fframes.three_d", frozen)]
#[derive(Clone)]
pub struct PyEnvironment(pub td::Environment);

#[pymethods]
impl PyEnvironment {
    /// A neutral dark studio with four softboxes.
    #[staticmethod]
    fn studio() -> Self {
        Self(td::Environment::studio())
    }
    /// No environment light.
    #[staticmethod]
    fn none() -> Self {
        Self(td::Environment::None)
    }
    /// A custom studio. `softboxes` holds (direction, width_degrees, height_degrees, color).
    #[staticmethod]
    #[pyo3(signature = (sky, horizon, ground, softboxes, intensity = 1.0, rotation = 0.0))]
    fn custom_studio(
        sky: &Bound<'_, PyAny>,
        horizon: &Bound<'_, PyAny>,
        ground: &Bound<'_, PyAny>,
        softboxes: &Bound<'_, PyAny>,
        intensity: f32,
        rotation: f32,
    ) -> PyResult<Self> {
        let softboxes = softboxes
            .try_iter()?
            .map(|b| {
                let b = b?;
                let (direction, width, height, color): (
                    Bound<'_, PyAny>,
                    f32,
                    f32,
                    Bound<'_, PyAny>,
                ) = b.extract()?;
                Ok(td::SoftBox::new(vec3(&direction)?, width, height, rgb(&color)?))
            })
            .collect::<PyResult<Vec<_>>>()?;
        Ok(Self(td::Environment::Studio(td::Studio {
            sky: rgb(sky)?,
            horizon: rgb(horizon)?,
            ground: rgb(ground)?,
            softboxes,
            intensity,
            rotation,
        })))
    }
    fn intensity(&self, value: f32) -> Self {
        Self(self.0.clone().intensity(value))
    }
    fn rotated(&self, radians: f32) -> Self {
        Self(self.0.clone().rotated(radians))
    }
}

/// How particles and glows blend: `"normal"` or `"additive"`.
fn blending(name: &str) -> PyResult<td::Blending> {
    match name {
        "normal" => Ok(td::Blending::Normal),
        "additive" => Ok(td::Blending::Additive),
        _ => Err(PyValueError::new_err("blending is 'normal' or 'additive'")),
    }
}

/// Particles from float32 bytes: positions (3 per item), sizes, colors (3, linear) and
/// opacities.
fn particles(
    positions: &[u8],
    sizes: &[u8],
    colors: &[u8],
    opacities: &[u8],
) -> PyResult<Vec<td::Particle>> {
    let positions = f32_bytes(positions, "positions")?;
    let sizes = f32_bytes(sizes, "sizes")?;
    let colors = f32_bytes(colors, "colors")?;
    let opacities = f32_bytes(opacities, "opacities")?;
    let n = sizes.len();
    if positions.len() != n * 3 || colors.len() != n * 3 || opacities.len() != n {
        return Err(PyValueError::new_err(
            "particles: positions and colors need 3 floats, sizes and opacities 1 per item",
        ));
    }
    let positions = positions.as_chunks::<3>().0;
    let colors = colors.as_chunks::<3>().0;
    Ok((0..n)
        .map(|i| {
            td::Particle::new(
                Vec3::from_array(positions[i]),
                sizes[i],
                td::Rgb(Vec3::from_array(colors[i])),
            )
            .opacity(opacities[i])
        })
        .collect())
}

/// A scene node before it goes into a scene: a mesh, a group, a light or particles.
#[pyclass(name = "Node", module = "fframes.three_d", frozen)]
#[derive(Clone)]
pub struct PyNode(pub td::Node);

impl PyNode {
    fn with(&self, f: impl FnOnce(td::Node) -> td::Node) -> Self {
        Self(f(self.0.clone()))
    }
}

#[pymethods]
impl PyNode {
    #[staticmethod]
    fn mesh(geometry: &PyGeometry, material: &PyMaterial) -> Self {
        Self(td::Node::mesh(Arc::clone(&geometry.0), material.0.clone()))
    }
    /// Copies of a mesh at `transforms` (a list of `Mat4`), with optional linear colors.
    #[staticmethod]
    #[pyo3(signature = (geometry, material, transforms, colors = None))]
    fn instanced(
        geometry: &PyGeometry,
        material: &PyMaterial,
        transforms: Vec<PyMat4>,
        colors: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Self> {
        let mut instances = td::Instances::new(transforms.into_iter().map(|m| m.0));
        if let Some(colors) = colors {
            let colors = colors
                .try_iter()?
                .map(|c| rgb(&c?))
                .collect::<PyResult<Vec<_>>>()?;
            instances = instances.colors(colors);
        }
        Ok(Self(td::Node::instanced(
            Arc::clone(&geometry.0),
            material.0.clone(),
            instances,
        )))
    }
    #[staticmethod]
    fn group() -> Self {
        Self(td::Node::group())
    }
    #[staticmethod]
    fn light(light: &PyLight) -> Self {
        Self(td::Node::light(light.0.clone()))
    }
    /// Empty particles; fill them in each frame with `Scene.set_particles`.
    #[staticmethod]
    #[pyo3(signature = (blending = "normal"))]
    fn particles(blending: &str) -> PyResult<Self> {
        Ok(Self(td::Node::particles(Vec::new(), self::blending(blending)?)))
    }
    fn named(&self, name: &str) -> Self {
        self.with(|n| n.named(name))
    }
    fn at(&self, x: f32, y: f32, z: f32) -> Self {
        self.with(|n| n.at(x, y, z))
    }
    fn with_position(&self, position: &Bound<'_, PyAny>) -> PyResult<Self> {
        let position = vec3(position)?;
        Ok(self.with(|n| n.with_position(position)))
    }
    fn with_rotation(&self, rotation: &PyQuat) -> Self {
        self.with(|n| n.with_rotation(rotation.0))
    }
    fn euler(&self, x: f32, y: f32, z: f32) -> Self {
        self.with(|n| n.euler(x, y, z))
    }
    fn rotate_x(&self, angle: f32) -> Self {
        self.with(|n| n.rotate_x(angle))
    }
    fn rotate_y(&self, angle: f32) -> Self {
        self.with(|n| n.rotate_y(angle))
    }
    fn rotate_z(&self, angle: f32) -> Self {
        self.with(|n| n.rotate_z(angle))
    }
    fn scaled(&self, scale: f32) -> Self {
        self.with(|n| n.scaled(scale))
    }
    fn scaled3(&self, x: f32, y: f32, z: f32) -> Self {
        self.with(|n| n.scaled3(x, y, z))
    }
    fn hidden(&self) -> Self {
        self.with(td::Node::hidden)
    }
    fn shadows(&self, cast: bool, receive: bool) -> Self {
        self.with(|n| n.shadows(cast, receive))
    }
}

/// A scene graph. Node ids are ints, valid in all clones of the scene.
#[pyclass(name = "Scene", module = "fframes.three_d")]
#[derive(Clone)]
pub struct PyScene(pub td::Scene);

impl PyScene {
    fn node(&mut self, id: u32) -> PyResult<&mut td::Node> {
        self.0
            .get_mut(td::NodeId(id))
            .ok_or_else(|| PyIndexError::new_err(format!("no node {id} in the scene")))
    }

    fn get(&self, id: u32) -> PyResult<td::NodeId> {
        let node = td::NodeId(id);
        self.0
            .get(node)
            .map(|_| node)
            .ok_or_else(|| PyIndexError::new_err(format!("no node {id} in the scene")))
    }

    fn material(&mut self, id: u32) -> PyResult<&mut td::Material> {
        self.node(id)?
            .material_mut()
            .ok_or_else(|| PyTypeError::new_err(format!("node {id} is not a mesh")))
    }
}

#[pymethods]
impl PyScene {
    #[new]
    #[pyo3(signature = (environment = None))]
    fn new(environment: Option<&PyEnvironment>) -> Self {
        let mut scene = td::Scene::new();
        if let Some(environment) = environment {
            scene = scene.environment(environment.0.clone());
        }
        Self(scene)
    }
    /// Adds `node` at the top level and returns its id.
    fn add(&mut self, node: &PyNode) -> u32 {
        self.0.add(node.0.clone()).0
    }
    /// Adds `node` as a child of `parent` and returns its id.
    fn add_to(&mut self, parent: u32, node: &PyNode) -> PyResult<u32> {
        let parent = self.get(parent)?;
        Ok(self.0.add_to(parent, node.0.clone()).0)
    }
    /// A copy to pose for one frame. The copies share the geometry, so this is cheap.
    fn clone(&self) -> Self {
        Clone::clone(self)
    }
    fn __len__(&self) -> usize {
        self.0.len()
    }
    fn find(&self, name: &str) -> Option<u32> {
        self.0.find(name).map(|id| id.0)
    }
    fn set_environment(&mut self, environment: &PyEnvironment) {
        self.0.environment = environment.0.clone();
    }
    /// A solid color, `None` for transparent, or `blur` (0..1) to show the environment.
    #[pyo3(signature = (color = None, *, blur = None))]
    fn set_background(&mut self, color: Option<&Bound<'_, PyAny>>, blur: Option<f32>) -> PyResult<()> {
        self.0.background = match (color, blur) {
            (Some(color), _) => td::Background::Color(rgb(color)?),
            (None, Some(blur)) => td::Background::Environment { blur },
            (None, None) => td::Background::Transparent,
        };
        Ok(())
    }
    /// three.js `FogExp2`. `density` 0 removes the fog.
    fn set_fog_exp2(&mut self, color: &Bound<'_, PyAny>, density: f32) -> PyResult<()> {
        self.0.fog = (density > 0.0).then_some(td::Fog::Exp2 {
            color: rgb(color)?,
            density,
        });
        Ok(())
    }
    /// three.js `Fog`.
    fn set_fog_linear(&mut self, color: &Bound<'_, PyAny>, near: f32, far: f32) -> PyResult<()> {
        self.0.fog = Some(td::Fog::Linear {
            color: rgb(color)?,
            near,
            far,
        });
        Ok(())
    }
    /// A mirror floor at y = 0 for materials with `reflection`.
    #[pyo3(signature = (scale = 1.0))]
    fn set_reflector_floor(&mut self, scale: f32) {
        self.0.reflector = Some(td::Reflector::floor().scale(scale));
    }
    fn set_position(&mut self, id: u32, position: &Bound<'_, PyAny>) -> PyResult<()> {
        self.node(id)?.position = vec3(position)?;
        Ok(())
    }
    fn set_rotation(&mut self, id: u32, rotation: &PyQuat) -> PyResult<()> {
        self.node(id)?.rotation = rotation.0;
        Ok(())
    }
    /// Sets the position and the rotation of a node from a rigid transform `m`.
    fn set_transform(&mut self, id: u32, m: &PyMat4) -> PyResult<()> {
        let (_, rotation, position) = m.0.to_scale_rotation_translation();
        let node = self.node(id)?;
        node.position = position;
        node.rotation = rotation;
        Ok(())
    }
    fn set_scale(&mut self, id: u32, scale: &Bound<'_, PyAny>) -> PyResult<()> {
        self.node(id)?.scale = vec3(scale)?;
        Ok(())
    }
    fn set_visible(&mut self, id: u32, visible: bool) -> PyResult<()> {
        self.node(id)?.visible = visible;
        Ok(())
    }
    fn set_material(&mut self, id: u32, material: &PyMaterial) -> PyResult<()> {
        *self.material(id)? = material.0.clone();
        Ok(())
    }
    /// Sets the color map of a mesh, `None` removes it.
    fn set_map(&mut self, id: u32, texture: Option<&PyTexture>) -> PyResult<()> {
        self.material(id)?.map = texture.map(|t| Arc::clone(&t.0));
        Ok(())
    }
    /// The color map of a mesh from an `Image`, e.g. `ctx.render_svgr(...)` or a 3D render.
    fn set_map_image(&mut self, py: Python<'_>, id: u32, image: &PyImage) -> PyResult<()> {
        let data = AssertSend(image_data(image));
        // Converts the pixels without the GIL, so that the frame threads run in parallel.
        let texture = py.detach(move || {
            let data = data;
            AssertSend(td::Texture::from_image(&data.0))
        })
        .0;
        self.material(id)?.map = Some(Arc::new(texture));
        Ok(())
    }
    fn set_color(&mut self, id: u32, color: &Bound<'_, PyAny>) -> PyResult<()> {
        self.material(id)?.color = rgb(color)?;
        Ok(())
    }
    fn set_emissive_intensity(&mut self, id: u32, value: f32) -> PyResult<()> {
        self.material(id)?.emissive_intensity = value;
        Ok(())
    }
    fn set_opacity(&mut self, id: u32, value: f32) -> PyResult<()> {
        self.material(id)?.opacity = value;
        Ok(())
    }
    fn set_light_intensity(&mut self, id: u32, value: f32) -> PyResult<()> {
        let light = self
            .node(id)?
            .light_mut()
            .ok_or_else(|| PyTypeError::new_err(format!("node {id} is not a light")))?;
        *light.intensity_mut() = value;
        Ok(())
    }
    /// The items of a particles node, from float32 `bytes` (for example
    /// `numpy_array.tobytes()`): positions (3 per item), sizes, linear colors (3 per item)
    /// and opacities.
    fn set_particles(
        &mut self,
        id: u32,
        positions: &[u8],
        sizes: &[u8],
        colors: &[u8],
        opacities: &[u8],
    ) -> PyResult<()> {
        let items = particles(positions, sizes, colors, opacities)?;
        match &mut self.node(id)?.object {
            td::Object::Particles(p) => {
                p.items = items;
                Ok(())
            }
            _ => Err(PyTypeError::new_err(format!("node {id} is not particles"))),
        }
    }
    fn world_matrix(&self, id: u32) -> PyResult<PyMat4> {
        Ok(PyMat4(self.0.world_matrix(self.get(id)?)))
    }
    fn world_position(&self, id: u32) -> PyResult<PyVec3> {
        Ok(PyVec3(self.0.world_position(self.get(id)?)))
    }
    fn local_to_world(&self, id: u32, local: &Bound<'_, PyAny>) -> PyResult<PyVec3> {
        Ok(PyVec3(self.0.local_to_world(self.get(id)?, vec3(local)?)))
    }
    /// The world bounds of a node and its children as (min, max).
    fn bounds(&self, id: u32) -> PyResult<(PyVec3, PyVec3)> {
        let b = self.0.bounds(self.get(id)?);
        Ok((PyVec3(b.min), PyVec3(b.max)))
    }
}

/// A camera, three.js `PerspectiveCamera` / `OrthographicCamera`. Builder methods return a
/// new camera.
#[pyclass(name = "Camera", module = "fframes.three_d", frozen, from_py_object)]
#[derive(Clone, Copy)]
pub struct PyCamera(pub td::Camera);

#[pymethods]
impl PyCamera {
    #[staticmethod]
    fn perspective(fov_degrees: f32) -> Self {
        Self(td::Camera::perspective(fov_degrees))
    }
    #[staticmethod]
    fn orthographic(height: f32) -> Self {
        Self(td::Camera::orthographic(height))
    }
    fn at(&self, x: f32, y: f32, z: f32) -> Self {
        Self(self.0.at(x, y, z))
    }
    fn position(&self, position: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(self.0.position(vec3(position)?)))
    }
    fn look_at(&self, target: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(self.0.look_at(vec3(target)?)))
    }
    fn fov(&self, fov_degrees: f32) -> Self {
        Self(self.0.fov(fov_degrees))
    }
    fn focus(&self, distance: f32, blur: f32) -> Self {
        Self(self.0.focus(distance, blur))
    }
    fn focus_on(&self, point: &Bound<'_, PyAny>, blur: f32) -> PyResult<Self> {
        Ok(Self(self.0.focus_on(vec3(point)?, blur)))
    }
    fn roll(&self, radians: f32) -> Self {
        Self(self.0.roll(radians))
    }
    fn clip(&self, near: f32, far: f32) -> Self {
        Self(self.0.clip(near, far))
    }
    /// A camera `distance` from `target`; `azimuth` and `elevation` in degrees.
    fn orbit(
        &self,
        target: &Bound<'_, PyAny>,
        distance: f32,
        azimuth: f32,
        elevation: f32,
    ) -> PyResult<Self> {
        Ok(Self(self.0.orbit(vec3(target)?, distance, azimuth, elevation)))
    }
    #[getter]
    fn get_position(&self) -> PyVec3 {
        PyVec3(self.0.position)
    }
    #[getter]
    fn target(&self) -> PyVec3 {
        PyVec3(self.0.target)
    }
    fn forward(&self) -> PyVec3 {
        PyVec3(self.0.forward())
    }
    /// The pixel (x, y) and depth of `world` on a `width` x `height` image, or `None`
    /// behind the camera.
    fn project(&self, world: &Bound<'_, PyAny>, width: f32, height: f32) -> PyResult<Option<PyVec3>> {
        Ok(self.0.project(vec3(world)?, width, height).map(PyVec3))
    }
    /// The size in pixels of `world_size` meters at `world`, on an image `height` high.
    fn pixel_size(&self, world: &Bound<'_, PyAny>, world_size: f32, height: f32) -> PyResult<f32> {
        Ok(self.0.pixel_size(vec3(world)?, world_size, height))
    }
}

/// Moves values that are not `Send` (the GPU textures of a scene) to the thread that
/// renders while the caller waits.
struct AssertSend<T>(T);
// SAFETY: the value is only used by the closure of `Python::detach`, and the caller waits.
unsafe impl<T> Send for AssertSend<T> {}

/// Makes images of scenes: `Renderer(1920, 1080).tone_mapping("neutral")`.
#[pyclass(name = "Renderer", module = "fframes.three_d", frozen)]
#[derive(Clone)]
pub struct PyRenderer(pub td::Renderer);

#[pymethods]
impl PyRenderer {
    /// It renders on the GPU when one is found, else on the CPU.
    #[new]
    fn new(width: u32, height: u32) -> Self {
        Self(td::Renderer::new(width, height))
    }
    /// `"aces"` (default), `"neutral"` or `"linear"`.
    fn tone_mapping(&self, name: &str) -> PyResult<Self> {
        let mapping = match name {
            "aces" => td::ToneMapping::Aces,
            "neutral" => td::ToneMapping::Neutral,
            "linear" => td::ToneMapping::Linear,
            _ => return Err(PyValueError::new_err("tone mapping: 'aces', 'neutral' or 'linear'")),
        };
        Ok(Self(self.0.clone().tone_mapping(mapping)))
    }
    #[pyo3(signature = (strength = 0.8, radius = 0.6, threshold = 1.0))]
    fn bloom(&self, strength: f32, radius: f32, threshold: f32) -> Self {
        Self(self.0.clone().bloom(td::Bloom {
            strength,
            radius,
            threshold,
        }))
    }
    fn exposure(&self, exposure: f32) -> Self {
        Self(self.0.clone().exposure(exposure))
    }
    fn antialias(&self, antialias: bool) -> Self {
        Self(self.0.clone().antialias(antialias))
    }
    fn scaled(&self, scale: f32) -> Self {
        Self(self.0.clone().scaled(scale))
    }
    /// Renders on the CPU, also when a GPU is there.
    fn cpu(&self) -> Self {
        Self(self.0.clone().cpu())
    }
    fn gpu(&self) -> Self {
        Self(self.0.clone().gpu())
    }
    #[getter]
    fn uses_gpu(&self) -> bool {
        self.0.uses_gpu()
    }
    #[getter]
    fn width(&self) -> u32 {
        self.0.width
    }
    #[getter]
    fn height(&self) -> u32 {
        self.0.height
    }
    /// The image of `scene` seen by `camera`. Runs without the GIL. `read_back` returns
    /// pixels on the CPU also when the GPU rendered.
    #[pyo3(signature = (scene, camera, *, read_back = false))]
    fn render(
        &self,
        py: Python<'_>,
        scene: &PyScene,
        camera: &PyCamera,
        read_back: bool,
    ) -> PyImage {
        let job = AssertSend((&self.0, &scene.0, camera.0));
        let data = py.detach(move || {
            let job = job;
            let (renderer, scene, camera) = job.0;
            let image = if read_back {
                renderer.render_pixels(scene, &camera).into_image()
            } else {
                renderer.render(scene, &camera)
            };
            AssertSend(image.image)
        });
        PyImage { data: data.0 }
    }
    /// The mean of the `moments` (a list of (scene, camera)), as a shutter that is open
    /// for the frame. Build the moments at the times of `Renderer.shutter_offsets(n)`.
    #[pyo3(signature = (moments, *, read_back = false))]
    fn render_motion_blur(
        &self,
        py: Python<'_>,
        moments: Vec<(PyRef<'_, PyScene>, PyCamera)>,
        read_back: bool,
    ) -> PyImage {
        let samples = moments.len();
        let moments: Vec<(td::Scene, td::Camera)> =
            moments.iter().map(|(s, c)| (s.0.clone(), c.0)).collect();
        let job = AssertSend((&self.0, moments));
        let data = py.detach(move || {
            let job = job;
            let (renderer, moments) = job.0;
            let mut moments = moments.into_iter();
            let mut next = |_offset: f32| moments.next().expect("one moment per sample");
            let image = if read_back {
                renderer
                    .render_motion_blur_pixels(samples, &mut next)
                    .into_image()
            } else {
                renderer.render_motion_blur(samples, &mut next)
            };
            AssertSend(image.image)
        });
        PyImage { data: data.0 }
    }
    /// The shutter offsets of `samples` moments in -0.5..0.5 of a frame, in f32.
    #[staticmethod]
    fn shutter_offsets(samples: usize) -> Vec<f32> {
        let samples = samples.max(1);
        (0..samples)
            .map(|i| (i as f32 + 0.5) / samples as f32 - 0.5)
            .collect()
    }
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    let py = m.py();
    let sub = PyModule::new(py, "three_d")?;
    sub.add_class::<PyVec3>()?;
    sub.add_class::<PyQuat>()?;
    sub.add_class::<PyMat4>()?;
    sub.add_class::<PyRgb>()?;
    sub.add_class::<PyGeometry>()?;
    sub.add_class::<PyGlyph>()?;
    sub.add_class::<PyTexture>()?;
    sub.add_class::<PyMaterial>()?;
    sub.add_class::<PyLight>()?;
    sub.add_class::<PyEnvironment>()?;
    sub.add_class::<PyNode>()?;
    sub.add_class::<PyScene>()?;
    sub.add_class::<PyCamera>()?;
    sub.add_class::<PyRenderer>()?;
    sub.add_function(wrap_pyfunction!(deg, &sub)?)?;
    sub.add_function(wrap_pyfunction!(euler, &sub)?)?;
    sub.add_function(wrap_pyfunction!(smoothstep, &sub)?)?;
    for f in [
        wrap_pyfunction!(sin, &sub)?,
        wrap_pyfunction!(cos, &sub)?,
        wrap_pyfunction!(tan, &sub)?,
        wrap_pyfunction!(asin, &sub)?,
        wrap_pyfunction!(acos, &sub)?,
        wrap_pyfunction!(atan, &sub)?,
        wrap_pyfunction!(atan2, &sub)?,
        wrap_pyfunction!(exp, &sub)?,
        wrap_pyfunction!(ln, &sub)?,
        wrap_pyfunction!(sqrt, &sub)?,
        wrap_pyfunction!(powf, &sub)?,
    ] {
        sub.add_function(f)?;
    }
    m.add_submodule(&sub)?;
    Ok(())
}
