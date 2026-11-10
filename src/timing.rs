//! Durations, audio timestamps, audio tracks and scene overlaps.
//!
//! The fframes values borrow file names and hold `Rc`, so they are not `Send`. These specs
//! own their data and build the fframes value each time that fframes asks for it.

use fframes::{AudioMap, AudioTimestamp, AudioTrack, Ducking, FadeCurve, Overlap, TrackMix};
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyString, PyTuple};

/// An owned `fframes::Duration`.
#[derive(Clone, Debug)]
pub enum DurSpec {
    FromAudio(String),
    FromVideo(String),
    Seconds(f32),
    Frames(usize),
    Auto,
    Add(Box<DurSpec>, Box<DurSpec>),
    Sub(Box<DurSpec>, Box<DurSpec>),
}

impl DurSpec {
    pub fn build(&self) -> fframes::Duration<'_> {
        use fframes::Duration as D;
        match self {
            DurSpec::FromAudio(file) => D::FromAudio(file),
            DurSpec::FromVideo(file) => D::FromVideo(file),
            DurSpec::Seconds(seconds) => D::Seconds(*seconds),
            DurSpec::Frames(frames) => D::Frames(*frames),
            DurSpec::Auto => D::Auto,
            DurSpec::Add(a, b) => a.build() + b.build(),
            DurSpec::Sub(a, b) => a.build() - b.build(),
        }
    }
}

/// How long a video or a scene lasts. A plain number means seconds.
#[pyclass(name = "Duration", module = "fframes", frozen)]
#[derive(Clone)]
pub struct PyDuration(pub DurSpec);

#[pymethods]
impl PyDuration {
    #[classattr]
    #[allow(non_snake_case)]
    fn AUTO() -> Self {
        Self(DurSpec::Auto)
    }

    #[staticmethod]
    fn seconds(seconds: f32) -> Self {
        Self(DurSpec::Seconds(seconds))
    }

    #[staticmethod]
    fn frames(frames: usize) -> Self {
        Self(DurSpec::Frames(frames))
    }

    /// The length of an audio file of the media folder.
    #[staticmethod]
    fn from_audio(file: String) -> Self {
        Self(DurSpec::FromAudio(file))
    }

    /// The length of a video file of the media folder.
    #[staticmethod]
    fn from_video(file: String) -> Self {
        Self(DurSpec::FromVideo(file))
    }

    fn __add__(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(DurSpec::Add(
            Box::new(self.0.clone()),
            Box::new(duration_from_any(other)?),
        )))
    }

    fn __radd__(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(DurSpec::Add(
            Box::new(duration_from_any(other)?),
            Box::new(self.0.clone()),
        )))
    }

    fn __sub__(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(DurSpec::Sub(
            Box::new(self.0.clone()),
            Box::new(duration_from_any(other)?),
        )))
    }

    fn __rsub__(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(DurSpec::Sub(
            Box::new(duration_from_any(other)?),
            Box::new(self.0.clone()),
        )))
    }

    fn __repr__(&self) -> String {
        format!("Duration({:?})", self.0)
    }
}

/// A duration from a `Duration`, a number of seconds or `None` (automatic).
pub fn duration_from_any(value: &Bound<'_, PyAny>) -> PyResult<DurSpec> {
    if value.is_none() {
        return Ok(DurSpec::Auto);
    }
    if let Ok(duration) = value.cast::<PyDuration>() {
        return Ok(duration.get().0.clone());
    }
    if let Ok(seconds) = value.extract::<f32>() {
        return Ok(DurSpec::Seconds(seconds));
    }
    Err(PyTypeError::new_err(
        "duration must be a Duration, a number of seconds or None",
    ))
}

/// An owned `fframes::AudioTimestamp`.
#[derive(Clone, Debug)]
pub enum TsSpec {
    Eof,
    Frame(usize),
    Second(f32),
    Time { minutes: f32, seconds: f32 },
    DurationOfAudio(String),
    Add(Box<TsSpec>, Box<TsSpec>),
    Sub(Box<TsSpec>, Box<TsSpec>),
}

impl TsSpec {
    pub fn build(&self) -> AudioTimestamp<'_> {
        match self {
            TsSpec::Eof => AudioTimestamp::Eof,
            TsSpec::Frame(frame) => AudioTimestamp::Frame(*frame),
            TsSpec::Second(second) => AudioTimestamp::Second(*second),
            TsSpec::Time { minutes, seconds } => AudioTimestamp::Time {
                minutes: *minutes,
                seconds: *seconds,
            },
            TsSpec::DurationOfAudio(file) => AudioTimestamp::DurationOfAudio(file),
            TsSpec::Add(a, b) => a.build() + b.build(),
            TsSpec::Sub(a, b) => a.build() - b.build(),
        }
    }
}

/// A point on the audio timeline. A plain number means seconds, `None` means the end of file.
#[pyclass(name = "Timestamp", module = "fframes", frozen)]
#[derive(Clone)]
pub struct PyTimestamp(pub TsSpec);

#[pymethods]
impl PyTimestamp {
    /// The end of the audio file.
    #[classattr]
    #[allow(non_snake_case)]
    fn EOF() -> Self {
        Self(TsSpec::Eof)
    }

    #[staticmethod]
    fn second(second: f32) -> Self {
        Self(TsSpec::Second(second))
    }

    #[staticmethod]
    fn frame(frame: usize) -> Self {
        Self(TsSpec::Frame(frame))
    }

    #[staticmethod]
    fn time(minutes: f32, seconds: f32) -> Self {
        Self(TsSpec::Time { minutes, seconds })
    }

    /// The length of an audio file of the media folder.
    #[staticmethod]
    fn duration_of_audio(file: String) -> Self {
        Self(TsSpec::DurationOfAudio(file))
    }

    fn __add__(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(TsSpec::Add(
            Box::new(self.0.clone()),
            Box::new(timestamp_from_any(other)?),
        )))
    }

    fn __radd__(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(TsSpec::Add(
            Box::new(timestamp_from_any(other)?),
            Box::new(self.0.clone()),
        )))
    }

    fn __sub__(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(TsSpec::Sub(
            Box::new(self.0.clone()),
            Box::new(timestamp_from_any(other)?),
        )))
    }

    fn __rsub__(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        Ok(Self(TsSpec::Sub(
            Box::new(timestamp_from_any(other)?),
            Box::new(self.0.clone()),
        )))
    }

    fn __repr__(&self) -> String {
        format!("Timestamp({:?})", self.0)
    }
}

pub fn timestamp_from_any(value: &Bound<'_, PyAny>) -> PyResult<TsSpec> {
    if value.is_none() {
        return Ok(TsSpec::Eof);
    }
    if let Ok(timestamp) = value.cast::<PyTimestamp>() {
        return Ok(timestamp.get().0.clone());
    }
    if let Ok(second) = value.extract::<f32>() {
        return Ok(TsSpec::Second(second));
    }
    Err(PyTypeError::new_err(
        "timestamp must be a Timestamp, a number of seconds or None (end of file)",
    ))
}

/// An owned `fframes::AudioTrack`.
#[derive(Clone, Debug)]
pub struct TrackSpec {
    pub file: String,
    pub start: TsSpec,
    pub end: TsSpec,
    pub mix: TrackMix,
}

impl TrackSpec {
    pub fn build(&self) -> AudioTrack<'_> {
        AudioTrack {
            file: &self.file,
            range: self.start.build()..self.end.build(),
            mix: self.mix.clone(),
        }
    }
}

pub fn build_audio_map(tracks: &[TrackSpec]) -> AudioMap<'_> {
    if tracks.is_empty() {
        AudioMap::none()
    } else {
        AudioMap::from(tracks.iter().map(TrackSpec::build).collect::<Vec<_>>())
    }
}

/// One audio file on the timeline, with its mix. Each method returns a changed copy.
#[pyclass(name = "AudioTrack", module = "fframes", frozen)]
#[derive(Clone)]
pub struct PyAudioTrack(pub TrackSpec);

impl PyAudioTrack {
    fn with(&self, change: impl FnOnce(AudioTrack<'static>) -> AudioTrack<'static>) -> Self {
        let track = AudioTrack {
            file: "",
            range: AudioTimestamp::Eof..AudioTimestamp::Eof,
            mix: self.0.mix.clone(),
        };
        let mut spec = self.0.clone();
        spec.mix = change(track).mix;
        Self(spec)
    }
}

#[pymethods]
impl PyAudioTrack {
    /// `file` plays from `start` to `end` (seconds, `Timestamp` or `None` for the end of file).
    #[new]
    #[pyo3(signature = (file, start = None, end = None))]
    fn new(
        file: String,
        start: Option<&Bound<'_, PyAny>>,
        end: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Self> {
        let start = match start {
            Some(start) if !start.is_none() => timestamp_from_any(start)?,
            _ => TsSpec::Second(0.0),
        };
        let end = match end {
            Some(end) => timestamp_from_any(end)?,
            None => TsSpec::Eof,
        };
        Ok(Self(TrackSpec {
            file,
            start,
            end,
            mix: TrackMix::default(),
        }))
    }

    #[getter]
    fn file(&self) -> &str {
        &self.0.file
    }

    fn gain_db(&self, gain_db: f32) -> Self {
        self.with(|t| t.gain_db(gain_db))
    }

    fn volume(&self, volume: f32) -> Self {
        self.with(|t| t.volume(volume))
    }

    fn pan(&self, pan: f32) -> Self {
        self.with(|t| t.pan(pan))
    }

    fn fade_in(&self, seconds: f32) -> Self {
        self.with(|t| t.fade_in(seconds))
    }

    fn fade_out(&self, seconds: f32) -> Self {
        self.with(|t| t.fade_out(seconds))
    }

    /// "linear", "equal-power", "s-curve" or "exponential".
    fn fade_curve(&self, curve: &str) -> PyResult<Self> {
        let curve = match curve.to_ascii_lowercase().replace('_', "-").as_str() {
            "linear" => FadeCurve::Linear,
            "equal-power" => FadeCurve::EqualPower,
            "s-curve" => FadeCurve::SCurve,
            "exponential" => FadeCurve::Exponential,
            other => {
                return Err(PyValueError::new_err(format!(
                    "unknown fade curve {other:?}"
                )));
            }
        };
        Ok(self.with(|t| t.fade_curve(curve)))
    }

    fn offset(&self, seconds: f32) -> Self {
        self.with(|t| t.offset(seconds))
    }

    fn voice(&self) -> Self {
        self.with(AudioTrack::voice)
    }

    fn duck_under_voice(&self) -> Self {
        self.with(AudioTrack::duck_under_voice)
    }

    #[pyo3(signature = (depth_db = -12.0, attack = 0.2, hold = 0.3, release = 0.8, merge_gap = 0.8))]
    fn duck(&self, depth_db: f32, attack: f32, hold: f32, release: f32, merge_gap: f32) -> Self {
        self.with(|t| {
            t.duck(Ducking {
                depth_db,
                attack,
                hold,
                release,
                merge_gap,
            })
        })
    }

    fn rate(&self, rate: f32) -> Self {
        self.with(|t| t.rate(rate))
    }

    fn normalize_lufs(&self, lufs: f32) -> Self {
        self.with(|t| t.normalize_lufs(lufs))
    }

    fn highpass(&self, hz: f32) -> Self {
        self.with(|t| t.highpass(hz))
    }

    fn lowpass(&self, hz: f32) -> Self {
        self.with(|t| t.lowpass(hz))
    }

    fn low_shelf(&self, hz: f32, db: f32) -> Self {
        self.with(|t| t.low_shelf(hz, db))
    }

    fn high_shelf(&self, hz: f32, db: f32) -> Self {
        self.with(|t| t.high_shelf(hz, db))
    }

    fn peak(&self, hz: f32, db: f32, q: f32) -> Self {
        self.with(|t| t.peak(hz, db, q))
    }

    fn width(&self, width: f32) -> Self {
        self.with(|t| t.width(width))
    }

    fn __repr__(&self) -> String {
        format!(
            "AudioTrack({:?}, {:?}..{:?})",
            self.0.file, self.0.start, self.0.end
        )
    }
}

/// Tracks from `None`, or an iterable of `AudioTrack` or `(file, start[, end])` tuples.
pub fn audio_from_any(value: Option<&Bound<'_, PyAny>>) -> PyResult<Vec<TrackSpec>> {
    let Some(value) = value else {
        return Ok(Vec::new());
    };
    if value.is_none() {
        return Ok(Vec::new());
    }
    let mut tracks = Vec::new();
    for item in value.try_iter()? {
        let item = item?;
        if let Ok(track) = item.cast::<PyAudioTrack>() {
            tracks.push(track.get().0.clone());
        } else if let Ok(tuple) = item.cast::<PyTuple>() {
            let file = tuple.get_item(0)?;
            let file = file.cast::<PyString>()?.to_cow()?.into_owned();
            let start = tuple.get_item(1).ok();
            let end = tuple.get_item(2).ok();
            tracks.push(PyAudioTrack::new(file, start.as_ref(), end.as_ref())?.0);
        } else {
            return Err(PyTypeError::new_err(
                "audio entries must be AudioTrack or (file, start, end) tuples",
            ));
        }
    }
    Ok(tracks)
}

/// How many seconds a scene overlaps the scene before and the scene after it.
#[derive(Clone, Copy, Debug, Default)]
pub struct OverlapSpec {
    pub previous: f32,
    pub next: f32,
}

impl OverlapSpec {
    pub fn build(self) -> Overlap {
        match (self.previous > 0.0, self.next > 0.0) {
            (false, false) => Overlap::None,
            (true, false) => Overlap::Previous(self.previous),
            (false, true) => Overlap::Next(self.next),
            (true, true) => Overlap::PreviousAndNext {
                previous: self.previous,
                next: self.next,
            },
        }
    }
}

/// An overlap from `None`, a number (seconds into the next scene) or `(previous, next)`.
pub fn overlap_from_any(value: Option<&Bound<'_, PyAny>>) -> PyResult<OverlapSpec> {
    let Some(value) = value else {
        return Ok(OverlapSpec::default());
    };
    if value.is_none() {
        return Ok(OverlapSpec::default());
    }
    if let Ok(next) = value.extract::<f32>() {
        return Ok(OverlapSpec {
            previous: 0.0,
            next,
        });
    }
    if let Ok((previous, next)) = value.extract::<(f32, f32)>() {
        return Ok(OverlapSpec { previous, next });
    }
    Err(PyTypeError::new_err(
        "overlap must be None, seconds into the next scene or (previous, next)",
    ))
}
