//! EXIF fields of media images (fframes feature `exif`).

use fframes::exif::Tag;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use crate::frame::PyContext;

fn tag(name: &str) -> PyResult<Tag> {
    Ok(match name {
        "DateTimeOriginal" => Tag::DateTimeOriginal,
        "DateTimeDigitized" => Tag::DateTimeDigitized,
        "DateTime" => Tag::DateTime,
        "Make" => Tag::Make,
        "Model" => Tag::Model,
        "LensModel" => Tag::LensModel,
        "Orientation" => Tag::Orientation,
        "Artist" => Tag::Artist,
        "Copyright" => Tag::Copyright,
        "ImageDescription" => Tag::ImageDescription,
        "Software" => Tag::Software,
        "ExposureTime" => Tag::ExposureTime,
        "FNumber" => Tag::FNumber,
        "PhotographicSensitivity" => Tag::PhotographicSensitivity,
        "FocalLength" => Tag::FocalLength,
        "PixelXDimension" => Tag::PixelXDimension,
        "PixelYDimension" => Tag::PixelYDimension,
        "GPSLatitude" => Tag::GPSLatitude,
        "GPSLongitude" => Tag::GPSLongitude,
        _ => {
            return Err(PyValueError::new_err(format!("unknown EXIF tag {name:?}")));
        }
    })
}

/// The display value of EXIF field `tag` (for example "DateTimeOriginal") of the media image
/// `image`, or `None`. The first call for an image parses its EXIF data; later calls are fast.
#[pyfunction]
pub fn exif(
    py: Python<'_>,
    ctx: &PyContext,
    image: &str,
    tag_name: &str,
) -> PyResult<Option<String>> {
    let tag = tag(tag_name)?;
    let Some(data) = ctx.get()?.get_image(image) else {
        return Ok(None);
    };
    let data = AssertSync(data);
    Ok(py.detach(move || {
        let data = data;
        data.0
            .get_exif_data(tag)
            .map(|field| field.display_value().to_string())
    }))
}

struct AssertSync<T>(T);
// SAFETY: the image data lives as long as the media provider of the render and is only read.
unsafe impl<T> Send for AssertSync<T> {}
