//! `Media`: folders of images, fonts, audio, video, subtitles and Lottie files, loaded once.

use fframes::{DynamicMediaProvider, MediaDirectory};
use pyo3::exceptions::{PyOSError, PyTypeError};
use pyo3::prelude::*;

/// The media of one or more folders. A name in an earlier folder wins.
/// Audio keeps stereo; `mono=True` mixes it down like Rust `include_media_dir!`.
/// Pass it as `media=` to `fframes.cli`.
#[pyclass(name = "Media", module = "fframes", frozen)]
pub struct PyMedia {
    // Declared before `_directories` so that it drops first: it borrows the directories.
    provider: DynamicMediaProvider<'static>,
    _directories: Vec<Box<MediaDirectory>>,
    paths: Vec<String>,
}

impl PyMedia {
    pub fn provider(&self) -> &DynamicMediaProvider<'_> {
        &self.provider
    }
}

fn load(
    path: &std::path::Path,
    mono: bool,
) -> PyResult<(Box<MediaDirectory>, DynamicMediaProvider<'static>)> {
    let error = |e: fframes::FFramesRendererError| {
        PyOSError::new_err(format!("media {}: {e}", path.display()))
    };
    let directory = Box::new(MediaDirectory::read_folder(path).map_err(error)?);
    let provider = directory.process_media_source().map_err(error)?;
    // SAFETY: `provider` borrows the boxed directory. The box does not move, and `PyMedia`
    // drops the provider before the directories.
    let mut provider: DynamicMediaProvider<'static> = unsafe { std::mem::transmute(provider) };
    if mono {
        // Mix audio down to mono like `include_media_dir!` does.
        for (name, audio) in provider.audio.iter_mut() {
            let file = path.join(name);
            let data = fframes::media::PreloadedAudioData::decode_raw_file(None, &file)
                .map_err(|e| PyOSError::new_err(format!("media {}: {e:?}", file.display())))?;
            *audio = fframes::AudioData::Preloaded(data);
        }
    }
    Ok((directory, provider))
}

#[pymethods]
impl PyMedia {
    #[new]
    #[pyo3(signature = (*folders, mono = false))]
    fn new(py: Python<'_>, folders: Vec<std::path::PathBuf>, mono: bool) -> PyResult<Self> {
        if folders.is_empty() {
            return Err(PyTypeError::new_err("Media needs at least one folder"));
        }
        py.detach(|| {
            let mut merged = DynamicMediaProvider::default();
            let mut directories = Vec::with_capacity(folders.len());
            // Later folders first, so that an earlier folder overwrites a name.
            for folder in folders.iter().rev() {
                let (directory, provider) = load(folder, mono)?;
                merged.audio.extend(provider.audio);
                merged.images.extend(provider.images);
                merged.subtitles.extend(provider.subtitles);
                merged.videos.extend(provider.videos);
                merged.lottie.extend(provider.lottie);
                let mut fonts = provider.fontdata;
                fonts.append(&mut merged.fontdata);
                merged.fontdata = fonts;
                directories.push(directory);
            }
            Ok(Self {
                provider: merged,
                _directories: directories,
                paths: folders.iter().map(|p| p.display().to_string()).collect(),
            })
        })
    }

    /// The names of the images.
    #[getter]
    fn images(&self) -> Vec<String> {
        sorted(self.provider.images.keys())
    }

    #[getter]
    fn audio(&self) -> Vec<String> {
        sorted(self.provider.audio.keys())
    }

    #[getter]
    fn videos(&self) -> Vec<String> {
        sorted(self.provider.videos.keys())
    }

    #[getter]
    fn subtitles(&self) -> Vec<String> {
        sorted(self.provider.subtitles.keys())
    }

    #[getter]
    fn lottie(&self) -> Vec<String> {
        sorted(self.provider.lottie.keys())
    }

    #[getter]
    fn fonts(&self) -> Vec<String> {
        self.provider
            .fontdata
            .iter()
            .map(|f| f.file_name.clone())
            .collect()
    }

    fn __repr__(&self) -> String {
        format!("Media({})", self.paths.join(", "))
    }
}

fn sorted<'a>(names: impl Iterator<Item = &'a String>) -> Vec<String> {
    let mut names: Vec<String> = names.cloned().collect();
    names.sort();
    names
}
