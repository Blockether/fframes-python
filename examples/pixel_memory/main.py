"""Pixel Memory: a seeded photo slideshow over bokeh that ends as a heart.

Port of the upstream `pixel-memory` example. The seed picks the photos, scenes and song
through `ff.Rng`, the `rand` 0.8 `StdRng` of the Rust example, so the same seed gives the
same video. Each draw names the Rust type of its range. The math is f32 where the Rust
example uses f32.
"""

import argparse
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import _media
import fframes as ff
import numpy as np

F = np.float32
WIDTH, HEIGHT = 1920, 1080
PI32 = F(math.pi)
PHI = F((1 + 5**0.5) / 2)
VIDEO_SUFFIXES = (".mp4", ".mov", ".webm", ".mkv")

# name: (duration, tempo)
SONGS = {
    "The_Farewell.mp3": (F(166.0), F(1.12)),
    "vostok_zapomny.mp3": (F(185.62), F(1.08)),
    "naruto_grief.mp3": (F(196.0), F(1.22)),
    "revenge.mp3": (F(132.0), F(1.05)),
    "passenger.mp3": (F(189.0), F(1.2)),
}


def log(message: str) -> None:
    print(message, file=sys.stderr)


def f32_fn(fn, *args) -> np.float32:
    """A libm f32 function: the f64 result rounded to f32, as correctly rounded f32 libm does."""
    return F(fn(*(float(a) for a in args)))


class Rng:
    """Typed draws of `rand` 0.8 `StdRng`."""

    def __init__(self, seed: int):
        self.r = ff.Rng(seed)

    def f32(self, lo, hi, inclusive=False) -> np.float32:
        return F(self.r.range(float(F(lo)), float(F(hi)), "f32", inclusive))

    def f64(self, lo, hi) -> float:
        return self.r.range(float(lo), float(hi), "f64")

    def int(self, lo, hi, inclusive=False, kind="i32") -> int:
        return self.r.range(lo, hi, kind, inclusive)

    def bool(self, p=0.5) -> bool:
        return self.r.bool(p)

    def shuffle(self, items):
        return self.r.shuffle(items)

    def choose(self, items):
        return self.r.choose(items)


class RandomPhotos:
    def __init__(self, rng: Rng, images, videos):
        self.images = rng.shuffle(sorted(images))
        self.videos = rng.shuffle(sorted(videos))
        self.image_count, self.video_count = len(self.images), len(self.videos)

    def choose_one(self) -> str:
        if not self.images:
            raise RuntimeError("No more images found, add more to the photos folder")
        return self.images.pop(0)

    def choose(self, n: int) -> list[str]:
        if n > len(self.images):
            raise RuntimeError("No more images found, add more to the photos folder")
        chosen, self.images = self.images[:n], self.images[n:]
        return chosen

    def choose_video(self) -> str | None:
        return self.videos.pop(0) if self.videos else None

    def print_usage(self) -> None:
        log(
            f"Used {self.image_count - len(self.images)}/{self.image_count} images and "
            f"{self.video_count - len(self.videos)}/{self.video_count} videos"
        )


# ------------------------------------------------------------------ Photo frame

FRAMED = ff.template("""
<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{rx}" ry="{ry}"
      stroke="{stroke}" stroke-width="{stroke_width}" opacity="{opacity}"
      transform="{transform}" transform-origin="{origin}" fill="none" />
<image href="{href}" x="{x}" y="{y}" width="{width}" height="{height}" opacity="{opacity}"
       transform="{transform}" transform-origin="{origin}" />
""")
IDENTITY = ff.Transform()


def framed(image, x, y, width, height, *, stroke_width=24, transform=IDENTITY, origin=""):
    """`ImageData::render_framed` with a `PhotoFrame`."""
    return FRAMED(
        x=x,
        y=y,
        width=width,
        height=height,
        rx=0,
        ry=0,
        stroke=ff.Color.WHITE,
        stroke_width=stroke_width,
        opacity=1.0,
        transform=transform,
        origin=origin,
        href=image,
    )


def fit(image, size: np.float32) -> tuple[np.float32, np.float32]:
    aspect = F(image.width) / F(image.height)
    if aspect > 1.0:
        return size, size / aspect
    return size * aspect, size


SHADOW = """
<filter id="{id}" x="-20%" y="-20%" width="140%" height="140%">
    <feGaussianBlur in="SourceAlpha" stdDeviation="{blur}" />
    <feOffset dx="{d}" dy="{d}" result="offsetblur" />
    <feComponentTransfer><feFuncA type="linear" slope="0.3" /></feComponentTransfer>
    <feMerge><feMergeNode /><feMergeNode in="SourceGraphic" /></feMerge>
</filter>
"""
PHOTO_SHADOW = SHADOW.format(id="photo-shadow", blur=8, d=3)
SHADOWED = ff.template(
    PHOTO_SHADOW
    + '<g transform="{transform}" filter="url(#photo-shadow)" opacity="{opacity}">{photo}</g>'
)

# ------------------------------------------------------------------ Scenes

START_TEXT_FAMILY = "Space Grotesk"


class StartScene:
    overlap = 3.0

    def __init__(self, text: str, duration: np.float32):
        self.text, self.duration = text, float(duration)
        self.fade = ff.timeline(
            ((float(duration - F(3.0)), float(duration)), 1.0, 0.0, ff.Easing.EASE_OUT)
        )

    def render_frame(self, frame, ctx):
        layout = frame.text_layout(
            ctx,
            self.text,
            width=1600,
            family=START_TEXT_FAMILY,
            size=124,
            line_height=1.1,
            x="50%",
            y="30%",
            fill="#fff",
            text_anchor="middle",
            dominant_baseline="middle",
            opacity=frame.animate(self.fade),
        )
        return layout.svgr() if layout is not None else ff.Svgr.empty()


FINAL = ff.template(
    f"""
<svg y="0" x="{{x}}" width="{{width}}" viewBox="-20 0 483 115" xmlns="http://www.w3.org/2000/svg">
    <path stroke-dasharray="900 900" stroke-dashoffset="{{offset}}" stroke-linecap="round"
          fill-rule="evenodd" fill="transparent" stroke="#fff" stroke-width="9"
          d="{(HERE / "final_path.txt").read_text()}" />
</svg>
"""
)


class FinalScene:
    def __init__(self, duration: np.float32):
        self.duration = float(duration + F(10.0))
        self.animation = ff.timeline(((0.0, float(duration)), 3000.0, 0.0, ff.Easing.LINEAR))

    def render_frame(self, frame, ctx):
        width = F(443.0 * 2.0)
        return FINAL(
            x=float(F(WIDTH) / F(2.0) - width / F(2.0)),
            width=float(width),
            offset=frame.animate(self.animation),
        )


class SinglePhotoFloat:
    overlap = 0.4
    SIZE = F(950.0)

    def __init__(self, photo: str, tempo: np.float32, rng: Rng):
        self.photo = photo
        horizontal = rng.bool(0.5)
        entry, center, exit_ = tempo * F(3.0), tempo * F(4.0), tempo * F(3.0)
        total = entry + center + exit_
        exit_start = entry + center
        w, h = F(WIDTH), F(HEIGHT)
        cx, cy = w / F(2.0), h / F(2.0)
        if horizontal:
            sx, sy, ex, ey = w + F(200.0), cy, -self.SIZE, cy
        else:
            sx, sy, ex, ey = cx, h + F(200.0), cx, -self.SIZE
        main = (cx + rng.f32(-30.0, 30.0), cy + rng.f32(-30.0, 30.0))
        main_scale = rng.r.range(1.0, 1.3, "f64", True)

        def t(x, y, scale):
            return ff.Transform(translate=(float(x), float(y)), scale=scale)

        exit_scale = rng.f64(0.7, 0.9)
        self.transform = ff.timeline(
            ((0.0, float(entry)), t(sx, sy, 0.9), t(cx, cy, 1.0), ff.Easing.EASE_OUT),
            (
                (float(entry), float(exit_start)),
                t(cx, cy, 1.0),
                t(*main, main_scale),
                ff.Easing.EASE_IN_OUT,
            ),
            (
                (float(exit_start), float(total)),
                t(*main, main_scale),
                t(ex, ey, exit_scale),
                ff.Easing.EASE_IN,
            ),
        )
        main_rotate = rng.f32(-2.0, 2.0)
        mid = entry + center * F(0.5)
        self.rotation = ff.timeline(
            ((0.0, float(entry)), float(rng.f32(-5.0, 5.0)), 0.0, ff.Easing.EASE_OUT),
            ((float(entry), float(mid)), 0.0, float(main_rotate), ff.Easing.EASE_IN_OUT),
            ((float(mid), float(exit_start)), float(main_rotate), 1.0, ff.Easing.EASE_IN_OUT),
            ((float(exit_start), float(total)), 1.0, float(rng.f32(-5.0, 5.0)), ff.Easing.EASE_IN),
        )
        self.duration = float(total)

    def render_frame(self, frame, ctx):
        image = ctx.image(self.photo)
        if image is None:
            return ff.Svgr.empty()
        pw, ph = (float(v) for v in fit(image, self.SIZE))
        t = frame.animate(self.transform)
        transform = ff.Transform(
            translate=(t.translate_x - pw / 2.0, t.translate_y - ph / 2.0),
            rotate=float(F(frame.animate(self.rotation))),
            scale=(t.scale_x, t.scale_y),
        )
        return framed(
            image,
            0.0,
            0.0,
            int(pw),
            int(ph),
            stroke_width=48,
            transform=transform,
            origin="center center",
        )


class FibonacciSpiralGallery:
    direction_is_left = False

    def __init__(self, photo: str, tempo: np.float32, rng: Rng):
        self.photo = photo
        self.size = F(rng.int(1200, 1400))
        self.fade_in = tempo * F(rng.int(1, 2))
        self.center = tempo * F(rng.int(2, 3))
        rng.bool(0.5)
        is_left = FibonacciSpiralGallery.direction_is_left
        self.direction = F(1.0) if is_left else F(-1.0)
        FibonacciSpiralGallery.direction_is_left = not is_left
        self.revolutions = rng.f32(1.0, 3.0)
        self.spiral_out = tempo * self.revolutions * PI32
        self.max_radius = rng.f32(350.0, 650.0)
        self.duration = float(self.fade_in + self.center + self.spiral_out)
        self.overlap = float(self.spiral_out * F(0.3))

    def render_frame(self, frame, ctx):
        image = ctx.image(self.photo)
        if image is None:
            return ff.Svgr.empty()
        cx, cy = F(WIDTH / 2), F(HEIGHT / 2)
        now = F(frame.seconds)
        pw, ph = fit(image, self.size)
        opacity = F(1.0)
        if now < self.fade_in:
            progress = now / self.fade_in
            opacity = progress
            transform = ff.Transform(
                translate=(float(cx), float(cy)), scale=0.7 + 0.3 * float(progress)
            )
        elif now < self.fade_in + self.center:
            transform = ff.Transform(translate=(float(cx), float(cy)), scale=1.0)
        else:
            progress = (now - self.fade_in - self.center) / self.spiral_out
            growth = f32_fn(math.pow, progress, F(0.8))
            opacity = F(1.0) - f32_fn(math.pow, progress, F(0.7))
            angle = f32_fn(math.pow, progress, F(0.6))
            theta = self.direction * angle * self.revolutions * F(2.0) * PI32
            b = f32_fn(math.log, PHI) / (F(2.0) * PI32)
            base = f32_fn(math.exp, b * abs(theta))
            max_factor = f32_fn(math.exp, b * self.revolutions * F(2.0) * PI32)
            spiral = self.max_radius * base / max_factor * growth
            blend = f32_fn(math.pow, progress, F(0.3))
            radius = F(0.1) * (F(1.0) - blend) + spiral * blend
            x = cx + radius * f32_fn(math.cos, theta)
            y = cy + radius * f32_fn(math.sin, theta)
            transform = ff.Transform(
                translate=(float(x), float(y)),
                scale=1.0 - 0.9 * float(progress),
                rotate=float(self.direction) * float(progress) * 25.0,
            )
        photo = framed(image, float(-pw / F(2.0)), float(-ph / F(2.0)), int(pw), int(ph))
        return SHADOWED(transform=transform, opacity=float(opacity), photo=photo)


SPIRAL_ITEM = ff.template(
    '<g transform="{transform}" filter="url(#photo-shadow)" opacity="{opacity}">{photo}</g>'
)
SPIRAL = ff.template("<defs>" + PHOTO_SHADOW + "</defs>{items}")


class SpiralHeapGallery:
    overlap = 0.5
    SIZE = F(1000.0)

    def __init__(self, photos: list[str], tempo: np.float32, rng: Rng):
        self.photos = photos
        count = len(photos)
        last_end = F(count - 1) * tempo * F(4.0) + tempo * F(4.0)
        total = last_end + rng.f32(5.0, 8.0)
        w, h = F(1920.0), F(1080.0)
        cx, cy = w / F(2.0), h / F(2.0)
        finals = []
        for i in range(count):
            theta = F(i) * F(0.5) * PI32
            radius = F(60.0) * f32_fn(math.pow, PHI, theta / PI32)
            fx = cx + radius * f32_fn(math.cos, theta)
            fy = cy + radius * f32_fn(math.sin, theta)
            half, margin = self.SIZE / F(2.0), F(50.0)
            fx = min(max(fx, half + margin), w - half - margin)
            fy = min(max(fy, half + margin), h - half - margin)
            finals.append((F(fx), F(fy), theta))
        self.motion, self.rotation, self.opacity = [], [], []
        end = float(total - F(0.5))
        for i, (fx, fy, theta) in enumerate(finals):
            start = F(i) * tempo * F(4.0)
            span = tempo * F(4.0)
            turn = F(math.fmod(float(theta), float(F(2.0) * PI32))) / (F(2.0) * PI32)
            if turn < 0.25:
                sx, sy = cx + rng.f32(-w / F(2.0), w / F(2.0)), F(-200.0)
            elif turn < 0.5:
                sx, sy = w + F(200.0), cy + rng.f32(-h / F(2.0), h / F(2.0))
            elif turn < 0.75:
                sx, sy = cx + rng.f32(-w / F(2.0), w / F(2.0)), h + F(200.0)
            else:
                sx, sy = F(-200.0), cy + rng.f32(-h / F(2.0), h / F(2.0))
            stiffness, mass, damping = rng.f32(30.0, 45.0), rng.f32(4.0, 5.0), rng.f32(20.0, 35.0)
            spring = ff.Easing.spring(float(mass), float(stiffness), float(damping))
            final = (
                float(fx + rng.f32(-10.0, 10.0)),
                float(fy + rng.f32(-10.0, 10.0)),
                float(F(1.0) + rng.f32(0.0, 0.02)),
            )
            out = (
                2000.0 if rng.bool(0.5) else -2000.0,
                2000.0 if rng.bool(0.5) else -2000.0,
                float(rng.f32(0.1, 0.8)),
            )
            settled = (float(fx), float(fy), 1.0)
            s, e = float(start), float(start + span)
            self.motion.append(
                ff.timeline(
                    ((s, e), (float(sx), float(sy), float(F(0.1))), settled, spring),
                    ((e, end), settled, final, ff.Easing.EASE_IN_OUT),
                    ((end, float(total)), final, out, ff.Easing.EASE_IN_OUT),
                )
            )
            initial, settle = rng.f32(-20.0, 20.0), rng.f32(-5.0, 5.0)
            drift = settle + rng.f32(-2.0, 2.0)
            leave_from = settle + rng.f32(-2.0, 2.0)
            leave_to = settle + rng.f32(30.0, 60.0)
            self.rotation.append(
                ff.timeline(
                    ((s, e), float(initial), float(settle), ff.Easing.EASE_OUT),
                    ((e, end), float(settle), float(drift), ff.Easing.EASE_IN_OUT),
                    ((end, float(total)), float(leave_from), float(leave_to), ff.Easing.EASE_IN),
                )
            )
            self.opacity.append(
                ff.timeline(
                    ((s, float(start + tempo * F(0.8))), 0.0, 1.0, ff.Easing.EASE_OUT),
                    ((end, float(total)), 1.0, 0.0, ff.Easing.EASE_IN),
                )
            )
        self.duration = float(total)

    def render_frame(self, frame, ctx):
        items = []
        for index, photo in enumerate(self.photos):
            image = ctx.image(photo)
            if image is None:
                continue
            x, y, scale = frame.animate(self.motion[index])
            transform = ff.Transform(
                translate=(x, y), rotate=frame.animate(self.rotation[index]), scale=float(F(scale))
            )
            pw, ph = fit(image, self.SIZE)
            items.append(
                SPIRAL_ITEM(
                    transform=transform,
                    opacity=frame.animate(self.opacity[index]),
                    photo=framed(image, float(-pw / F(2.0)), float(-ph / F(2.0)), int(pw), int(ph)),
                )
            )
        return SPIRAL(items=ff.Svgr.concat(items))


BORDER, CAPTION, MIN_SIDE = F(14.0), F(60.0), F(450.0)
POLAROID = ff.template(
    "<defs>" + SHADOW.format(id="polaroid-shadow", blur=10, d=5) + "</defs>{items}"
)
POLAROID_ITEM = ff.template("""
<g transform="{transform}" filter="url(#polaroid-shadow)" opacity="{shadow}">
    <rect width="{pw}" height="{ph}" rx="2" ry="2" fill="#ffffff" stroke="#e9e9e9" stroke-width="1" />
    <rect x="{border}" y="{border}" width="{w}" height="{h}" fill="#f0f0f0" />
    <image href="{href}" x="{border}" y="{border}" width="{w}" height="{h}"
           preserveAspectRatio="xMidYMid slice" />
    <rect x="{border}" y="{border}" width="{w}" height="{h}" fill="#ffffff" opacity="{veil}" />
    <text x="{tx}" y="{ty}" text-anchor="middle" dominant-baseline="middle"
          font-family="'Indie Flower', cursive, sans-serif" font-size="44" fill="#333333"
          opacity="{progress}">{year}</text>
</g>
""")
KNOWN_YEARS = {
    "055.jpg": "1996",
    "049.jpg": "2003",
    "024.jpg": "2003",
    "031.jpg": "2003",
    "030.jpg": "2018",
    "042.jpg": "2006",
    "058.jpg": "2001",
    "041.jpg": "",
    "060.jpg": "",
}


class PolaroidDevelopment:
    overlap = 0.3

    def __init__(self, photos: list[str], tempo: np.float32, rng: Rng):
        self.photos = photos
        self.years: dict[str, str] = {}
        count = len(photos)
        total = tempo * F(4.0) * F(count) + tempo * rng.f32(1.0, 2.0)
        w, h = F(WIDTH), F(HEIGHT)
        aw, ah = w * rng.f32(0.90, 1.00, True), h * rng.f32(0.90, 1.00, True)
        ax0 = rng.f32(0.0, max(w - aw, F(0.0)), True)
        ay0 = rng.f32(0.0, max(h - ah, F(0.0)), True)
        ax1, ay1 = ax0 + aw, ay0 + ah
        lw = min(w * rng.f32(0.52, 0.60, True), h * rng.f32(0.62, 0.72, True))
        lh = min(h * rng.f32(0.68, 0.80, True), lw * rng.f32(1.12, 1.24, True))
        margin = max(max(lw, lh) * F(0.15), F(40.0))
        mx, my = lw / F(2.0) + margin, lh / F(2.0) + margin
        x_min, x_max = ax0 + mx, ax1 - mx
        if x_min >= x_max:
            x_min, x_max = mx, w - mx
        if x_min >= x_max:
            x_min, x_max = w * F(0.25), w * F(0.75)
        y_min, y_max = ay0 + my, ay1 - my
        if y_min >= y_max:
            y_min, y_max = my, h - my
        if y_min >= y_max:
            y_min, y_max = h * F(0.25), h * F(0.75)
        min_dist = F(0.40) * max(lw, lh)
        min_dist_sq = min_dist * min_dist
        centers = []
        self.develop, self.position, self.shadow = [], [], []
        blow_out = F(0.5)
        for index in range(count):
            start = F(index) * tempo * F(3.0)
            self.develop.append(
                ff.timeline(
                    ((float(start), float(start + tempo * F(2.0))), 0.0, 1.0, ff.Easing.EASE_OUT)
                )
            )
            attempts, local = 0, min_dist_sq
            while True:
                attempts += 1
                cx, cy = rng.f32(x_min, x_max), rng.f32(y_min, y_max)
                if all(
                    (cx - px) * (cx - px) + (cy - py) * (cy - py) >= local for px, py in centers
                ):
                    break
                if attempts > 48:
                    local = local * F(0.85)
                    attempts = 0
            centers.append((cx, cy))
            tx, ty = cx - lw / F(2.0), cy - lh / F(2.0)
            rotation = rng.f32(-4.0, 4.0)
            last = (
                tx + rng.f32(-10.0, 10.0),
                ty + rng.f32(-10.0, 10.0),
                rotation + rng.f32(-1.0, 1.0),
            )
            gone = (
                -2000.0 if index % 2 == 0 else 2000.0,
                -2000.0 if (index + index // 2) % 2 == 0 else 2000.0,
                float(last[2]),
            )
            placed = (float(tx), float(ty), float(rotation))
            last = tuple(float(v) for v in last)
            drop = (float(start - F(0.5)), float(start + F(0.5)))
            self.position.append(
                ff.timeline(
                    (drop, (float(tx), float(-lh), 0.0), placed, ff.Easing.EASE_OUT),
                    ((drop[1], float(total)), placed, last, ff.Easing.EASE_IN_OUT),
                    ((float(total), float(total + blow_out)), last, gone, ff.Easing.EASE_IN),
                )
            )
            self.shadow.append(ff.timeline((drop, 0.0, 1.0, ff.Easing.EASE_OUT)))
        self.duration = float(total + blow_out)

    def year(self, ctx, photo: str) -> str:
        if photo in KNOWN_YEARS:
            return KNOWN_YEARS[photo]
        if ctx.mode == "editor-timeline-preview":
            return ""
        if photo not in self.years:
            log(f"Fetching EXIF data for photo: {photo}")
            value = ff.exif(ctx, photo, "DateTimeOriginal")
            self.years[photo] = value[:4] if value is not None and len(value) >= 4 else ""
        return self.years[photo]

    def render_frame(self, frame, ctx):
        w, h = F(WIDTH), F(HEIGHT)
        max_w, max_h = max(w * F(0.60), MIN_SIDE), max(h * F(0.80), MIN_SIDE)
        items = []
        for index, photo in enumerate(self.photos):
            image = ctx.image(photo)
            if image is None:
                continue
            year = self.year(ctx, photo)
            aspect = F(image.width) / F(image.height)
            pw = max_w
            ph = pw / aspect
            if ph > max_h:
                ph = max_h
                pw = ph * aspect
            if pw < MIN_SIDE and pw < ph:
                pw = MIN_SIDE
                ph = pw / aspect
            elif ph < MIN_SIDE and ph < pw:
                ph = MIN_SIDE
                pw = ph * aspect
            polaroid_w = pw + BORDER * F(2.0)
            polaroid_h = ph + BORDER + CAPTION
            tx, ty, rotation = frame.animate(self.position[index])
            progress = frame.animate(self.develop[index])
            transform = ff.Transform(
                translate=(tx, ty),
                rotate=(rotation, (float(polaroid_w / F(2.0)), float(polaroid_h / F(2.0)))),
            )
            items.append(
                POLAROID_ITEM(
                    transform=transform,
                    shadow=frame.animate(self.shadow[index]),
                    pw=float(polaroid_w),
                    ph=float(polaroid_h),
                    border=float(BORDER),
                    w=float(pw),
                    h=float(ph),
                    href=image,
                    veil=float(F(1.0) - F(progress)),
                    tx=float(polaroid_w / F(2.0)),
                    ty=float(polaroid_h - CAPTION / F(2.0) + F(5.0)),
                    progress=progress,
                    year=year,
                )
            )
        return POLAROID(items=ff.Svgr.concat(items))


PARALLAX = ff.template("""
<g id="bg_parallax_images" transform="{bg_transform}">{bg}</g>
<g id="main_parallax_images" transform="{main_transform}">{main}</g>
""")
BG_IMAGE = ff.template("""
<image href="{href}" height="{height}" width="{width}" x="{x}" y="{y}"
       transform-origin="center center" transform="{transform}" opacity="{opacity}" />
""")


class ParallaxGridPhotos:
    overlap = 0.3

    def __init__(self, main: list[str], bg: list[str], tempo: np.float32, rng: Rng):
        self.main, self.bg = main, bg
        pause = rng.f32(0.2, 0.3, True)
        enter = tempo * rng.f32(1.5, 2.5, True)
        keys = [((0.0, float(enter - pause)), -1080.0, 0.0, ff.Easing.EASE_OUT)]
        for index in range(len(main)):
            start = F(index) * (tempo * F(4.0)) + pause + enter
            end = F(index + 1) * tempo * F(4.0) - pause
            keys.append(
                (
                    (float(start), float(end)),
                    float(F(index) * F(1080.0)),
                    float(F(index + 1) * F(1080.0)),
                    ff.Easing.EASE_IN_OUT,
                )
            )
        self.main_animation = ff.timeline(*keys)
        bg_end = F(self.main_animation.duration) + rng.f32(0.3, 0.7, True)
        self.bg_animation = ff.timeline(
            ((0.0, float(bg_end)), -1080.0, float(F(len(bg) + 2) * F(400.0)), ff.Easing.LINEAR)
        )
        self.duration = float(F(self.bg_animation.duration) - F(0.5))

    def render_frame(self, frame, ctx):
        bg = []
        for index, photo in enumerate(self.bg):
            image = ctx.image(photo)
            if image is None:
                continue
            ratio = image.height / 350.0
            width = image.width / ratio
            bg.append(
                BG_IMAGE(
                    href=image,
                    height=350.0,
                    width=width,
                    x="75%" if index % 2 == 0 else "25%",
                    y=400 // 3 if index == 0 else index * 400,
                    transform=ff.Transform(translate=(-width / 2.0, 0.0), scale=1.2),
                    opacity=0.85,
                )
            )
        main = []
        for index, photo in enumerate(self.main):
            image = ctx.image(photo)
            if image is None:
                continue
            ratio = F(image.height) / F(800.0)
            width = F(image.width) / ratio
            main.append(
                framed(
                    image,
                    float(F(WIDTH) / F(2.0)),
                    float(F(1080.0) * F(index) + F(140.0)),
                    int(width),
                    800,
                    stroke_width=48,
                    transform=ff.Transform(translate=(float(-width) / 2.0, 0.0)),
                )
            )
        return PARALLAX(
            bg_transform=ff.Transform(translate=(0.0, float(-F(frame.animate(self.bg_animation))))),
            bg=ff.Svgr.concat(bg),
            main_transform=ff.Transform(
                translate=(0.0, float(-F(frame.animate(self.main_animation))))
            ),
            main=ff.Svgr.concat(main),
        )


VIDEO_IMAGE = ff.template(
    '<image x="{x}" y="0" width="{width}" height="1080" href="{href}" opacity="{opacity}" />'
)
PORTRAIT_VIDEO = ff.template("""
<g>
    <defs><filter id="blur-effect"><feGaussianBlur in="SourceGraphic" stdDeviation="30" /></filter></defs>
    <image href="{href}" x="0" y="0" width="1920" height="1080" preserveAspectRatio="xMidYMid slice"
           opacity="{blur_opacity}" filter="url(#blur-effect)" />
    <image id="main-image" y="0" x="{x}" width="{width}" height="1080" href="{href}" opacity="{opacity}" />
</g>
""")


class PixelSingleVideoScene:
    """A video of the photos folder with its own sound."""

    def __init__(self, video: str):
        self.video = video
        self.duration = ff.Duration.from_video(video)
        self.audio = [(video, 0.0, None)]

    def render_frame(self, frame, ctx):
        video_frame = frame.video_frame(ctx, self.video)
        if video_frame is None:
            return ff.Svgr.empty()
        length = video_frame.stream_duration
        opacity = frame.animate(
            ff.timeline(
                ((0.0, 0.5), 0.0, 1.0, ff.Easing.EASE_IN),
                ((length - 0.5, length), 1.0, 0.0, ff.Easing.EASE_OUT),
            )
        )
        image = video_frame.image
        scaled = video_frame.width / (video_frame.height / 1080.0)
        x = (1920.0 - scaled) / 2.0
        if video_frame.height > video_frame.width:
            return PORTRAIT_VIDEO(
                href=image, blur_opacity=opacity * 0.7, x=x, width=scaled, opacity=opacity
            )
        return VIDEO_IMAGE(x=x, width=scaled, href=image, opacity=opacity)


# ------------------------------------------------------------------ Bokeh background


class Bokeh:
    __slots__ = ("ax", "ay", "cx", "cy", "fill", "filter", "heart", "opacity", "r")


GRADIENTS = ("url(#bokeh-gold-bright)", "url(#bokeh-gold-medium)", "url(#bokeh-gold-soft)")
FILTERS = ("url(#bokeh-blur-large)", "url(#bokeh-blur-medium)", "url(#bokeh-blur-small)")


def heart_point(index: int, total: int) -> tuple[float, float]:
    t = (index / total) * 2.0 * math.pi
    x = 16.0 * math.sin(t) ** 3
    y = -(
        13.0 * math.cos(t) - 5.0 * math.cos(2.0 * t) - 2.0 * math.cos(3.0 * t) - math.cos(4.0 * t)
    )
    scale = 1.0 * (HEIGHT / 50.0)
    return WIDTH / 2.0 + x * scale, HEIGHT / 2.0 + y * scale


def bokeh_circle(rng: Rng, cx, cy, r, opacity, heart) -> Bokeh:
    circle = Bokeh()
    size_factor = 1.0 - min(r / 40.0, 0.7)
    circle.fill = GRADIENTS[rng.int(0, 3, kind="usize")]
    circle.filter = FILTERS[0 if r > 25.0 else 1 if r > 15.0 else 2]
    circle.cx, circle.cy, circle.r, circle.opacity, circle.heart = cx, cy, r, opacity, heart
    circle.ax = rng.f64(-1.5, 1.5) * size_factor
    circle.ay = rng.f64(-1.5, 1.5) * size_factor
    return circle


def generate_bokeh(rng: Rng) -> list[Bokeh]:
    count = rng.int(120, 140, kind="usize")
    width, height, center_y, amplitude = 1920.0, 1080.0, 540.0, 250.0
    main_count = count * 6 // 10
    secondary_count = count * 3 // 10
    random_count = count - main_count - secondary_count
    circles = []
    for i in range(main_count):
        x = width * (i / main_count)
        sine = amplitude * math.sin(x / width * 2.0 * math.pi * 1.3)
        deviation = rng.f64(-amplitude * 0.3, amplitude * 0.3)
        jitter = width / main_count * 0.3
        xj = max(min(x + rng.f64(-jitter, jitter), width - 10.0), 10.0)
        y = max(min(center_y + sine + deviation, height - 10.0), 10.0)
        position = abs(sine / amplitude)
        if position < 0.3:
            r = rng.f64(20.0, 35.0)
        elif position < 0.7:
            r = rng.f64(12.0, 25.0)
        else:
            r = rng.f64(5.0, 15.0)
        if r > 25.0:
            opacity = rng.f64(0.5, 0.7)
        elif r > 15.0:
            opacity = rng.f64(0.4, 0.6)
        else:
            opacity = rng.f64(0.3, 0.5)
        circles.append(bokeh_circle(rng, xj, y, r, opacity, heart_point(i, count)))
    for i in range(secondary_count):
        x = width * (i / secondary_count) + width / (2.0 * secondary_count)
        sine = amplitude * 0.8 * math.sin(x / width * 2.0 * math.pi * 2.0 + 0.5)
        deviation = rng.f64(-amplitude * 0.6, amplitude * 0.6)
        jitter = width / secondary_count * 0.4
        xj = max(min(x + rng.f64(-jitter, jitter), width - 10.0), 10.0)
        y = max(min(center_y + sine + deviation, height - 10.0), 10.0)
        r = rng.f64(3.0, 20.0)
        opacity = rng.f64(0.2, 0.5)
        circles.append(bokeh_circle(rng, xj, y, r, opacity, heart_point(i + main_count, count)))
    for i in range(random_count):
        x = rng.f64(10.0, width - 10.0)
        y = rng.f64(10.0, height - 10.0)
        roll = rng.f64(0.0, 1.0)
        if roll > 0.9:
            r = rng.f64(20.0, 30.0)
        elif roll > 0.7:
            r = rng.f64(10.0, 20.0)
        else:
            r = rng.f64(3.0, 10.0)
        opacity = rng.f64(0.2, 0.5)
        heart = heart_point(i + main_count + secondary_count, count)
        circles.append(bokeh_circle(rng, x, y, r, opacity, heart))
    return circles


def loop_segments(keys):
    """An f64 `animate_loop` timeline: `(segment, progress)` pairs in f32, and the f64 values."""
    pairs = []
    for index, key in enumerate(keys):
        at, *_ = key
        pairs.append((at, (float(index), 0.0), (float(index), 1.0), ff.Easing.LINEAR))
    return ff.timeline(*pairs), [(a, b) for _, a, b in keys]


DEVIATION_1 = loop_segments(
    [
        (0.0, 0.0, 20.0),
        (2.8, 20.0, 0.0),
        (5.3, 0.0, -20.0),
        (7.9, -20.0, 0.0),
        (10.4, 0.0, 20.0),
        (13.1, 20.0, -20.0),
        (15.7, -20.0, 0.0),
        (18.2, 0.0, 20.0),
        (20.9, 20.0, 0.0),
        (23.5, 0.0, -20.0),
        ((26.1, 28.7), -20.0, 0.0),
    ]
)
DEVIATION_2 = loop_segments(
    [
        (0.0, 0.0, 20.0),
        (2.3, 20.0, 0.0),
        (4.9, 0.0, -20.0),
        (7.2, -20.0, 0.0),
        (9.8, 0.0, 20.0),
        (12.1, 20.0, -20.0),
        (14.7, -20.0, 0.0),
        (17.3, 0.0, 20.0),
        (19.6, 20.0, 0.0),
        (22.2, 0.0, -20.0),
        (24.5, -20.0, 0.0),
        (27.1, 0.0, 20.0),
        ((29.8, 32.0), 20.0, 0.0),
    ]
)


def deviation(frame, timeline) -> float:
    animation, values = timeline
    index, progress = frame.animate_loop(animation)
    start, end = values[int(index)]
    return start + (end - start) * progress


HEART = ff.AnimationRuntime(3.0, ff.Easing.EASE_IN_OUT)
CIRCLE = ff.template(
    '<circle cx="{cx}" cy="{cy}" r="{r}" opacity="{opacity}" fill="{fill}" filter="{filter}" '
    'transform="{transform}" />'
)
GRADIENT = '<radialGradient id="{}" cx="50%" cy="50%" r="50%" fx="40%" fy="40%">' + (
    '<stop offset="0%" stop-color="{}" /><stop offset="70%" stop-color="{}" />'
    '<stop offset="100%" stop-color="{}" /></radialGradient>'
)
BLUR = (
    '<filter id="bokeh-blur-{}" x="-50%" y="-50%" width="200%" height="200%">'
    '<feGaussianBlur in="SourceGraphic" stdDeviation="{}" /></filter>'
)
VIDEO = ff.template(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080" width="{width}" height="{height}">'
    '<defs><linearGradient id="bg-gradient" x1="0%" y1="0%" x2="100%" y2="100%">'
    '<stop offset="0%" stop-color="#000000" /><stop offset="100%" stop-color="#050505" />'
    "</linearGradient>"
    + BLUR.format("large", 8)
    + BLUR.format("medium", 5)
    + BLUR.format("small", 2)
    + GRADIENT.format("bokeh-gold-bright", "#ffffff", "#f5f0e0", "#e1c78c")
    + GRADIENT.format("bokeh-gold-medium", "#f8f5e8", "#e8dfc0", "#c0b090")
    + GRADIENT.format("bokeh-gold-soft", "#f0ebd8", "#d8cba8", "#a89870")
    + '</defs><rect width="1920" height="1080" fill="url(#bg-gradient)" />'
    '<g id="circles">{circles}</g>{scenes}</svg>'
)

# ------------------------------------------------------------------ Video


def scene_length(scene) -> np.float32 | None:
    """The time a scene adds; `None` for a video scene, whose length the music media lacks."""
    if isinstance(scene, PixelSingleVideoScene):
        return None
    return F(scene.duration) - F(getattr(scene, "overlap", 0.0))


class PixelVideo:
    fps = 30
    width = WIDTH
    height = HEIGHT

    def __init__(self, song: str, text: str, rng: Rng, photos: RandomPhotos):
        self.bokeh = generate_bokeh(rng)
        total, tempo = SONGS[song]
        self.scenes = self.randomize(total, tempo, rng, text, photos)
        photos.print_usage()
        self.total = total
        self.duration = float(total)
        self.audio = [(song, 6.0, None)]
        self.heart_at = float(max(total - F(6.0), F(0.0)))

    @staticmethod
    def randomize(total, tempo, rng: Rng, text: str, photos: RandomPhotos) -> list:
        current = tempo * F(rng.int(4, 5, inclusive=True))
        scenes = [StartScene(text, current)]
        current = current - F(3.0)
        while total - current > 10.0:
            chance = rng.int(0, 50 if total - current > 20.0 else 20)
            if chance < 10:
                scene = SinglePhotoFloat(photos.choose_one(), tempo, rng)
            elif chance < 20:
                scene = FibonacciSpiralGallery(photos.choose_one(), tempo, rng)
            elif chance < 25:
                scene = PolaroidDevelopment(photos.choose(rng.int(4, 8, True, "usize")), tempo, rng)
            elif chance < 30:
                scene = SpiralHeapGallery(photos.choose(rng.int(6, 10, True, "usize")), tempo, rng)
            elif chance < 40:
                main = photos.choose(rng.int(2, 4, True, "usize"))
                scene = ParallaxGridPhotos(main, photos.choose(len(main) * 3), tempo, rng)
            else:
                video = photos.choose_video()
                if video is None:
                    continue
                scene = PixelSingleVideoScene(video)
            length = scene_length(scene)
            if length is None:
                log("No duration found for scene, skipping")
                continue
            if current + length < total - F(3.0):
                scenes.append(scene)
                current = current + length
        scenes.append(FinalScene(total - current))
        return scenes

    def render_frame(self, frame, ctx):
        d1, d2 = deviation(frame, DEVIATION_1), deviation(frame, DEVIATION_2)
        p = HEART.animate(frame, self.heart_at, 0.0, 1.0)
        circles = []
        for index, c in enumerate(self.bokeh):
            d = d1 if index % 2 == 0 else d2
            hx, hy = c.heart
            circles.append(
                CIRCLE(
                    cx=c.cx + (hx - c.cx) * p,
                    cy=c.cy + (hy - c.cy) * p,
                    r=c.r,
                    opacity=c.opacity,
                    fill=c.fill,
                    filter=c.filter,
                    transform=ff.Transform(translate=(d * c.ax, d * c.ay)),
                )
            )
        return VIDEO(
            width=ctx.width,
            height=ctx.height,
            circles=ff.Svgr.concat(circles),
            scenes=ctx.render_scenes(frame),
        )


DEFAULT_TEXT = (
    "They say dogs live shorter lives because they already know how to love unconditionally"
)


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-e", "--enter-text", default=DEFAULT_TEXT)
    parser.add_argument("-s", "--song", help="Song file. Without it the seed picks one.")
    parser.add_argument("--seed", type=int, default=48)
    args, rest = parser.parse_known_args()
    media = ff.Media(
        _media.folder("pixel-memory"), _media.folder("pixel-memory", "photos"), mono=True
    )
    rng = Rng(args.seed)
    photos = RandomPhotos(rng, media.images, media.videos)
    # Rust picks from the keys of a HashMap, whose order changes per run; this order is fixed.
    song = args.song or rng.choose(list(SONGS))
    video = PixelVideo(song, args.enter_text, rng, photos)
    return ff.cli(
        video,
        [sys.argv[0], *rest],
        media=media,
        codec_params={
            "crf": "23",
            "preset": "slower",
            "profile:v": "high",
            "level:v": "5.1",
            "g": "24",
            "sc_threshold": "0",
        },
        qmin=0,
        qmax=69,
        cache_capacity=300,
    )


if __name__ == "__main__":
    sys.exit(main())
