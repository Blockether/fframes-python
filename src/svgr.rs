//! `fframes.svgr(markup, **values)`: the runtime twin of the `svgr!` macro.
//!
//! A template compiles once into a node tree with holes. The compile step does what the macro
//! does at build time: it types static attribute values, expands static `style` attributes and
//! gives every fully static subtree a content hash, so the renderers cache it between frames.
//! Each frame only converts the values of the holes.

use std::borrow::Cow;
use std::collections::HashMap;
use std::hash::{DefaultHasher, Hash, Hasher};
use std::str::FromStr;
use std::sync::Arc;

use fframes::usvgr::svgtree::{
    AId, Attribute, EId, NestedNodeData, NestedNodeKind, StaticPathData, StringStorage,
    SvgAttributeValue, roxmltree, svgrtypes,
};
use pyo3::exceptions::{PyKeyError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyBool, PyDict, PyFloat, PyInt, PyString, PyTuple};

use crate::values::{PyColor, PyImage, PyPath, PyTransform};

pub type Nodes = Vec<Option<NestedNodeData<'static>>>;

/// Opens a hole inside an attribute value, the hole index follows, then [`HOLE_END`].
const HOLE_START: char = '\u{E000}';
const HOLE_END: char = '\u{E001}';
const HOLE_TAG: &str = "ff-hole";
const ROOT_TAG: &str = "ff-root";

/// An SVG fragment: what `render_frame` returns and what goes into a hole.
#[pyclass(name = "Svgr", module = "fframes", frozen)]
pub struct PySvgr {
    pub nodes: Nodes,
}

impl PySvgr {
    pub fn into_svgr(nodes: Nodes) -> fframes::Svgr<'static> {
        fframes::Svgr {
            svg_tree: fframes::usvgr::svgtree::NestedSvgDocument::from_nodes(nodes),
        }
    }
}

#[pymethods]
impl PySvgr {
    /// A fragment with no nodes.
    #[staticmethod]
    fn empty() -> Self {
        Self { nodes: Vec::new() }
    }

    /// One fragment with the nodes of every item (fragments, strings, numbers, nested lists).
    #[staticmethod]
    fn concat(items: &Bound<'_, PyAny>) -> PyResult<Self> {
        let mut nodes = Vec::new();
        push_child_value(items, &mut nodes)?;
        Ok(Self { nodes })
    }

    /// A text node, to use inside `<text>`.
    #[staticmethod]
    fn text(value: &str) -> Self {
        Self {
            nodes: vec![Some(text_node(value))],
        }
    }

    fn __add__(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        let mut nodes = self.nodes.clone();
        push_child_value(other, &mut nodes)?;
        Ok(Self { nodes })
    }

    fn __radd__(&self, other: &Bound<'_, PyAny>) -> PyResult<Self> {
        let mut nodes = Vec::new();
        push_child_value(other, &mut nodes)?;
        nodes.extend(self.nodes.iter().cloned());
        Ok(Self { nodes })
    }

    fn __len__(&self) -> usize {
        self.nodes.len()
    }

    fn __bool__(&self) -> bool {
        !self.nodes.is_empty()
    }

    /// The fragment as SVG markup.
    fn to_svg(&self) -> String {
        Self::into_svgr(self.nodes.clone()).to_string()
    }

    fn __str__(&self) -> String {
        self.to_svg()
    }

    fn __repr__(&self) -> String {
        let svg = self.to_svg();
        let short: String = svg.chars().take(80).collect();
        if short.len() < svg.len() {
            format!("Svgr({short:?}...)")
        } else {
            format!("Svgr({short:?})")
        }
    }
}

fn text_node(value: &str) -> NestedNodeData<'static> {
    NestedNodeData {
        kind: NestedNodeKind::Text(StringStorage::new_owned(value)),
        attrs: Box::new([]),
        children: Vec::new(),
        static_hash: None,
    }
}

// ---------------------------------------------------------------------------------------------
// Compiled template
// ---------------------------------------------------------------------------------------------

enum Part {
    Text(String),
    Hole(usize),
}

enum TAttr {
    Static {
        name: AId,
        source: String,
        value: SvgAttributeValue<'static>,
    },
    Hole {
        name: AId,
        element: EId,
        hole: usize,
    },
    Format {
        name: AId,
        element: EId,
        parts: Vec<Part>,
    },
}

impl TAttr {
    fn name(&self) -> AId {
        match self {
            TAttr::Static { name, .. } | TAttr::Hole { name, .. } | TAttr::Format { name, .. } => {
                *name
            }
        }
    }

    fn static_source(&self) -> Option<&str> {
        match self {
            TAttr::Static { source, .. } => Some(source),
            _ => None,
        }
    }
}

enum TChild {
    Node(TNode),
    Hole(usize),
}

struct TNode {
    kind: NestedNodeKind<'static>,
    attrs: Vec<TAttr>,
    children: Vec<TChild>,
    static_hash: Option<u64>,
    /// The whole node when its subtree has no hole: instances clone it.
    prebuilt: Option<NestedNodeData<'static>>,
}

impl TNode {
    fn tag_name(&self) -> Option<EId> {
        match self.kind {
            NestedNodeKind::Element { tag_name } => Some(tag_name),
            _ => None,
        }
    }

    fn static_attr(&self, name: AId) -> Option<&str> {
        self.attrs
            .iter()
            .find(|attr| attr.name() == name)
            .and_then(TAttr::static_source)
    }

    fn has_holes(&self) -> bool {
        self.attrs.iter().any(|a| !matches!(a, TAttr::Static { .. }))
            || self.children.iter().any(|c| match c {
                TChild::Hole(_) => true,
                TChild::Node(node) => node.has_holes(),
            })
    }

    fn build_static(&self) -> NestedNodeData<'static> {
        NestedNodeData {
            kind: self.kind.clone(),
            attrs: self
                .attrs
                .iter()
                .map(|attr| match attr {
                    TAttr::Static { name, value, .. } => Attribute {
                        name: *name,
                        value: value.clone(),
                    },
                    _ => unreachable!("a static node has only static attributes"),
                })
                .collect(),
            children: self
                .children
                .iter()
                .map(|child| match child {
                    TChild::Node(node) => Some(node.build_static()),
                    TChild::Hole(_) => unreachable!("a static node has no holes"),
                })
                .collect(),
            static_hash: self.static_hash,
        }
    }

    fn prebuild(&mut self) {
        if self.has_holes() {
            for child in &mut self.children {
                if let TChild::Node(node) = child {
                    node.prebuild();
                }
            }
        } else {
            self.prebuilt = Some(self.build_static());
        }
    }
}

/// Where the values of the holes come from.
#[derive(Clone)]
enum HoleNames {
    /// `{name}` holes, filled from keyword arguments.
    Named(Vec<String>),
    /// The interpolations of a t-string, in order.
    Positional(usize),
}

pub struct Template {
    nodes: Vec<TChild>,
    names: HoleNames,
}

/// The value of each hole for one instance.
pub struct Values<'py> {
    values: Vec<Bound<'py, PyAny>>,
}

impl Template {
    fn instantiate(&self, values: &Values<'_>) -> PyResult<Nodes> {
        let mut out = Vec::with_capacity(self.nodes.len());
        for child in &self.nodes {
            instantiate_child(child, values, &mut out)?;
        }
        Ok(out)
    }

    fn values_from_kwargs<'py>(
        &self,
        py: Python<'py>,
        kwargs: Option<&Bound<'py, PyDict>>,
    ) -> PyResult<Values<'py>> {
        match &self.names {
            HoleNames::Named(names) => {
                let mut values = Vec::with_capacity(names.len());
                for name in names {
                    let value = kwargs
                        .map(|kw| kw.get_item(name))
                        .transpose()?
                        .flatten()
                        .ok_or_else(|| {
                            PyKeyError::new_err(format!("svgr: no value for the hole {{{name}}}"))
                        })?;
                    values.push(value);
                }
                Ok(Values { values })
            }
            HoleNames::Positional(count) => {
                if *count != 0 {
                    return Err(PyTypeError::new_err(
                        "svgr: this template comes from a t-string, call it with one",
                    ));
                }
                let _ = py;
                Ok(Values { values: Vec::new() })
            }
        }
    }
}

fn instantiate_child(child: &TChild, values: &Values<'_>, out: &mut Nodes) -> PyResult<()> {
    match child {
        TChild::Hole(index) => push_child_value(&values.values[*index], out),
        TChild::Node(node) => {
            out.push(Some(instantiate_node(node, values)?));
            Ok(())
        }
    }
}

fn instantiate_node(node: &TNode, values: &Values<'_>) -> PyResult<NestedNodeData<'static>> {
    if let Some(prebuilt) = &node.prebuilt {
        return Ok(prebuilt.clone());
    }

    let mut attrs = Vec::with_capacity(node.attrs.len());
    for attr in &node.attrs {
        match attr {
            TAttr::Static { name, value, .. } => attrs.push(Attribute {
                name: *name,
                value: value.clone(),
            }),
            TAttr::Hole {
                name,
                element,
                hole,
            } => {
                if let Some(value) = dynamic_attribute_value(&values.values[*hole], *name, *element)? {
                    attrs.push(Attribute { name: *name, value });
                }
            }
            TAttr::Format {
                name,
                element,
                parts,
            } => {
                let mut text = String::new();
                for part in parts {
                    match part {
                        Part::Text(s) => text.push_str(s),
                        Part::Hole(index) => push_display(&values.values[*index], &mut text)?,
                    }
                }
                attrs.push(Attribute {
                    name: *name,
                    value: typed_value(text, *name, *element, false),
                });
            }
        }
    }

    let mut children = Vec::with_capacity(node.children.len());
    for child in &node.children {
        instantiate_child(child, values, &mut children)?;
    }

    Ok(NestedNodeData {
        kind: node.kind.clone(),
        attrs: attrs.into_boxed_slice(),
        children,
        static_hash: node.static_hash,
    })
}

/// Text of a value inside an attribute that also has literal text, e.g. `translate({x} 0)`.
fn push_display(value: &Bound<'_, PyAny>, out: &mut String) -> PyResult<()> {
    use std::fmt::Write;
    if let Ok(f) = value.cast::<PyFloat>() {
        let _ = write!(out, "{}", f.value());
    } else if value.is_instance_of::<PyBool>() {
        out.push_str(if value.is_truthy()? { "true" } else { "false" });
    } else if let Ok(s) = value.cast::<PyString>() {
        out.push_str(&s.to_cow()?);
    } else {
        out.push_str(&value.str()?.to_cow()?);
    }
    Ok(())
}

/// The value of a hole that is a whole attribute value. `None` drops the attribute.
fn dynamic_attribute_value(
    value: &Bound<'_, PyAny>,
    name: AId,
    element: EId,
) -> PyResult<Option<SvgAttributeValue<'static>>> {
    if value.is_none() {
        return Ok(None);
    }
    if let Ok(f) = value.cast::<PyFloat>() {
        return Ok(Some(SvgAttributeValue::from(f.value())));
    }
    if value.is_instance_of::<PyBool>() {
        let text = if value.is_truthy()? { "true" } else { "false" };
        return Ok(Some(SvgAttributeValue::StringStorage(StringStorage::Borrowed(text))));
    }
    if let Ok(i) = value.cast::<PyInt>() {
        let v: f64 = i.extract()?;
        return Ok(Some(SvgAttributeValue::from(v)));
    }
    if let Ok(s) = value.cast::<PyString>() {
        return Ok(Some(SvgAttributeValue::StringStorage(StringStorage::new_owned(
            &*s.to_cow()?,
        ))));
    }
    if let Ok(color) = value.cast::<PyColor>() {
        return Ok(Some(SvgAttributeValue::from(color.get().0)));
    }
    if let Ok(transform) = value.cast::<PyTransform>() {
        return Ok(Some(SvgAttributeValue::from(transform.get().0)));
    }
    if let Ok(image) = value.cast::<PyImage>() {
        return Ok(Some(SvgAttributeValue::ImageData(image.get().data.clone())));
    }
    if let Ok(path) = value.cast::<PyPath>() {
        return Ok(Some(SvgAttributeValue::PathData(Cow::Owned(
            path.get().segments.clone(),
        ))));
    }
    let text = value.str()?.to_cow()?.into_owned();
    Ok(Some(typed_value(text, name, element, false)))
}

/// Appends the nodes of a value in a child position.
pub fn push_child_value(value: &Bound<'_, PyAny>, out: &mut Nodes) -> PyResult<()> {
    if value.is_none() {
        return Ok(());
    }
    if let Ok(svgr) = value.cast::<PySvgr>() {
        out.extend(svgr.get().nodes.iter().cloned());
        return Ok(());
    }
    if let Ok(s) = value.cast::<PyString>() {
        out.push(Some(text_node(&s.to_cow()?)));
        return Ok(());
    }
    if value.is_instance_of::<PyBool>() {
        return Err(PyTypeError::new_err(
            "svgr: a bool can not be a child, use `x if cond else None`",
        ));
    }
    if value.is_instance_of::<PyFloat>() || value.is_instance_of::<PyInt>() {
        out.push(Some(text_node(&value.str()?.to_cow()?)));
        return Ok(());
    }
    if let Ok(iter) = value.try_iter() {
        for item in iter {
            push_child_value(&item?, out)?;
        }
        return Ok(());
    }
    Err(PyTypeError::new_err(format!(
        "svgr: a child must be Svgr, str, a number, None or an iterable of those, not {}",
        value.get_type().name()?
    )))
}

// ---------------------------------------------------------------------------------------------
// Attribute values, as the macro types them
// ---------------------------------------------------------------------------------------------

/// Attributes usvgr reads a color from (svgr-macro `accepts_color`).
fn accepts_color(aid: AId) -> bool {
    matches!(
        aid,
        AId::Fill | AId::Stroke | AId::StopColor | AId::FloodColor | AId::LightingColor | AId::Color
    )
}

/// Attributes usvgr reads as a transform (svgr-macro `accepts_transform`).
fn accepts_transform(aid: AId) -> bool {
    matches!(
        aid,
        AId::Transform | AId::GradientTransform | AId::PatternTransform
    )
}

fn path_segments(value: &str) -> Option<Vec<svgrtypes::PathSegment>> {
    svgrtypes::PathParser::from(value)
        .collect::<Result<Vec<_>, _>>()
        .ok()
        .filter(|segments| !segments.is_empty())
}

fn points_to_segments(value: &str, element: EId) -> Option<Vec<svgrtypes::PathSegment>> {
    use svgrtypes::PathSegment;
    let mut segments: Vec<_> = svgrtypes::PointsParser::from(value)
        .enumerate()
        .map(|(index, (x, y))| {
            if index == 0 {
                PathSegment::MoveTo { abs: true, x, y }
            } else {
                PathSegment::LineTo { abs: true, x, y }
            }
        })
        .collect();
    if segments.len() < 2 {
        return None;
    }
    if element == EId::Polygon {
        segments.push(PathSegment::ClosePath { abs: true });
    }
    Some(segments)
}

/// Types a textual attribute value like svgr-macro `inline_attribute_value`. A static value of a
/// template keeps its path geometry in a `StaticPathData`, so its `tiny_skia` path is built once.
fn typed_value(value: String, aid: AId, element: EId, is_static: bool) -> SvgAttributeValue<'static> {
    let geometry = if aid == AId::D {
        path_segments(&value)
    } else if aid == AId::Points && matches!(element, EId::Polygon | EId::Polyline) {
        points_to_segments(&value, element)
    } else {
        None
    };
    if let Some(segments) = geometry {
        if is_static {
            // Templates live for the whole process, see `template_cache`.
            let segments: &'static [svgrtypes::PathSegment] = Box::leak(segments.into_boxed_slice());
            let path: &'static StaticPathData = Box::leak(Box::new(StaticPathData::new(segments)));
            return SvgAttributeValue::StaticPath(path);
        }
        return SvgAttributeValue::PathData(Cow::Owned(segments));
    }

    if let Ok(float) = f32::from_str(&value) {
        return SvgAttributeValue::Float(float, StringStorage::new_owned(value));
    }
    if accepts_color(aid) {
        if let Ok(color) = svgrtypes::Color::from_str(&value) {
            return SvgAttributeValue::Color(color);
        }
    }
    if let Ok(length) = svgrtypes::Length::from_str(&value) {
        return SvgAttributeValue::Length(length);
    }
    if accepts_transform(aid) {
        if let Ok(transform) = svgrtypes::Transform::from_str(&value) {
            return SvgAttributeValue::Transform(transform);
        }
    }
    SvgAttributeValue::StringStorage(StringStorage::new_owned(value))
}

// ---------------------------------------------------------------------------------------------
// Compiling: markup -> XML with sentinels -> template nodes
// ---------------------------------------------------------------------------------------------

enum Piece<'s> {
    Text(&'s str),
    Hole(usize),
}

/// Splits `{name}` holes out of markup. `{{` and `}}` are literal braces.
fn split_named(markup: &str) -> PyResult<(Vec<Piece<'_>>, Vec<String>)> {
    let mut pieces = Vec::new();
    let mut names: Vec<String> = Vec::new();
    let bytes = markup.as_bytes();
    let mut start = 0;
    let mut i = 0;
    while i < bytes.len() {
        match bytes[i] {
            b'{' if bytes.get(i + 1) == Some(&b'{') => {
                pieces.push(Piece::Text(&markup[start..=i]));
                i += 2;
                start = i;
            }
            b'}' if bytes.get(i + 1) == Some(&b'}') => {
                pieces.push(Piece::Text(&markup[start..=i]));
                i += 2;
                start = i;
            }
            b'{' => {
                let end = markup[i + 1..].find('}').map(|p| p + i + 1).ok_or_else(|| {
                    PyValueError::new_err(format!("svgr: unclosed '{{' at byte {i}"))
                })?;
                let name = markup[i + 1..end].trim();
                if name.is_empty() || !name.chars().all(|c| c.is_alphanumeric() || c == '_') {
                    return Err(PyValueError::new_err(format!(
                        "svgr: a hole is a keyword name like {{opacity}}, got {{{name}}}; \
                         write {{{{ and }}}} for literal braces"
                    )));
                }
                pieces.push(Piece::Text(&markup[start..i]));
                let index = names.iter().position(|n| n == name).unwrap_or_else(|| {
                    names.push(name.to_owned());
                    names.len() - 1
                });
                pieces.push(Piece::Hole(index));
                i = end + 1;
                start = i;
            }
            b'}' => {
                return Err(PyValueError::new_err(format!(
                    "svgr: single '}}' at byte {i}; write '}}}}' for a literal brace"
                )));
            }
            _ => i += 1,
        }
    }
    pieces.push(Piece::Text(&markup[start..]));
    Ok((pieces, names))
}

/// Joins the pieces into parseable XML: a hole in an attribute value becomes sentinel text, a
/// hole between elements becomes `<ff-hole n="i"/>`.
fn pieces_to_xml(pieces: &[Piece<'_>]) -> PyResult<String> {
    #[derive(PartialEq, Clone, Copy)]
    enum State {
        Content,
        Tag,
        AfterEq,
        Quoted(u8),
        Comment,
    }
    let mut xml = String::from("<ff-root xmlns:xlink=\"http://www.w3.org/1999/xlink\">");
    let mut state = State::Content;
    for piece in pieces {
        match piece {
            Piece::Text(text) => {
                let bytes = text.as_bytes();
                let mut i = 0;
                while i < bytes.len() {
                    let b = bytes[i];
                    state = match state {
                        State::Content if bytes[i..].starts_with(b"<!--") => State::Comment,
                        State::Comment if bytes[i..].starts_with(b"-->") => State::Content,
                        State::Content if b == b'<' => State::Tag,
                        State::Tag if b == b'>' => State::Content,
                        State::Tag if b == b'=' => State::AfterEq,
                        State::AfterEq if b == b'"' || b == b'\'' => State::Quoted(b),
                        State::AfterEq if !b.is_ascii_whitespace() => State::Tag,
                        State::Quoted(q) if b == q => State::Tag,
                        other => other,
                    };
                    i += 1;
                }
                xml.push_str(text);
            }
            Piece::Hole(index) => match state {
                State::Content => {
                    use std::fmt::Write;
                    let _ = write!(xml, "<{HOLE_TAG} n=\"{index}\"/>");
                }
                State::Quoted(_) => {
                    xml.push(HOLE_START);
                    xml.push_str(&index.to_string());
                    xml.push(HOLE_END);
                }
                State::AfterEq => {
                    xml.push('"');
                    xml.push(HOLE_START);
                    xml.push_str(&index.to_string());
                    xml.push(HOLE_END);
                    xml.push('"');
                    state = State::Tag;
                }
                State::Tag => {
                    return Err(PyValueError::new_err(
                        "svgr: a hole inside a tag must be an attribute value, like r={r}",
                    ));
                }
                State::Comment => {}
            },
        }
    }
    xml.push_str("</ff-root>");
    Ok(xml)
}

fn parse_attr_parts(value: &str) -> Option<Vec<Part>> {
    if !value.contains(HOLE_START) {
        return None;
    }
    let mut parts = Vec::new();
    let mut rest = value;
    while let Some(start) = rest.find(HOLE_START) {
        if start > 0 {
            parts.push(Part::Text(rest[..start].to_owned()));
        }
        let after = &rest[start + HOLE_START.len_utf8()..];
        let end = after.find(HOLE_END).unwrap_or(after.len());
        let index = after[..end].parse().unwrap_or(0);
        parts.push(Part::Hole(index));
        rest = &after[(end + HOLE_END.len_utf8()).min(after.len())..];
    }
    if !rest.is_empty() {
        parts.push(Part::Text(rest.to_owned()));
    }
    Some(parts)
}

fn element_error(node: &roxmltree::Node<'_, '_>, message: String) -> PyErr {
    let pos = node.document().text_pos_at(node.range().start);
    PyValueError::new_err(format!(
        "svgr: {message} (line {}, column {})",
        pos.row, pos.col
    ))
}

fn parse_attributes(node: &roxmltree::Node<'_, '_>, element: EId) -> PyResult<Vec<TAttr>> {
    let mut attrs = Vec::new();
    for attr in node.attributes() {
        let name = match attr.namespace() {
            Some("http://www.w3.org/XML/1998/namespace") => continue,
            _ => attr.name(),
        };
        let aid = AId::from_str(name).ok_or_else(|| {
            element_error(
                node,
                format!(
                    "the attribute `{name}` of <{}> is not supported",
                    node.tag_name().name()
                ),
            )
        })?;
        if aid == AId::Class {
            return Err(element_error(
                node,
                "the `class` attribute is not supported: use attributes or style=\"\"".into(),
            ));
        }
        let value = attr.value();
        attrs.push(match parse_attr_parts(value) {
            Some(parts) => match parts.as_slice() {
                [Part::Hole(hole)] => TAttr::Hole {
                    name: aid,
                    element,
                    hole: *hole,
                },
                _ => TAttr::Format {
                    name: aid,
                    element,
                    parts,
                },
            },
            None => TAttr::Static {
                name: aid,
                source: value.to_owned(),
                value: typed_value(value.to_owned(), aid, element, true),
            },
        });
    }
    Ok(expand_static_style(attrs, element))
}

/// svgr-macro `expand_static_style`: a static `style` becomes the attributes that it sets.
fn expand_static_style(attributes: Vec<TAttr>, element: EId) -> Vec<TAttr> {
    let Some(style_index) = attributes
        .iter()
        .position(|attr| attr.name() == AId::Style && attr.static_source().is_some())
    else {
        return attributes;
    };
    let style = attributes[style_index].static_source().unwrap_or_default();

    let mut declarations: Vec<(AId, String)> = Vec::new();
    for declaration in simplecss::DeclarationTokenizer::from(style) {
        let Some(aid) = AId::from_str(declaration.name) else {
            continue;
        };
        if !aid.is_presentation() {
            continue;
        }
        if declaration.value == "inherit" {
            return attributes;
        }
        declarations.retain(|(existing, _)| *existing != aid);
        declarations.push((aid, declaration.value.to_owned()));
    }

    let clashes = attributes.iter().enumerate().any(|(index, attr)| {
        index != style_index && declarations.iter().any(|(aid, _)| *aid == attr.name())
    });
    if clashes {
        return attributes;
    }

    let mut expanded = Vec::with_capacity(attributes.len() + declarations.len());
    for (index, attr) in attributes.into_iter().enumerate() {
        if index == style_index {
            expanded.extend(declarations.drain(..).map(|(name, value)| TAttr::Static {
                name,
                value: typed_value(value.clone(), name, element, true),
                source: value,
            }));
        } else {
            expanded.push(attr);
        }
    }
    expanded
}

fn is_text_element(eid: EId) -> bool {
    matches!(eid, EId::Text | EId::Tspan | EId::TextPath)
}

fn hole_index(node: &roxmltree::Node<'_, '_>) -> Option<usize> {
    (node.tag_name().name() == HOLE_TAG)
        .then(|| node.attribute("n").and_then(|n| n.parse().ok()))
        .flatten()
}

fn parse_tag(node: &roxmltree::Node<'_, '_>) -> PyResult<EId> {
    let name = node.tag_name().name();
    EId::from_str(name)
        .ok_or_else(|| element_error(node, format!("the element <{name}> is not supported")))
}

/// Children of an element that is not a text element: elements and holes, text is ignored.
fn parse_children(node: &roxmltree::Node<'_, '_>) -> PyResult<Vec<TChild>> {
    let mut children = Vec::new();
    for child in node.children() {
        if !child.is_element() {
            continue;
        }
        if let Some(index) = hole_index(&child) {
            children.push(TChild::Hole(index));
            continue;
        }
        let tag_name = parse_tag(&child)?;
        if tag_name == EId::Style {
            return Err(element_error(
                &child,
                "<style> is not supported: use attributes or style=\"\"".into(),
            ));
        }
        let attrs = parse_attributes(&child, tag_name)?;
        let grandchildren = if is_text_element(tag_name) {
            parse_text_children(&child, tag_name)?
        } else {
            parse_children(&child)?
        };
        children.push(TChild::Node(TNode {
            kind: NestedNodeKind::Element { tag_name },
            attrs,
            children: grandchildren,
            static_hash: None,
            prebuilt: None,
        }));
    }
    Ok(children)
}

/// Collapses XML whitespace like SVG `xml:space="default"`: runs of whitespace become one space,
/// the first text of an element loses its leading space, the last its trailing space, and pure
/// indentation (whitespace with a line break) disappears.
fn normalize_text(text: &str, is_first: bool, is_last: bool) -> Option<String> {
    if text.trim().is_empty() && text.contains('\n') {
        return None;
    }
    let mut out = String::with_capacity(text.len());
    let mut in_space = false;
    for c in text.chars() {
        if c.is_whitespace() {
            if !in_space {
                out.push(' ');
            }
            in_space = true;
        } else {
            out.push(c);
            in_space = false;
        }
    }
    let mut out = out.as_str();
    if is_first {
        out = out.trim_start();
    }
    if is_last {
        out = out.trim_end();
    }
    (!out.is_empty()).then(|| out.to_owned())
}

/// Children of `text`, `tspan` and `textPath`: text, holes, `tspan` and `textPath`.
fn parse_text_children(node: &roxmltree::Node<'_, '_>, parent: EId) -> PyResult<Vec<TChild>> {
    let all: Vec<_> = node
        .children()
        .filter(|c| c.is_text() || c.is_element())
        .collect();
    let mut children = Vec::new();
    for (index, child) in all.iter().enumerate() {
        if child.is_text() {
            let text = child.text().unwrap_or_default();
            if let Some(text) = normalize_text(text, index == 0, index + 1 == all.len()) {
                children.push(TChild::Node(TNode {
                    kind: NestedNodeKind::Text(StringStorage::new_owned(text)),
                    attrs: Vec::new(),
                    children: Vec::new(),
                    static_hash: None,
                    prebuilt: None,
                }));
            }
            continue;
        }
        if let Some(hole) = hole_index(child) {
            children.push(TChild::Hole(hole));
            continue;
        }
        let tag_name = parse_tag(child)?;
        if !matches!(tag_name, EId::Tspan | EId::TextPath) {
            continue;
        }
        if tag_name == EId::TextPath && parent != EId::Text {
            continue;
        }
        children.push(TChild::Node(TNode {
            kind: NestedNodeKind::Element { tag_name },
            attrs: parse_attributes(child, tag_name)?,
            children: parse_text_children(child, tag_name)?,
            static_hash: None,
            prebuilt: None,
        }));
    }
    Ok(children)
}

// ---------------------------------------------------------------------------------------------
// Static hashes (svgr-macro `assign_static_hashes`)
// ---------------------------------------------------------------------------------------------

fn is_inheritable(aid: AId) -> bool {
    matches!(
        aid,
        AId::ClipRule
            | AId::Color
            | AId::ColorInterpolation
            | AId::ColorInterpolationFilters
            | AId::ColorRendering
            | AId::Direction
            | AId::Fill
            | AId::FillOpacity
            | AId::FillRule
            | AId::FontFamily
            | AId::FontKerning
            | AId::FontSize
            | AId::FontSizeAdjust
            | AId::FontStretch
            | AId::FontStyle
            | AId::FontVariant
            | AId::FontWeight
            | AId::GlyphOrientationHorizontal
            | AId::GlyphOrientationVertical
            | AId::ImageRendering
            | AId::Isolation
            | AId::LetterSpacing
            | AId::MarkerEnd
            | AId::MarkerMid
            | AId::MarkerStart
            | AId::MaskType
            | AId::MixBlendMode
            | AId::PaintOrder
            | AId::ShapeRendering
            | AId::Stroke
            | AId::StrokeDasharray
            | AId::StrokeDashoffset
            | AId::StrokeLinecap
            | AId::StrokeLinejoin
            | AId::StrokeMiterlimit
            | AId::StrokeOpacity
            | AId::StrokeWidth
            | AId::TextAnchor
            | AId::TextOverflow
            | AId::TextRendering
            | AId::UnicodeBidi
            | AId::VectorEffect
            | AId::Visibility
            | AId::WhiteSpace
            | AId::WordSpacing
            | AId::WritingMode
            | AId::TextDecoration
            | AId::Style
    )
}

fn establishes_viewport(eid: EId) -> bool {
    matches!(eid, EId::Svg | EId::Symbol | EId::Pattern | EId::Marker)
}

fn is_viewport_attribute(aid: AId) -> bool {
    matches!(
        aid,
        AId::Width | AId::Height | AId::ViewBox | AId::PreserveAspectRatio
    )
}

fn collect_references(aid: AId, value: &str, out: &mut Vec<String>) {
    if aid == AId::Href {
        if let Some(id) = value.strip_prefix('#') {
            out.push(id.to_owned());
        }
        return;
    }
    let mut rest = value;
    while let Some(pos) = rest.find("url(") {
        rest = &rest[pos + "url(".len()..];
        let end = rest.find(')').unwrap_or(rest.len());
        let target = rest[..end].trim().trim_matches(['"', '\'']).trim();
        if let Some(id) = target.strip_prefix('#') {
            out.push(id.to_owned());
        }
        rest = &rest[end..];
    }
}

#[derive(Clone, Copy, Default)]
struct AncestorContext {
    dynamic_inherited: bool,
    dynamic_viewport: bool,
    inherited_hash: u64,
}

struct StaticCandidate {
    local_hash: Option<u64>,
    references: Vec<String>,
}

fn hash_content(node: &TNode, hasher: &mut impl Hasher) {
    match &node.kind {
        NestedNodeKind::Root => 2u8.hash(hasher),
        NestedNodeKind::Element { tag_name } => {
            0u8.hash(hasher);
            (*tag_name as u16).hash(hasher);
        }
        NestedNodeKind::Text(storage) => {
            1u8.hash(hasher);
            storage.as_str().hash(hasher);
        }
    }
    node.attrs.len().hash(hasher);
    for attr in &node.attrs {
        if let Some(source) = attr.static_source() {
            (attr.name() as u16).hash(hasher);
            source.hash(hasher);
        }
    }
    node.children.len().hash(hasher);
    for child in &node.children {
        if let TChild::Node(child) = child {
            hash_content(child, hasher);
        }
    }
}

fn collect_static_candidates(
    node: &TNode,
    ctx: AncestorContext,
    candidates: &mut Vec<StaticCandidate>,
    ids: &mut HashMap<String, usize>,
) -> (Option<u64>, Vec<String>) {
    let index = candidates.len();
    candidates.push(StaticCandidate {
        local_hash: None,
        references: Vec::new(),
    });
    if let Some(id) = node.static_attr(AId::Id) {
        ids.entry(id.to_owned()).or_insert(index);
    }

    let mut is_static = !ctx.dynamic_inherited;
    let mut references = Vec::new();
    let mut child_ctx = ctx;
    let is_viewport = node.tag_name().is_some_and(establishes_viewport);
    for attr in &node.attrs {
        let name = attr.name();
        let affects_descendants =
            is_inheritable(name) || (is_viewport && is_viewport_attribute(name));
        if let Some(value) = attr.static_source() {
            collect_references(name, value, &mut references);
            if ctx.dynamic_viewport && value.contains('%') {
                is_static = false;
            }
            if affects_descendants {
                let mut hasher = DefaultHasher::new();
                child_ctx.inherited_hash.hash(&mut hasher);
                (name as u16).hash(&mut hasher);
                value.hash(&mut hasher);
                child_ctx.inherited_hash = hasher.finish();
            }
        } else {
            is_static = false;
            if is_inheritable(name) {
                child_ctx.dynamic_inherited = true;
            }
            if is_viewport && is_viewport_attribute(name) {
                child_ctx.dynamic_viewport = true;
            }
        }
    }
    for child in &node.children {
        match child {
            TChild::Node(child) => {
                let (child_hash, child_refs) =
                    collect_static_candidates(child, child_ctx, candidates, ids);
                is_static &= child_hash.is_some();
                references.extend(child_refs);
            }
            TChild::Hole(_) => is_static = false,
        }
    }
    references.sort();
    references.dedup();

    let local_hash = is_static.then(|| {
        let mut hasher = DefaultHasher::new();
        ctx.inherited_hash.hash(&mut hasher);
        hash_content(node, &mut hasher);
        hasher.finish()
    });
    candidates[index] = StaticCandidate {
        local_hash,
        references: references.clone(),
    };
    (local_hash, references)
}

#[allow(clippy::option_option)]
fn resolve_static_hash(
    index: usize,
    candidates: &[StaticCandidate],
    ids: &HashMap<String, usize>,
    resolved: &mut [Option<Option<u64>>],
    visiting: &mut Vec<usize>,
) -> Option<u64> {
    if let Some(result) = resolved[index] {
        return result;
    }
    if visiting.contains(&index) {
        return None;
    }
    let candidate = &candidates[index];
    let result = candidate.local_hash.and_then(|local_hash| {
        if candidate.references.is_empty() {
            return Some(local_hash);
        }
        visiting.push(index);
        let mut hasher = DefaultHasher::new();
        local_hash.hash(&mut hasher);
        let mut all_static = true;
        for reference in &candidate.references {
            if let Some(hash) = ids.get(reference).and_then(|&target| {
                resolve_static_hash(target, candidates, ids, resolved, visiting)
            }) {
                hash.hash(&mut hasher);
            } else {
                all_static = false;
                break;
            }
        }
        visiting.pop();
        all_static.then(|| hasher.finish())
    });
    resolved[index] = Some(result);
    result
}

fn write_static_hashes(node: &mut TNode, hashes: &[Option<u64>], cursor: &mut usize) {
    node.static_hash = hashes[*cursor];
    *cursor += 1;
    for child in &mut node.children {
        if let TChild::Node(child) = child {
            write_static_hashes(child, hashes, cursor);
        }
    }
}

fn assign_static_hashes(nodes: &mut [TChild]) {
    let mut candidates = Vec::new();
    let mut ids = HashMap::new();
    for node in nodes.iter() {
        if let TChild::Node(node) = node {
            collect_static_candidates(node, AncestorContext::default(), &mut candidates, &mut ids);
        }
    }
    let mut resolved = vec![None; candidates.len()];
    let hashes: Vec<_> = (0..candidates.len())
        .map(|index| resolve_static_hash(index, &candidates, &ids, &mut resolved, &mut Vec::new()))
        .collect();
    let mut cursor = 0;
    for node in nodes.iter_mut() {
        if let TChild::Node(node) = node {
            write_static_hashes(node, &hashes, &mut cursor);
        }
    }
}

fn compile(pieces: &[Piece<'_>], names: HoleNames) -> PyResult<Template> {
    let xml = pieces_to_xml(pieces)?;
    let doc = roxmltree::Document::parse(&xml)
        .map_err(|err| PyValueError::new_err(format!("svgr: invalid markup: {err}")))?;
    let mut nodes = parse_children(&doc.root_element())?;
    assign_static_hashes(&mut nodes);
    for node in &mut nodes {
        if let TChild::Node(node) = node {
            node.prebuild();
        }
    }
    Ok(Template { nodes, names })
}

// ---------------------------------------------------------------------------------------------
// Python API
// ---------------------------------------------------------------------------------------------

/// A compiled template. `fframes.template(markup)` returns one; calling it with the values of
/// its holes gives an `Svgr`.
#[pyclass(name = "Template", module = "fframes", frozen)]
pub struct PyTemplate {
    inner: Arc<Template>,
}

#[pymethods]
impl PyTemplate {
    #[pyo3(signature = (**values))]
    fn __call__(&self, py: Python<'_>, values: Option<&Bound<'_, PyDict>>) -> PyResult<PySvgr> {
        let values = self.inner.values_from_kwargs(py, values)?;
        Ok(PySvgr {
            nodes: self.inner.instantiate(&values)?,
        })
    }

    /// The names of the holes.
    #[getter]
    fn holes(&self) -> Vec<String> {
        match &self.inner.names {
            HoleNames::Named(names) => names.clone(),
            HoleNames::Positional(count) => (0..*count).map(|i| i.to_string()).collect(),
        }
    }
}

/// Compiled templates, keyed by the markup string or the strings of a t-string.
fn template_cache(py: Python<'_>) -> &Bound<'_, PyDict> {
    static CACHE: PyOnceLock<Py<PyDict>> = PyOnceLock::new();
    CACHE.get_or_init(py, || PyDict::new(py).unbind()).bind(py)
}

fn compile_named(py: Python<'_>, markup: &Bound<'_, PyString>) -> PyResult<Arc<Template>> {
    let cache = template_cache(py);
    if let Some(hit) = cache.get_item(markup)? {
        return Ok(hit.cast::<PyTemplate>()?.get().inner.clone());
    }
    let text = markup.to_cow()?;
    let (pieces, names) = split_named(&text)?;
    let template = Arc::new(compile(&pieces, HoleNames::Named(names))?);
    cache.set_item(
        markup,
        PyTemplate {
            inner: template.clone(),
        },
    )?;
    Ok(template)
}

fn is_tstring(value: &Bound<'_, PyAny>) -> bool {
    value.hasattr("strings").unwrap_or(false) && value.hasattr("interpolations").unwrap_or(false)
}

/// A PEP 750 t-string: `t'<circle r={r}/>'`.
fn render_tstring<'py>(py: Python<'py>, template: &Bound<'py, PyAny>) -> PyResult<PySvgr> {
    let strings = template.getattr("strings")?;
    let strings = strings.cast::<PyTuple>()?;
    let cache = template_cache(py);
    let compiled = if let Some(hit) = cache.get_item(strings)? {
        hit.cast::<PyTemplate>()?.get().inner.clone()
    } else {
        let owned: Vec<String> = strings.extract()?;
        let mut pieces = Vec::with_capacity(owned.len() * 2);
        for (index, s) in owned.iter().enumerate() {
            if index > 0 {
                pieces.push(Piece::Hole(index - 1));
            }
            pieces.push(Piece::Text(s));
        }
        let template = Arc::new(compile(&pieces, HoleNames::Positional(owned.len() - 1))?);
        cache.set_item(
            strings,
            PyTemplate {
                inner: template.clone(),
            },
        )?;
        template
    };

    let interpolations = template.getattr("interpolations")?;
    let interpolations = interpolations.cast::<PyTuple>()?;
    let mut values = Vec::with_capacity(interpolations.len());
    for interpolation in interpolations.iter() {
        let mut value = interpolation.getattr("value")?;
        let conversion = interpolation.getattr("conversion")?;
        let spec = interpolation.getattr("format_spec")?;
        let spec = spec.cast::<PyString>()?;
        if !conversion.is_none() || !spec.to_cow()?.is_empty() {
            let builtins = py.import("builtins")?;
            if !conversion.is_none() {
                let func = match &*conversion.cast::<PyString>()?.to_cow()? {
                    "r" => "repr",
                    "a" => "ascii",
                    _ => "str",
                };
                value = builtins.getattr(func)?.call1((value,))?;
            }
            value = builtins.getattr("format")?.call1((value, spec))?;
        }
        values.push(value);
    }
    Ok(PySvgr {
        nodes: compiled.instantiate(&Values { values })?,
    })
}

/// `svgr(markup, **values)`: an SVG fragment from markup with `{name}` holes, or from a t-string.
#[pyfunction]
#[pyo3(signature = (markup, /, **values))]
pub fn svgr(
    py: Python<'_>,
    markup: &Bound<'_, PyAny>,
    values: Option<&Bound<'_, PyDict>>,
) -> PyResult<PySvgr> {
    if let Ok(markup) = markup.cast::<PyString>() {
        let template = compile_named(py, markup)?;
        let values = template.values_from_kwargs(py, values)?;
        return Ok(PySvgr {
            nodes: template.instantiate(&values)?,
        });
    }
    if is_tstring(markup) {
        return render_tstring(py, markup);
    }
    Err(PyTypeError::new_err(
        "svgr: markup must be a str with {name} holes or a t-string",
    ))
}

/// `template(markup)`: compiles markup once; call the result with the values of its holes.
#[pyfunction]
pub fn template(py: Python<'_>, markup: &Bound<'_, PyString>) -> PyResult<PyTemplate> {
    Ok(PyTemplate {
        inner: compile_named(py, markup)?,
    })
}
