"""Port of fframes/examples/fframes-intro: a 128 second introduction to fframes, made with fframes.

Everything sits on the beat grid of the soundtrack (see _fframes_intro_ui.py). Needs the media of
fframes/examples/fframes-intro (fonts, images, music, sound effects and clips).

python examples/fframes_intro.py timeline
python examples/fframes_intro.py render -o fframes-intro.mp4
"""

import math
import subprocess
import sys

import _fframes_intro_ui
import _media
import fframes as ff
import numpy as np
import tomllib
from _fframes_intro_ui import (
    BEAT,
    BG,
    BONE,
    COND,
    DISPLAY,
    EMBER,
    FPS,
    GREY,
    INK,
    ORANGE,
    PAPER,
    SERIF,
    TOTAL_SECONDS,
    F,
    Slam,
    T,
    beat_time,
    callout,
    corners,
    cubic_in_out,
    exp32,
    expo_in,
    expo_out,
    fract,
    gbeat,
    gsec,
    hash32,
    hash_array,
    label,
    lerp,
    letters,
    measure,
    prog,
    pulse,
    quart_out,
    rem_euclid,
    s32,
    snap,
    soft,
    span_frames,
    spring,
    text,
    thousands,
    timecode,
    usize,
)  # fmt: skip

EXAMPLE = "fframes-intro"
SOURCE = _media.ROOT / "examples" / EXAMPLE
TAU = F(math.tau)
FRAC_PI_2 = F(math.pi / 2)
GROUP = T("<g>{content}</g>")
FULL_IMAGE = T('<image href="{href}" x="0" y="0" width="1920" height="1080" />')
IMAGE = T('<image href="{href}" x="{x}" y="{y}" width="{width}" height="{height}" />')


def round_u(x) -> int:
    """Rust `x.round() as u64` for x >= 0."""
    return usize(math.floor(float(x) + 0.5))


sin_cos32 = _fframes_intro_ui.sin_cos32


def powf(x, y):
    """Rust `f32::powf`."""
    return F(_fframes_intro_ui._libm.powf(F(x), F(y)))


def f(x) -> float:
    return float(x)


# --- shaders, compiled once by the Skia renderer


def shader_source(name: str) -> str:
    return (SOURCE / "src" / "shaders" / name).read_text()


TUNNEL_SOURCE = shader_source("tunnel.sksl")
GRAIN = ff.Shader.sksl(shader_source("grain.sksl"))
CONTOUR = ff.Shader.sksl(shader_source("contour.sksl"))
TUNNEL = ff.Shader.sksl(TUNNEL_SOURCE)
KEY = ff.Shader.sksl(shader_source("key.sksl"))
DEVELOP = ff.Shader.sksl(shader_source("develop.sksl"))
GRID = ff.Shader.sksl(shader_source("grid.sksl"))
INK_GREY = ff.Color.hex("#8a857c")
GRID_INK = ff.Color.hex("#6f6a63")
HOT = ff.Color.hex(ORANGE)
BONE_COLOR = ff.Color.hex(BONE)


def contour(frame, well, depth, density, bright):
    return CONTOUR.draw(
        frame,
        {"uWell": (f(well[0]), f(well[1])), "uDepth": f(depth), "uDensity": f(density),
         "uBright": f(bright), "uInk": INK_GREY, "uHot": HOT},
    )  # fmt: skip


def grid(frame, speed, horizon, bright):
    return GRID.draw(
        frame,
        {"uSpeed": f(speed), "uHorizon": f(horizon), "uBright": f(bright), "uInk": GRID_INK,
         "uHot": HOT},
    )  # fmt: skip


# --- facts: every measured number that appears on screen

RELEASE_LABEL = "v" + tomllib.loads((SOURCE / "Cargo.toml").read_text())["package"]["version"]
LINES_OF_RUST = 89_372
FRAMES = 7_650
RENDER_SECONDS = F(79.6)
BENCH_REMOTION_S = F(121.132_1)
BENCH_FFRAMES_S = F(4.074_223)
BENCH_FFRAMES_CPU_S = F(69.740_39)
BENCH_REMOTION_LABEL = "REMOTION 4.0"
BENCH_FFRAMES_LABEL = "FFRAMES · SKIA ON METAL"
BENCH_NOTE = "M5 MAX · REMOTION 4.0.529 · SERIAL · H.264 MP4 · MEDIANS"


class BeatScene:
    """A scene placed on the beat grid; START/END None stand for the start or end of the video."""

    START: float | None = None
    END: float | None = None

    def __init__(self):
        self.name = type(self).__name__
        self.duration = ff.Duration.frames(span_frames(self.START, self.END))

    def lb(self, frame):
        """Beat inside the scene (0 on its first downbeat)."""
        return gbeat(frame) - F(self.START or 0.0)


# --- 00 / PROMPT: the prompt that asked for this video, typed into a coding agent

PROMPT = "make an intro video for fframes. make it stunning."
OUTPUT = (
    (True, "Explored skills/fframes-video"),
    (False, "Read SKILL.md, design.md, audio.md"),
    (True, "Edited src/lib.rs"),
    (True, "Ran cargo run --release -- timeline"),
    (True, "Ran cargo run --release -- strip all -n 24"),
)
CALL_MARKER = T('<circle cx="172" cy="{cy}" r="7" fill="{ORANGE}" />')
READ_MARKER = T('<path d="{d}" fill="none" stroke="{GREY}" stroke-width="2" />')
OUTPUT_LINE = T("""
<g opacity="{o}">
    {marker}
    <text x="{x}" y="{y}" font-family="{MONO}" font-size="28" fill="#b9b4ab">{text}</text>
</g>
""")
PROMPT_FRAME = T("""
<g>
    <image href="{bg}" x="0" y="0" width="1920" height="1080" />
    <g transform="{lift}">
        <text x="160" y="366" font-family="{MONO}" font-weight="500" font-size="22" letter-spacing="2" fill="{GREY}">{agent}</text>
        <text x="1760" y="366" text-anchor="end" font-family="{MONO}" font-weight="500" font-size="28" letter-spacing="2" fill="{GREY}">{release}</text>
        <rect x="140" y="400" width="1640" height="270" rx="18" fill="#0f0e0d" fill-opacity="0.85"
              stroke="{stroke}" stroke-width="2" />
        <text x="180" y="522" font-family="{MONO}" font-weight="600" font-size="64" fill="{ORANGE}">›</text>
        <text x="240" y="522" font-family="{MONO}" font-weight="500" font-size="64" fill="{BONE}">{line1}</text>
        <text x="240" y="612" font-family="{MONO}" font-weight="500" font-size="64" fill="{ORANGE}">{line2}</text>
        <rect x="{caret_x}" y="{caret_y}" width="32" height="64" fill="{ORANGE}" opacity="{caret}" />
    </g>
    <g transform="translate(0 -40)">{lines}</g>
</g>
""")


class PromptScene(BeatScene):
    START, END = None, 0.0

    def render_frame(self, frame, ctx):
        t = gsec(frame)
        enter_at = beat_time(-1.0)
        chars = len(PROMPT)
        typed = min(usize(F(8.0) + (t - F(0.02)) * F(44.0)), chars)
        shown = PROMPT[:typed]
        done = typed >= chars
        caret_on = not done or fract(t * F(3.0)) < 0.55
        split = PROMPT.find(". ") + 2
        adv = F(64.0) * F(0.6)
        on_second = typed > split
        caret_x = F(240.0) + F(typed - split if on_second else typed) * adv
        caret_y = F(612.0) if on_second else F(522.0)
        after = t - enter_at
        lift = -expo_out(after / F(0.25)) * F(200.0) if after > 0.0 else F(0.0)
        enter_flash = exp32(-after * F(9.0)) if after > 0.0 else F(0.0)
        lines = []
        for i, (call, line) in enumerate(OUTPUT):
            at = enter_at + F(0.05) + F(i) * F(0.07)
            y = F(560.0) + F(i) * F(44.0)
            if call:
                marker = CALL_MARKER(cy=f(y - F(9.0)))
            else:
                marker = READ_MARKER(d=f"M204 {s32(y - F(26.0))} V{s32(y - F(9.0))} H222")
            lines.append(
                OUTPUT_LINE(
                    o=f(prog(t, at, at + F(0.06))),
                    marker=marker,
                    x=200.0 if call else 236.0,
                    y=f(y),
                    text=text(line),
                )
            )
        bg = contour(frame, (0.74, 0.62), 0.6, 16.0, F(0.35) + enter_flash * F(0.4))
        return PROMPT_FRAME(
            bg=bg, lift=f"translate(0 {s32(lift)})", agent=text("CODEX  ·  ~/dev/fframes"),
            release=text(RELEASE_LABEL), stroke=ORANGE if after > 0.0 else "#4a4640",
            line1=text(shown[:split]), line2=text(shown[split:]),
            caret_x=f(caret_x + F(4.0)), caret_y=f(caret_y - F(50.0)),
            caret=1.0 if caret_on and after <= 0.0 else 0.0, lines=lines,
        )  # fmt: skip


# --- 01 / ORIGIN: the first commit, five years of history, and the numbers behind it


def read_commits():
    """`git log` of the fframes repository, like the build script of the Rust example."""
    done = subprocess.run(
        ["git", "log", "--reverse", "--format=%h|%ad|%s", "--date=short"],
        cwd=_media.ROOT, capture_output=True, check=False,
    )  # fmt: skip
    if done.returncode != 0:
        print("git log failed, the origin scene will have no commits", file=sys.stderr)
        return []
    commits = []
    for line in done.stdout.decode("utf-8", "replace").split("\n"):
        parts = line.split("|", 2)
        if len(parts) == 3:
            commits.append(tuple(parts))
    return commits


def day_number(date: str) -> int:
    """Days since 1970-01-01 of a `YYYY-MM-DD` date (Howard Hinnant's algorithm)."""
    parts = [int(p) if p.isdigit() else 1 for p in date.split("-")] + [1970, 1, 1]
    y, m, d = parts[0], parts[1], parts[2]
    y = y - 1 if m <= 2 else y
    era = y // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146_097 + doe - 719_468


MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


def month_label(date: str) -> str:
    month = int(date[5:7]) if date[5:7].isdigit() else 1
    return f"{MONTHS[min(month - 1, 11)]} {date[:4]}"


COMMITS = read_commits()
FIRST_DATE = COMMITS[0][1] if COMMITS else "2021-09-19"
LAST_DATE = COMMITS[-1][1] if COMMITS else FIRST_DATE
HISTORY_COUNT = len(COMMITS)
HISTORY_DAYS = day_number(LAST_DATE) - day_number(FIRST_DATE)
HISTORY_SINCE, HISTORY_UNTIL = month_label(FIRST_DATE), month_label(LAST_DATE)

ORIGIN = T('<g><image href="{bg}" x="0" y="0" width="1920" height="1080" />{content}</g>')
FIRST_COMMIT = T("""
<g opacity="{opacity}" transform="{transform}">
    <text x="160" y="220" font-family="{MONO}" font-weight="500" font-size="30" fill="{GREY}">{command}</text>
    {year}
    <rect x="160" y="740" width="{underline}" height="10" fill="{ORANGE}" />
    <g opacity="{meta}">
        <text x="160" y="826" font-family="{MONO}" font-weight="600" font-size="36" fill="{ORANGE}">{hash}</text>
        <text x="{date_x}" y="826" font-family="{MONO}" font-weight="500" font-size="36" fill="{BONE}">{date_and_author}</text>
        <text x="1030" y="832" font-family="{SERIF}" font-style="italic" font-size="64" fill="{ORANGE}">{message}</text>
    </g>
    {first}
    {ago}
    {title}
</g>
""")
TITLE_BLOCK = T("""
<g opacity="{o}" font-family="{MONO}" font-size="18" letter-spacing="1.5" fill="{BONE}">
    <rect x="1290" y="800" width="470" height="150" fill="#0b0b0b" fill-opacity="0.7" stroke="{GREY}" stroke-width="1.5" />
    <path d="M1290 850 H1760 M1290 900 H1760 M1400 800 V950 M1600 850 V950" stroke="{GREY}" stroke-width="1.5" />
    <text x="1306" y="832" fill="{GREY}">TITLE</text>
    <text x="1416" y="832">FFRAMES — PROOF OF CONCEPT</text>
    <text x="1306" y="882" fill="{GREY}">DRAWN</text>
    <text x="1416" y="882">dmtrKovalenko</text>
    <text x="1616" y="882" fill="{GREY}">REV 1</text>
    <text x="1306" y="932" fill="{GREY}">SHEET</text>
    <text x="1416" y="932">{sheets}</text>
    <text x="1616" y="932" fill="{ORANGE}">{date}</text>
</g>
""")
HISTORY_ROW = T("""
<g opacity="{o}">
    <text x="160" y="{y}" font-family="{MONO}" font-weight="600" font-size="26" fill="{hash_fill}">{hash}</text>
    <text x="310" y="{y}" font-family="{MONO}" font-weight="500" font-size="26" fill="{GREY}">{date}</text>
    <text x="510" y="{y}" font-family="{MONO}" font-weight="500" font-size="26" fill="{text_fill}">{msg}</text>
</g>
""")
HISTORY = T("""
<g opacity="{opacity}" transform="{transform}">
    <rect x="140" y="{band_y}" width="1060" height="48" fill="{ORANGE}" fill-opacity="0.12" />
    <rect x="140" y="{band_y}" width="4" height="48" fill="{ORANGE}" />
    {rows}
    <text x="1770" y="600" text-anchor="end" font-family="{DISPLAY}" font-size="300" letter-spacing="-10" fill="{ORANGE}">{year}</text>
    <text x="1770" y="680" text-anchor="end" font-family="{MONO}" font-weight="500" font-size="36" fill="{BONE}">{count}</text>
    <text x="1770" y="730" text-anchor="end" font-family="{MONO}" font-weight="500" font-size="26" fill="{GREY}">{date}</text>
</g>
""")
STAT = T("""
<g opacity="{opacity}">
    <g transform="{transform}">
        <text x="0" y="640" font-family="{DISPLAY}" font-size="400" letter-spacing="-10" fill="{BONE}">{shown}</text>
        <g transform="{unit_transform}" opacity="{unit_opacity}">
            <text x="0" y="640" font-family="{DISPLAY}" font-size="110" letter-spacing="-3" fill="{ORANGE}">{unit}</text>
        </g>
        <rect x="4" y="{rule_y}" width="{rule_w}" height="4" fill="{ORANGE}" />
        <text x="4" y="{caption_y}" font-family="{MONO}" font-weight="500" font-size="30" letter-spacing="3" fill="{BONE}" opacity="{cap}">{caption}</text>
    </g>
</g>
""")
ONE_IDEA = T("""
<g opacity="{opacity}">
    <text x="160" y="330" font-family="{MONO}" font-weight="600" font-size="34" letter-spacing="6" fill="{ORANGE}" opacity="{a}">ONE IDEA</text>
    {video}
    {f}
</g>
""")


class OriginScene(BeatScene):
    START, END = 0.0, 32.0

    def render_frame(self, frame, ctx):
        lb = self.lb(frame)
        bg = contour(frame, (F(0.7) - prog(lb, 0.0, 32.0) * F(0.25), 0.58), 0.8, 18.0, 0.42)
        if lb < 8.0:
            content = self.first_commit(frame, ctx, lb)
        elif lb < 16.0:
            content = self.history(lb - F(8.0))
        else:
            content = self.stats(frame, ctx, lb - F(16.0))
        return ORIGIN(bg=bg, content=content)

    @staticmethod
    def first_commit(frame, ctx, lb):
        """Beats 0-8: the year of the first commit, one digit per beat, then the commit."""
        if not COMMITS:
            return None
        hash_, date, message = COMMITS[0]
        exit_ = expo_in(prog(lb, 7.6, 8.0))
        command = "$ git log --reverse | head -1"
        typed = usize((lb / F(0.8)) * F(len(command)))
        command = command[: min(typed, len(command))]

        def digit(i):
            s = snap(lb - F(i))
            return (
                F(0.0),
                (F(1.0) - s) * F(160.0),
                prog(lb, i, F(i) + F(0.15)),
                F(0.85) + F(0.15) * s,
            )

        year = letters(
            frame, ctx, 150.0, 690.0, date[:4] or "2021", DISPLAY, 440, 400, BONE, -8.0, digit
        )
        hash_w = F(7.0) * F(36.0) * F(0.6)
        return FIRST_COMMIT(
            opacity=f(F(1.0) - exit_), transform=f"translate(0 {s32(-exit_ * F(120.0))})",
            command=text(command), year=year,
            underline=f(max(quart_out(prog(lb, 3.0, 4.0)) * F(1120.0), F(0.5))),
            meta=f(prog(lb, 4.0, 4.4)), hash=text(hash_), date_x=f(F(160.0) + hash_w + F(30.0)),
            date_and_author=text(f"{date}   Dmitriy Kovalenko"), message=text(f"“{message}”"),
            first=callout(F(160.0) + hash_w / F(2.0), 842.0, F(160.0) + hash_w / F(2.0), 980.0,
                          "FIRST COMMIT", ORANGE, prog(lb, 5.0, 5.8)),
            ago=callout(1270.0, 520.0, 1420.0, 360.0, f"{HISTORY_DAYS // 365} YEARS AGO", BONE,
                        prog(lb, 5.5, 6.3)),
            title=title_block(date, prog(lb, 6.0, 6.4)),
        )  # fmt: skip

    @staticmethod
    def history(lb):
        """Beats 8-16: every commit scrolls past, accelerating, the year flips."""
        n = len(COMMITS)
        if n == 0:
            return None
        enter = expo_out(prog(lb, 0.0, 0.5))
        exit_ = expo_in(prog(lb, 7.6, 8.0))
        pos = cubic_in_out(prog(lb, 0.3, 7.4)) * F(n - 1)
        current = round_u(pos)
        line_h, center_y = F(44.0), F(560.0)
        first = math.floor(pos) - 11
        rows = []
        for i in range(max(first, 0), min(first + 24, n)):
            hash_, date, message = COMMITS[i]
            y = center_y + (F(i) - pos) * line_h
            dist = abs((y - center_y) / F(480.0))
            o = powf(min(max(F(1.0) - dist, F(0.0)), F(1.0)), 1.5)
            is_current = i == current
            msg = "".join(c for c in message if c.isascii())[:48]
            rows.append(
                HISTORY_ROW(
                    o=f(o),
                    y=f(y),
                    hash_fill=ORANGE if is_current else "#6d4a36",
                    hash=text(hash_),
                    date=text(date),
                    text_fill=BONE if is_current else "#8f8a82",
                    msg=text(msg),
                )
            )
        _, date, _ = COMMITS[min(current, n - 1)]
        return HISTORY(
            opacity=f(enter * (F(1.0) - exit_)),
            transform=f"translate(0 {s32((F(1.0) - enter) * F(80.0) - exit_ * F(80.0))})",
            band_y=f(center_y - F(34.0)), rows=rows, year=text(date[:4]),
            count=text(f"#{current + 1:03} / {n}"), date=text(date),
        )  # fmt: skip

    @staticmethod
    def stats(frame, ctx, lb):
        """Beats 16-32: the numbers, one per bar, then "video = f(frame)"."""
        items = (
            (HISTORY_DAYS // 365, "YEARS",
             f"{HISTORY_SINCE} → {HISTORY_UNTIL}  ·  {thousands(HISTORY_DAYS)} DAYS"),
            (HISTORY_COUNT, "COMMITS", "FROM THE FIRST “POC” TO TODAY"),
            (LINES_OF_RUST, "LINES OF RUST", "FFMPEG · SVG · SKIA · EDITOR · CLI"),
        )  # fmt: skip
        bar = usize(math.floor(lb / F(4.0)))
        local = lb - F(bar) * F(4.0)
        if bar < 3:
            value, unit, caption = items[bar]
            num = thousands(value)
            enter = expo_out(prog(local, 0.0, 0.7))
            exit_ = expo_in(prog(local, 3.65, 4.0))
            x = F(150.0) + (F(1.0) - enter) * F(260.0) - exit_ * F(300.0)
            num_w = measure(frame, ctx, DISPLAY, 400, 400, False, num) - F(10.0) * F(len(num))
            unit_s = snap(local - F(0.5))
            unit_w = measure(frame, ctx, DISPLAY, 110, 400, False, unit) - F(3.0) * F(len(unit))
            if F(150.0) + num_w + F(40.0) + unit_w < 1770.0:
                ux, uy, cap_y = num_w + F(40.0), F(0.0), F(0.0)
            else:
                ux, uy, cap_y = F(8.0), F(130.0), F(130.0)
            cap = prog(local, 1.0, 1.4)
            shown = thousands(round_u(F(value) * expo_out(prog(local, 0.0, 1.3))))
            return STAT(
                opacity=f(F(1.0) - exit_), transform=f"translate({s32(x)} 0)", shown=text(shown),
                unit_transform=f"translate({s32(ux)} {s32(uy + (F(1.0) - unit_s) * F(60.0))})",
                unit_opacity=f(min(unit_s, F(1.0))), unit=text(unit), rule_y=f(F(700.0) + cap_y),
                rule_w=f(max(cap * F(60.0), F(0.5))), caption_y=f(F(760.0) + cap_y), cap=f(cap),
                caption=text(caption),
            )  # fmt: skip
        exit_ = expo_in(prog(local, 3.7, 4.0))
        return ONE_IDEA(
            opacity=f(F(1.0) - exit_), a=f(min(snap(local), F(1.0))),
            video=Slam(150.0, 620.0, "video =", DISPLAY, 190.0, BONE).draw(local - F(1.0), 0.0, 150.0),
            f=Slam(905.0, 628.0, "f(frame)", SERIF, 270.0, ORANGE)
            .italicized()
            .draw(local - F(2.0), 260.0, 0.0),
        )  # fmt: skip


def title_block(date, o):
    """Engineering-drawing title block, bottom right."""
    if o <= 0.0:
        return None
    return TITLE_BLOCK(o=f(o), sheets=text(f"1 OF {HISTORY_COUNT}"), date=text(date))


# --- 02 / CODE: the code of a video is typed out while its output renders next to it

KW, TY, PL, PU, ST = ORANGE, "#d9c7a8", BONE, "#8f8a82", "#f3a676"
CODE = (
    (("impl ", KW), ("Video ", TY), ("for ", KW), ("Intro ", TY), ("{", PU)),
    (("    const ", KW), ("FPS", PL), (": ", PU), ("usize ", TY), ("= ", PU), ("60", ST), (";", PU)),
    (),
    (
        ("    fn ", KW), ("render_frame", PL), ("(", PU), ("&self", KW), (", ", PU), ("frame", PL),
        (": ", PU), ("Frame", TY), (") -> ", PU), ("Svgr ", TY), ("{", PU),
    ),
    (
        ("        let ", KW), ("y ", PL), ("= ", PU), ("spring", PL), ("(frame.", PU),
        ("seconds", PL), ("());", PU),
    ),
    (
        ("        svgr!", KW), ("(<", PU), ("text ", PL), ("y", TY), ("={y}>", PU),
        ('"EVERY FRAME"', ST), ("</", PU), ("text", PL), (">)", PU),
    ),
    (("    }", PU),),
    (("}", PU),),
)  # fmt: skip
CODE_TOTAL = sum(len(t) for line in CODE for t, _ in line)
CODE_X, CODE_Y, CODE_SIZE, LINE_H = F(150.0), F(300.0), F(34.0), F(56.0)
ADV = CODE_SIZE * F(0.6)
CODE_SPAN = T(
    '<text x="{x}" y="{y}" font-family="{MONO}" font-weight="500" font-size="{size}" fill="{fill}">{text}</text>'
)
CODE_FRAME = T("""
<g>
    <g opacity="{dim}">
        <text x="{code_x}" y="220" font-family="{MONO}" font-weight="500" font-size="22" letter-spacing="3" fill="{GREY}">SRC/LIB.RS</text>
        <rect x="{code_x}" y="236" width="1000" height="1" fill="{GREY}" opacity="0.5" />
        {rows}
        <rect x="{caret_x}" y="{caret_y}" width="16" height="36" fill="{ORANGE}" opacity="{caret}" />
        {called}
        {returns}
    </g>
    {out}
    {words}
</g>
""")
CODE_OUTPUT = T("""
<g opacity="{opacity}" transform="{transform}">
    <rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#141312" stroke="#3a3733" stroke-width="1.5" />
    {corners}
    <clipPath id="code-out"><rect x="{x}" y="{y}" width="{w}" height="{h}" /></clipPath>
    <g clip-path="url(#code-out)">
        <text x="{tx}" y="{ty}" text-anchor="middle" font-family="{DISPLAY}" font-size="76" letter-spacing="-2" fill="{BONE}">EVERY FRAME</text>
    </g>
    {output}
    {fnum}
    {callout}
</g>
""")
SILENCE = T("""
<g>
    <rect width="1920" height="1080" fill="{BG}" />
    <text x="960" y="560" text-anchor="middle" font-family="{MONO}" font-weight="500" font-size="40" letter-spacing="12" fill="{GREY}" opacity="{o}">RENDERED ON THE</text>
    <rect x="{x}" y="600" width="{w}" height="4" fill="{ORANGE}" />
</g>
""")


def code_output(frame, lb):
    """The frame the code draws: EVERY FRAME, bouncing on every beat."""
    appear = expo_out(prog(lb, 3.0, 4.0))
    if appear <= 0.0:
        return None
    exit_ = expo_in(prog(lb, 11.7, 12.0))
    x, y, w, h = F(1190.0), F(320.0), F(600.0), F(338.0)
    bounce = spring(fract(lb) * BEAT, 260.0, 14.0)
    ty = (F(1.0) - bounce) * F(-60.0)
    return CODE_OUTPUT(
        opacity=f(appear * (F(1.0) - exit_)), transform=f"translate({s32((F(1.0) - appear) * F(120.0))} 0)",
        x=f(x), y=f(y), w=f(w), h=f(h),
        corners=corners(x - F(14.0), y - F(14.0), w + F(28.0), h + F(28.0), 18.0, ORANGE, 2.0),
        tx=f(x + w / F(2.0)), ty=f(y + h / F(2.0) + F(30.0) + ty),
        output=label(x, y + h + F(44.0), "OUTPUT", GREY, 18.0, "start"),
        fnum=label(x + w, y + h + F(44.0), f"FRAME {frame.global_index:05}", ORANGE, 18.0, "end"),
        callout=callout(x + w / F(2.0), y + h + F(14.0), x + w / F(2.0) - F(40.0), 820.0,
                        "DRAWN BY SKIA ON THE GPU", ORANGE, prog(lb, 10.0, 10.8)),
    )  # fmt: skip


EVERY = Slam(150.0, 560.0, "EVERY", DISPLAY, 250.0, BONE)
FRAME_DOT = Slam(150.0, 800.0, "FRAME.", DISPLAY, 250.0, ORANGE)


def big_words(lb):
    """Beats 12-14: EVERY / FRAME. over the dimmed code."""
    l = lb - F(12.0)
    if l < 0.0:
        return None
    return GROUP(content=[EVERY.draw(l, 0.0, 190.0), FRAME_DOT.draw(l - F(1.0), 0.0, 190.0)])


def silence(l):
    """The bar that goes (nearly) silent before the drop."""
    w = snap(l - F(0.9))
    return SILENCE(
        o=f(prog(l, 0.0, 0.2)), x=f(F(960.0) - F(30.0) * w), w=f(max(F(60.0) * w, F(0.5)))
    )


class CodeScene(BeatScene):
    START, END = 32.0, 48.0

    def render_frame(self, frame, ctx):
        lb = self.lb(frame)
        if lb >= 46.0 - 32.0:
            return silence(lb - F(14.0))
        typed = usize(powf(expo_out(prog(lb, 0.0, 7.0)), 0.7) * F(CODE_TOTAL))
        left = typed
        rows = []
        caret = (CODE_X, CODE_Y)
        for li, line in enumerate(CODE):
            y = CODE_Y + F(li) * LINE_H
            col = 0
            spans = []
            for value, color in line:
                n = len(value)
                take = min(n, left)
                if take > 0:
                    part = value[:take]
                    lead = len(part) - len(part.lstrip(" "))
                    part = part.lstrip()
                    if part:
                        spans.append(
                            CODE_SPAN(
                                x=f(CODE_X + F(col + lead) * ADV),
                                y=f(y),
                                size=f(CODE_SIZE),
                                fill=color,
                                text=text(part),
                            )
                        )
                left -= take
                col += take
                if take < n:
                    break
            if left > 0 or col > 0:
                caret = (CODE_X + F(col) * ADV, y)
            rows.append(GROUP(content=spans))
            if left == 0:
                break
        return CODE_FRAME(
            dim=f(F(1.0) - F(0.75) * prog(lb, 12.0, 12.3)), code_x=f(CODE_X), rows=rows,
            caret_x=f(caret[0] + F(2.0)), caret_y=f(caret[1] - F(28.0)),
            caret=1.0 if fract(lb * F(2.0)) < 0.6 else 0.0,
            called=callout(CODE_X + F(13.0) * ADV, CODE_Y + F(3.0) * LINE_H - F(40.0), CODE_X + F(13.0) * ADV,
                           190.0, "CALLED FOR EVERY FRAME", ORANGE, prog(lb, 8.0, 8.8)),
            returns=callout(CODE_X + F(13.0) * ADV, CODE_Y + F(5.0) * LINE_H + F(12.0), 520.0, 790.0,
                            "RETURNS AN SVG TREE", BONE, prog(lb, 9.0, 9.8)),
            out=code_output(frame, lb), words=big_words(lb),
        )  # fmt: skip


# --- 03 / GPU: the first drop on "GPU", then the render pipeline

GPU_SLAM = T("""
<g>
    <rect width="1920" height="1080" fill="{ORANGE}" />
    <g transform="{t}">
        <text x="120" y="880" font-family="{DISPLAY}" font-size="760" letter-spacing="-40" fill="{INK}">GPU</text>
        <rect x="1605" y="765" width="115" height="115" fill="{INK}" transform="{dot}" opacity="{dot_o}" />
    </g>
    <g font-family="{MONO}" font-weight="600" font-size="22" letter-spacing="4" fill="{INK}">
        <text x="130" y="170">SKIA</text>
        <text x="330" y="170">METAL</text>
        <text x="540" y="170">VULKAN</text>
        <text x="1790" y="170" text-anchor="end">NO BROWSER IN THE LOOP</text>
    </g>
    <rect x="130" y="196" width="1660" height="3" fill="{INK}" />
</g>
""")
PIPE_NODES = (
    ("svgr!", "SVG TREE / FRAME"), ("SKIA", "GANESH, GPU"), ("METAL", "VULKAN ON LINUX"),
    ("FFMPEG", "H.264 · HEVC · VP9"), (".MP4", "OUT.MP4"),
)  # fmt: skip
PIPE_BOX = T("""
<g opacity="{opacity}" transform="{transform}">
    <rect x="0" y="-70" width="250" height="140" fill="{fill}" stroke="{stroke}" stroke-width="2" />
    <text x="125" y="8" text-anchor="middle" font-family="{DISPLAY}" font-size="40" fill="{name_fill}">{name}</text>
    <text x="125" y="46" text-anchor="middle" font-family="{MONO}" font-weight="500" font-size="15" letter-spacing="1.5" fill="{sub_fill}">{sub}</text>
</g>
""")
PIPE_LINK = T('<rect x="{x}" y="{y}" width="{w}" height="2" fill="#5a564f" />')
PIPE_PACKET = T('<rect x="{x}" y="{y}" width="12" height="8" fill="{ORANGE}" />')
PIPELINE = T("""
<g opacity="{opacity}">
    <g transform="{title_t}" opacity="{title_o}">
        <text x="186" y="330" font-family="{DISPLAY}" font-size="120" letter-spacing="-4" fill="{BONE}">DIRECTLY ON</text>
        <text x="186" y="450" font-family="{DISPLAY}" font-size="120" letter-spacing="-4" fill="{ORANGE}">THE GPU.</text>
    </g>
    {links}
    {boxes}
    {note}
    <text x="1730" y="450" text-anchor="end" font-family="{MONO}" font-weight="600" font-size="30" fill="{ORANGE}" opacity="{fps_o}">{fps}</text>
</g>
""")


def gpu_slam(lb):
    s = F(1.0) + (F(1.0) - expo_out(lb / F(0.35))) * F(0.18)
    shake = (F(1.0) - prog(lb, 0.0, 0.5)) * F(14.0)
    dx = (hash32(lb * F(97.0)) - F(0.5)) * shake
    dy = (hash32(lb * F(53.0) + F(3.0)) - F(0.5)) * shake
    dot = snap(lb - F(1.0))
    return GPU_SLAM(
        t=f"translate({s32(dx)} {s32(dy)}) translate(150 790) scale({s32(s)}) translate(-150 -790)",
        dot=f"translate(0 {s32((F(1.0) - dot) * F(-300.0))})", dot_o=f(prog(lb, 1.0, 1.05)),
    )  # fmt: skip


def pipeline(l):
    """svgr! through Skia, the GPU and ffmpeg to an .mp4, with packets moving on the beat."""
    title_in = snap(l)
    exit_ = expo_in(prog(l, 5.7, 6.0))
    x0, gap, y = F(190.0), F(330.0), F(640.0)
    boxes = []
    for i, (name, sub) in enumerate(PIPE_NODES):
        at = F(0.4) + F(i) * F(0.35)
        s = snap(l - at)
        hot = i == 2
        boxes.append(
            PIPE_BOX(
                opacity=f(prog(l, at, at + F(0.1))),
                transform=f"translate({s32(x0 + F(i) * gap)} {s32(y + (F(1.0) - s) * F(50.0))})",
                fill=ORANGE if hot else "#121110",
                stroke=ORANGE if hot else "#5a564f",
                name_fill=INK if hot else BONE,
                name=text(name),
                sub_fill=INK if hot else GREY,
                sub=text(sub),
            )
        )
    links = []
    for i in range(4):
        at = F(0.6) + F(i) * F(0.35)
        pr = expo_out(prog(l, at, at + F(0.5)))
        xa = x0 + F(i) * gap + F(250.0)
        length = gap - F(250.0)
        links.append(PIPE_LINK(x=f(xa), y=f(y - F(1.0)), w=f(max(length * pr, F(0.5)))))
        for k in range(3):
            phase = fract(l * F(2.0) + F(k) / F(3.0) + F(i) * F(0.21))
            if l > at + F(0.5):
                links.append(PIPE_PACKET(x=f(xa + phase * length - F(6.0)), y=f(y - F(4.0))))
    return PIPELINE(
        opacity=f(F(1.0) - exit_), title_t=f"translate(0 {s32((F(1.0) - title_in) * F(60.0))})",
        title_o=f(prog(l, 0.0, 0.1)), links=links, boxes=boxes,
        note=label(190.0, 820.0, "NO HEADLESS BROWSER. NO SCREENSHOTS. NO REACT.", GREY, 22.0, "start"),
        fps_o=f(prog(l, 2.0, 2.2)), fps=text("1920×1080 · 60 FPS"),
    )  # fmt: skip


class GpuScene(BeatScene):
    START, END = 48.0, 56.0

    def render_frame(self, frame, ctx):
        lb = self.lb(frame)
        return gpu_slam(lb) if lb < 2.0 else pipeline(lb - F(2.0))


# --- 04 / TEXT: a wall of marquee rows; the lit row jumps on every beat

TEXT_ROWS = (
    "TEXT · SHAPED · MEASURED · WRAPPED · ", "KERNING · LIGATURES · 60 FPS · ",
    "EVERY GLYPH ON THE GPU · ", "TEXT · TEXT · TEXT · TEXT · ", "FONTS COMPILED INTO THE BINARY · ",
    "TYPOGRAPHY IS CODE · ", "TEXT · SHAPED · MEASURED · ", "WORD BY WORD · LINE BY LINE · ",
)  # fmt: skip
ROW_H, TEXT_SIZE = F(140.0), 160
LIT_COPY = T(
    '<text x="{x}" y="{y}" font-family="{COND}" font-size="{size}" fill="{ORANGE}">{t}</text>'
)
DIM_COPY = T(
    '<text x="{x}" y="{y}" font-family="{COND}" font-size="{size}" fill="none" stroke="#4b4741" stroke-width="1.6">{t}</text>'
)
TEXT_ROW = T('<g opacity="{o}">{copies}</g>')
TEXT_WALL = T("""
<g opacity="{opacity}">
    {rows}
    <rect x="120" y="360" width="690" height="270" fill="{BG}" />
    <text x="150" y="560" font-family="{DISPLAY}" font-size="170" letter-spacing="-6" fill="{BONE}">TEXT</text>
    {number}
    {caption}
</g>
""")
TEXT_NUMBER = label(154.0, 408.0, "01", ORANGE, 26.0, "start")
TEXT_CAPTION = label(154.0, 610.0, "SHAPED · MEASURED · WRAPPED", GREY, 18.0, "start")


class TextScene(BeatScene):
    START, END = 56.0, 62.0

    def render_frame(self, frame, ctx):
        lb = self.lb(frame)
        exit_ = expo_in(prog(lb, 5.7, 6.0))
        lit = (math.floor(max(lb, F(0.0))) * 3 + 1) % len(TEXT_ROWS)
        rows = []
        for i, value in enumerate(TEXT_ROWS):
            w = measure(frame, ctx, COND, TEXT_SIZE, 400, False, value)
            direction = F(-1.0) if i % 2 == 0 else F(1.0)
            speed = F(260.0) + F(math.fmod(float(F(i) * F(37.0)), 140.0))
            enter = expo_out(prog(lb, F(i) * F(0.05), F(0.6) + F(i) * F(0.05)))
            offset = (
                rem_euclid(lb * BEAT * speed * direction, w)
                - w
                + (F(1.0) - enter) * F(900.0) * direction
            )
            y = f(F(150.0) + F(i) * ROW_H)
            is_lit = i == lit
            flash = pulse(lb, 5.0) if is_lit else F(0.0)
            copy = LIT_COPY if is_lit else DIM_COPY
            copies = [
                copy(x=f(offset + F(k) * w), y=y, size=TEXT_SIZE, t=text(value)) for k in range(4)
            ]
            rows.append(TEXT_ROW(o=f(F(0.7) + flash * F(0.3)), copies=copies))
        return TEXT_WALL(
            opacity=f(F(1.0) - exit_), rows=rows, number=TEXT_NUMBER, caption=TEXT_CAPTION
        )


# --- 05 / IMAGE: the 2024 beta poster develops from an orange dither

IMAGE_FRAME = T("""
<g opacity="{opacity}">
    <g transform="{t}">
        <image href="{layer}" x="{x}" y="{y}" width="{w}" height="{h}" />
        {corners}
    </g>
    <text x="150" y="220" font-family="{DISPLAY}" font-size="120" letter-spacing="-4" fill="{BONE}" opacity="{title_o}">IMAGE</text>
    {number}
    {file}
    {pass_}
</g>
""")
INK_1A = ff.Color.hex("#1a1210")
HOT = ff.Color.hex(ORANGE)


class ImageScene(BeatScene):
    START, END = 62.0, 66.0

    def render_frame(self, frame, ctx):
        lb = self.lb(frame)
        poster = ctx.image("beta_poster.jpg")
        if poster is None:
            return None
        x, y, w, h = F(560.0), F(300.0), F(1060.0), F(596.0)
        enter = expo_out(prog(lb, 0.0, 0.6))
        exit_ = expo_in(prog(lb, 3.7, 4.0))
        layer = DEVELOP.draw(frame, {
            "iChannel0": poster, "uImg": (1920.0, 1080.0), "uReveal": f(prog(lb, 0.0, 0.7)),
            "uProgress": f(cubic_in_out(prog(lb, 0.9, 3.1)) * F(1.02)), "uInk": INK_1A, "uHot": HOT,
        })  # fmt: skip
        s = F(0.94) + F(0.06) * enter
        c = s32(y + h / F(2.0))
        return IMAGE_FRAME(
            opacity=f(F(1.0) - exit_), t=f"translate(960 {c}) scale({s32(s)}) translate(-960 -{c})",
            layer=layer, x=f(x), y=f(y), w=f(w), h=f(h),
            corners=corners(x - F(18.0), y - F(18.0), w + F(36.0), h + F(36.0), 22.0, BONE, 2.0),
            title_o=f(prog(lb, 0.2, 0.3)), number=label(154.0, 110.0, "02", ORANGE, 26.0, "start"),
            file=label(x, y + h + F(60.0), "BETA_POSTER.JPG · 2024", GREY, 18.0, "start"),
            pass_=label(x + w, y + h + F(60.0), "DITHER → COLOR · ONE SKSL PASS", ORANGE, 18.0, "end"),
        )  # fmt: skip


# --- 06 / VIDEO: two podcast feeds decoded by ffmpeg; on the last bar the right one is keyed out

LEFT = (F(150.0), F(300.0), F(790.0), F(444.0))
RIGHT = (F(980.0), F(300.0), F(790.0), F(444.0))
ORANGE_C = ff.Color.hex(ORANGE)
BONE_C = ff.Color.hex(BONE)


def clip_frame(frame, ctx, file):
    """The synced frame of a looping clip, as an image (None when the clip is missing)."""
    video = frame.video_frame(ctx, file, start_from=0.0, looping=True)
    return None if video is None else video.image


def keyed_guest(frame, ctx, rect, halftone, alpha):
    """The keyed guest from the right feed: footage (0) or halftone print (1)."""
    image = clip_frame(frame, ctx, "right_clip.mp4")
    if image is None:
        return None
    layer = KEY.draw(frame, {
        "iChannel0": image, "uImg": (1280.0, 720.0), "uHalftone": f(halftone), "uCell": 9.0,
        "uAlpha": f(alpha), "uInk": ORANGE_C, "uPaper": BONE_C,
    })  # fmt: skip
    x, y, w, h = rect
    return IMAGE(href=layer, x=f(x), y=f(y), width=f(w), height=f(h))


def tunnel(frame, speed, glow):
    layer = TUNNEL.draw(frame, {
        "uT": f(gsec(frame)), "uSpeed": f(speed), "uGlow": f(glow), "uHot": ORANGE_C, "uBone": BONE_C,
    })  # fmt: skip
    return FULL_IMAGE(href=layer)


FILM_HOLE = T('<rect x="{x}" y="{y}" width="14" height="10" rx="2" fill="#2d2a27" />')


def film(x, y, w, h):
    holes = []
    for i in range(22):
        hx = f(x + F(10.0) + F(i) * (w - F(20.0)) / F(21.0))
        holes += [FILM_HOLE(x=hx, y=f(y - F(26.0))), FILM_HOLE(x=hx, y=f(y + h + F(16.0)))]
    return GROUP(content=holes)


FILM_LEFT, FILM_RIGHT = film(*LEFT), film(*RIGHT)
KEYED_RIGHT = T("""
<g>
    <clipPath id="vid-right"><rect x="{x}" y="{y}" width="{w}" height="{h}" /></clipPath>
    <g clip-path="url(#vid-right)">{tunnel}</g>
    <g opacity="{flicker}">{guest}</g>
</g>
""")
VIDEO_FRAME = T("""
<g>
    <g opacity="{exit}">
        <text x="150" y="220" font-family="{DISPLAY}" font-size="120" letter-spacing="-4" fill="{BONE}">VIDEO</text>
        {number}
        <g opacity="{enter_l}" transform="{t_l}">
            {film_l}
            {left}
            {label_l}
        </g>
        {decoded}
    </g>
    <g opacity="{enter_r}" transform="{t_r}">
        {film_r}
        {right}
        {label_r}
        {key_label}
    </g>
</g>
""")
VIDEO_NUMBER = label(154.0, 110.0, "03", ORANGE, 26.0, "start")
VIDEO_DECODED = label(1770.0, 220.0, "DECODED BY FFMPEG · IN SYNC TO THE FRAME", GREY, 18.0, "end")


class VideoScene(BeatScene):
    START, END = 66.0, 72.0

    def render_frame(self, frame, ctx):
        lb = self.lb(frame)
        left = clip_frame(frame, ctx, "left_clip.mp4")
        right = clip_frame(frame, ctx, "right_clip.mp4")
        enter_l = expo_out(prog(lb, 0.0, 0.7))
        enter_r = expo_out(prog(lb, 0.5, 1.2))
        keyed = lb >= 4.0
        seconds = F(frame.index) / F(FPS)
        lx, ly, lw, lh = LEFT
        rx, ry, rw, rh = RIGHT
        left_img = (
            None if left is None else IMAGE(href=left, x=f(lx), y=f(ly), width=f(lw), height=f(lh))
        )
        if keyed:
            flicker = (1.0 if hash32(lb * F(211.0)) > 0.5 else 0.0) if lb < 4.25 else 1.0
            right_img = KEYED_RIGHT(
                x=f(rx), y=f(ry), w=f(rw), h=f(rh), tunnel=tunnel(frame, 3.0, 1.0), flicker=flicker,
                guest=keyed_guest(frame, ctx, RIGHT, 0.0, 1.0),
            )  # fmt: skip
        else:
            right_img = (
                None
                if right is None
                else IMAGE(href=right, x=f(rx), y=f(ry), width=f(rw), height=f(rh))
            )
        exit_ = expo_in(prog(lb, 5.75, 6.0))
        return VIDEO_FRAME(
            exit=f(F(1.0) - exit_), number=VIDEO_NUMBER, enter_l=f(enter_l),
            t_l=f"translate(0 {s32((F(1.0) - enter_l) * F(80.0))})", film_l=FILM_LEFT, left=left_img,
            label_l=label(lx, ly + lh + F(70.0), f"LEFT.MP4  {timecode(seconds + F(28.0))}", GREY, 18.0, "start"),
            decoded=VIDEO_DECODED, enter_r=f(enter_r),
            t_r=f"translate(0 {s32((F(1.0) - enter_r) * F(80.0))})", film_r=FILM_RIGHT, right=right_img,
            label_r=label(rx, ry + rh + F(70.0), f"RIGHT.MP4  {timecode(seconds + F(246.0))}", GREY, 18.0, "start"),
            key_label=label(rx + rw, ry + rh + F(70.0), "CHROMA KEY · SKSL" if keyed else "", ORANGE, 18.0, "end"),
        )  # fmt: skip


# --- 07 / SHADER: the tunnel grows to the whole frame, its SkSL source scrolls, the guest prints

SOURCE_LINES = [line[:60] for line in TUNNEL_SOURCE.splitlines() if line.strip()]
SOURCE_LINE = T(
    '<text x="150" y="{y}" font-family="{MONO}" font-size="17" fill="#d8d0c4" opacity="{o}">{t}</text>'
)
SHADER_FRAME = T("""
<g opacity="{opacity}">
    <clipPath id="shader-open"><rect x="{cx}" y="{cy}" width="{cw}" height="{ch}" /></clipPath>
    <g clip-path="url(#shader-open)">{tunnel}</g>
    {guest}
    <g opacity="{panel}">
        <rect x="120" y="250" width="720" height="650" fill="#0b0b0b" fill-opacity="0.72" />
        <clipPath id="shader-src"><rect x="120" y="250" width="720" height="650" /></clipPath>
        <g clip-path="url(#shader-src)">{lines}</g>
        {corners}
        {caption}
    </g>
    <g opacity="{title_o}" transform="{title_t}">
        <text x="150" y="220" font-family="{DISPLAY}" font-size="120" letter-spacing="-4" fill="{BONE}">SHADER</text>
        {number}
    </g>
    <g opacity="{all_o}" transform="{all_t}">
        <rect x="860" y="850" width="930" height="120" fill="{ORANGE}" />
        <text x="890" y="940" font-family="{DISPLAY}" font-size="74" letter-spacing="-2" fill="{INK}">ALL IN ONE FRAME.</text>
    </g>
</g>
""")
SHADER_CORNERS = corners(120.0, 250.0, 720.0, 650.0, 18.0, ORANGE, 2.0)
SHADER_CAPTION = label(
    140.0, 935.0, "TUNNEL.SKSL · RAYMARCHED · 80 STEPS/PIXEL", ORANGE, 18.0, "start"
)
SHADER_NUMBER = label(154.0, 110.0, "04", ORANGE, 26.0, "start")


class ShaderScene(BeatScene):
    START, END = 72.0, 80.0

    def render_frame(self, frame, ctx):
        lb = self.lb(frame)
        open_ = expo_out(prog(lb, 0.0, 1.0))
        rx, ry, rw, rh = RIGHT
        guest_rect = (
            lerp(rx, 860.0, open_),
            lerp(ry, 150.0, open_),
            lerp(rw, 1280.0, open_),
            lerp(rh, 720.0, open_),
        )
        lines = []
        for i, line in enumerate(SOURCE_LINES):
            y = F(300.0) + F(i) * F(26.0) - lb * F(40.0)
            o = F(1.0) if 250.0 <= y < 900.0 else F(0.0)
            lines.append(SOURCE_LINE(y=f(y), o=f(o * F(0.85)), t=text(line)))
        title = snap(lb - F(0.8))
        all_ = snap(lb - F(4.0))
        return SHADER_FRAME(
            opacity=f(F(1.0) - expo_in(prog(lb, 7.7, 8.0))),
            cx=f(lerp(rx, 0.0, open_)), cy=f(lerp(ry, 0.0, open_)),
            cw=f(max(lerp(rw, 1920.0, open_), F(1.0))), ch=f(max(lerp(rh, 1080.0, open_), F(1.0))),
            tunnel=tunnel(frame, 3.0, 1.0), guest=keyed_guest(frame, ctx, guest_rect, prog(lb, 0.8, 1.6), 1.0),
            panel=f(prog(lb, 1.0, 1.6)), lines=lines, corners=SHADER_CORNERS, caption=SHADER_CAPTION,
            title_o=f(prog(lb, 0.8, 0.9)), title_t=f"translate(0 {s32((F(1.0) - title) * F(50.0))})",
            number=SHADER_NUMBER, all_o=f(prog(lb, 4.0, 4.1)),
            all_t=f"translate(0 {s32((F(1.0) - all_) * F(60.0))})",
        )  # fmt: skip


# --- 08 / SCALE: HOW FAST? while a wall of 3,334 text nodes fills in

NODES_PER_FRAME, COLS, ROWS = 3_334, 62, 54
WORDS = ("ff", "fx", "0x", "60", "rs", "gp", "sk", "vk", "mt", "tx")
_I = np.arange(NODES_PER_FRAME)
_C, _R = _I % COLS, _I // COLS
WALL_KEY = (_C.astype(F) / F(COLS)) * F(0.7) + (_R.astype(F) / F(ROWS)) * F(0.3)
WALL_SEED = _I.astype(F) * F(1.37)
WALL_WORD = (hash_array(_I.astype(F)) * F(len(WORDS))).astype(np.int64) % len(WORDS)
_DX = (F(1770.0) - F(150.0)) / F(COLS)
_DY = (F(900.0) - F(345.0)) / F(ROWS)
WALL_X = F(150.0) + _C.astype(F) * _DX
WALL_Y = F(345.0) + _R.astype(F) * _DY
WALL_COLORS = (ORANGE, "#b3aca2", "#6b665f")
WALL_NODE = T(
    '<text x="{x}" y="{y}" font-family="{MONO}" font-size="13" font-weight="500" fill="{fill}">{word}</text>'
)
_wall_nodes: dict = {}
_wall_hashes: dict = {}


def wall_hash(step):
    """The hash of every wall cell for one quarter beat, computed once."""
    h = _wall_hashes.get(step)
    if h is None:
        h = _wall_hashes[step] = hash_array(WALL_SEED + F(step))
    return h


def wall_node(i, color):
    """The text node of wall cell i in one of the three colors, built once."""
    node = _wall_nodes.get((i, color))
    if node is None:
        node = _wall_nodes[i, color] = WALL_NODE(
            x=f(WALL_X[i]), y=f(WALL_Y[i]), fill=WALL_COLORS[color], word=text(WORDS[WALL_WORD[i]])
        )
    return node


WALL = T("""
<g opacity="{opacity}">
    {nodes}
    <rect x="1010" y="130" width="760" height="140" fill="{BG}" />
    <text x="1770" y="232" text-anchor="end" font-family="{DISPLAY}" font-size="110" letter-spacing="-3" fill="{BONE}">{count}</text>
    {nodes_label}
    {frame_label}
</g>
""")
WALL_LABEL = label(1770.0, 290.0, "TEXT NODES TO RENDER", ORANGE, 20.0, "end")
WALL_FRAMES = label(
    150.0, 940.0, f"ONE FRAME = {thousands(100_000)} TEXT NODES  ×  300 FRAMES", GREY, 20.0, "start"
)


def wall(lb):
    """3,334 tiny text nodes filling in with a diagonal wave."""
    l = lb - F(4.0)
    if l < 0.0:
        return None
    reach = cubic_in_out(prog(l, 0.0, 8.0)) * F(1.02)
    shown = np.nonzero(WALL_KEY <= reach)[0]
    h = wall_hash(math.floor(lb * F(4.0)))[shown]
    fresh = (reach - WALL_KEY[shown]) < F(0.03)
    color = np.where(fresh | (h > F(0.97)), 0, np.where(h > F(0.55), 1, 2))
    nodes = [wall_node(i, c) for i, c in zip(shown.tolist(), color.tolist(), strict=True)]
    count = round_u(F(len(shown)) / F(NODES_PER_FRAME) * F(100_000.0))
    return WALL(
        opacity=f(F(1.0) - expo_in(prog(l, 9.6, 10.0))), nodes=nodes, count=text(thousands(count)),
        nodes_label=WALL_LABEL, frame_label=WALL_FRAMES,
    )  # fmt: skip


HOW = Slam(150.0, 440.0, "HOW", DISPLAY, 330.0, BONE)
FAST = Slam(150.0, 760.0, "FAST?", DISPLAY, 330.0, ORANGE)
QUESTION = T('<g transform="{t}">{how}{fast}</g>')
COUNTDOWN = T("""
<g opacity="{opacity}">
    <text x="960" y="{ya}" text-anchor="middle" font-family="{DISPLAY}" font-size="120" letter-spacing="-3" fill="{GREY}">REMOTION</text>
    <text x="960" y="560" text-anchor="middle" font-family="{SERIF}" font-style="italic" font-size="70" fill="{BONE}" opacity="{v}">vs</text>
    <text x="960" y="{yb}" text-anchor="middle" font-family="{DISPLAY}" font-size="120" letter-spacing="-3" fill="{ORANGE}" opacity="{v}">FFRAMES</text>
</g>
""")


def question(lb):
    """HOW / FAST? on beats 0 and 1, then it shrinks into a heading."""
    shrink = cubic_in_out(prog(lb, 3.0, 4.0))
    s = lerp(1.0, 0.28, shrink)
    t = f"translate({s32(lerp(0.0, F(150.0) - F(150.0) * s, shrink))} {s32(lerp(0.0, 34.0, shrink))}) scale({s32(s)})"
    return QUESTION(t=t, how=HOW.draw(lb, -260.0, 0.0), fast=FAST.draw(lb - F(1.0), 260.0, 0.0))


def countdown(l):
    """The near silent bar before the drop: two names, then nothing."""
    v = f(prog(l, 0.5, 0.55))
    return COUNTDOWN(
        opacity=f(F(1.0) - prog(l, 1.55, 1.6)), ya=f(F(470.0) + (F(1.0) - snap(l)) * F(40.0)), v=v,
        yb=f(F(690.0) + (F(1.0) - snap(l - F(0.5))) * F(40.0)),
    )  # fmt: skip


class ScaleScene(BeatScene):
    START, END = 80.0, 96.0

    def render_frame(self, frame, ctx):
        lb = self.lb(frame)
        if lb >= 14.0:
            return countdown(lb - F(14.0))
        return GROUP(content=[wall(lb), question(lb)])


# --- 09 / BENCHMARK: Remotion and fframes render the same 100,000 elements, as a time-lapse

RACE_START, RACE_BEATS, RESULT_AT, TABLE_AT = F(2.0), F(12.0), F(16.0), F(22.0)
SLOWEST = max(BENCH_REMOTION_S, BENCH_FFRAMES_S, F(0.001))
GRID_INK = ff.Color.hex("#6f6a63")
LANES = (
    (BENCH_REMOTION_LABEL, "CHROME + REACT → H.264 MP4", BENCH_REMOTION_S, GREY, F(470.0)),
    (BENCH_FFRAMES_LABEL, "RUST + SKIA → H.264 MP4", BENCH_FFRAMES_S, ORANGE, F(700.0)),
)  # fmt: skip
LANE = T("""
<g opacity="{opacity}" transform="{transform}">
    <text x="150" y="{y}" font-family="{DISPLAY}" font-size="58" letter-spacing="-2" fill="{name_fill}">{name}</text>
    <text x="150" y="{y_sub}" font-family="{MONO}" font-weight="500" font-size="18" letter-spacing="2.5" fill="{GREY}">{sub}</text>
    <rect x="150" y="{y_bar}" width="1620" height="64" fill="#141312" stroke="#2f2c29" stroke-width="1.5" />
    <rect x="150" y="{y_bar}" width="{bar_w}" height="64" fill="{color}" />
    <rect x="150" y="{y_bar}" width="1620" height="64" fill="{BONE}" opacity="{flash}" />
    <text x="1770" y="{y}" text-anchor="end" font-family="{MONO}" font-weight="600" font-size="52" fill="{time_fill}">{time}</text>
    <text x="170" y="{y_in}" font-family="{MONO}" font-weight="600" font-size="22" letter-spacing="2" fill="{INK}" opacity="{frames_o}">{frames}</text>
    <g opacity="{done_o}" transform="{done_t}">
        <text x="1750" y="{y_in}" text-anchor="end" font-family="{MONO}" font-weight="700" font-size="24" letter-spacing="4" fill="{INK}">DONE</text>
    </g>
</g>
""")
RACE = T("""
<g opacity="{opacity}">
    {title}
    {spec}
    {rows}
    <g opacity="{lapse_o}">
        {lapse}
    </g>
</g>
""")
NODES_TITLE = Slam(150.0, 250.0, "100,000 TEXT NODES", DISPLAY, 120.0, BONE)
RACE_SPEC = label(
    154.0, 310.0, "300 FRAMES · 3840×2160 · H.264 MP4 · SAME LAYOUT, SAME FONT", GREY, 20.0, "start"
)
SPEEDUP = SLOWEST / (RACE_BEATS * BEAT)
RACE_LAPSE = label(
    1770.0, 310.0, f"TIME-LAPSE ×{float(SPEEDUP):.1f} · MEASURED WALL CLOCK", ORANGE, 20.0, "end"
)


def race(lb):
    real = prog(lb, RACE_START, RACE_START + RACE_BEATS) * SLOWEST
    rows = []
    for i, (name, sub, secs, color, y) in enumerate(LANES):
        appear = snap(lb - F(0.6) - F(i) * F(0.3))
        pr = min(real / max(secs, F(0.001)), F(1.0))
        done = pr >= 1.0
        bar_w = max(F(1620.0) * pr, F(0.5))
        done_at = RACE_START + RACE_BEATS * secs / SLOWEST
        stamp = snap(lb - done_at)
        flash = exp32(-(lb - done_at) * F(6.0)) if done else F(0.0)
        rows.append(
            LANE(
                opacity=f(prog(lb, F(0.6) + F(i) * F(0.3), F(0.7) + F(i) * F(0.3))),
                transform=f"translate({s32((F(1.0) - appear) * F(-120.0))} 0)",
                y=f(y),
                name_fill=ORANGE if i == 1 else BONE,
                name=text(name),
                y_sub=f(y + F(34.0)),
                sub=text(sub),
                y_bar=f(y + F(56.0)),
                bar_w=f(bar_w),
                color=color,
                flash=f(flash * F(0.6)),
                time_fill=color if done else BONE,
                time=text(f"{float(min(real, secs)):.3f}s"),
                y_in=f(y + F(100.0)),
                frames_o=1.0 if bar_w > 260.0 else 0.0,
                frames=text(f"{math.floor(F(300.0) * pr)} / 300 FRAMES"),
                done_o=1.0 if done else 0.0,
                done_t=f"translate(0 {s32((F(1.0) - stamp) * F(20.0))})",
            )
        )
    return RACE(
        opacity=f(F(1.0) - expo_in(prog(lb, 15.6, 16.0))), title=NODES_TITLE.draw(lb, 0.0, 140.0),
        spec=RACE_SPEC, rows=rows, lapse_o=f(prog(lb, RACE_START, RACE_START + F(0.2))), lapse=RACE_LAPSE,
    )  # fmt: skip


RESULT = T("""
<g opacity="{opacity}">
    <rect width="1920" height="1080" fill="{ORANGE}" />
    <g transform="{t}">
        <text x="130" y="760" font-family="{DISPLAY}" font-size="480" letter-spacing="-30" fill="{INK}">{n}</text>
    </g>
    <text x="150" y="{y}" font-family="{DISPLAY}" font-size="120" letter-spacing="-4" fill="{INK}" opacity="{o}">FASTER THAN REMOTION</text>
    <g font-family="{MONO}" font-weight="600" font-size="22" letter-spacing="4" fill="{INK}">
        <text x="150" y="170">SAME 100,000 TEXT NODES</text>
        <text x="1770" y="170" text-anchor="end">COMPLETE MP4 · MEDIAN WALL CLOCK</text>
    </g>
    <rect x="150" y="196" width="1620" height="3" fill="{INK}" />
</g>
""")
RATIO = BENCH_REMOTION_S / max(BENCH_FFRAMES_S, F(0.001))


def result(l):
    """N× FASTER on an orange field."""
    n = F(1.0) + (RATIO - F(1.0)) * expo_out(prog(l, 0.0, 1.2))
    s = F(1.0) + (F(1.0) - expo_out(l / F(0.35))) * F(0.15)
    return RESULT(
        opacity=f(F(1.0) - expo_in(prog(l, 5.7, 6.0))),
        t=f"translate(150 760) scale({s32(s)}) translate(-150 -760)", n=text(f"{float(n):.2f}×"),
        y=f(F(900.0) + (F(1.0) - snap(l - F(1.0))) * F(60.0)), o=f(prog(l, 1.0, 1.08)),
    )  # fmt: skip


TABLE_ROWS = (
    (BENCH_REMOTION_LABEL, BENCH_REMOTION_S, GREY), ("FFRAMES · CPU", BENCH_FFRAMES_CPU_S, BONE),
    (BENCH_FFRAMES_LABEL, BENCH_FFRAMES_S, ORANGE),
)  # fmt: skip
TABLE_ROW = T("""
<g opacity="{opacity}" transform="{transform}">
    <rect x="150" y="{y_box}" width="1620" height="110" fill="#0f0e0d" fill-opacity="0.85" stroke="#2f2c29" stroke-width="1.5" />
    <rect x="150" y="{y_box}" width="6" height="110" fill="{color}" />
    <text x="190" y="{y}" font-family="{DISPLAY}" font-size="48" letter-spacing="-1" fill="{BONE}">{name}</text>
    <text x="1740" y="{y}" text-anchor="end" font-family="{MONO}" font-weight="600" font-size="48" fill="{color}">{secs}</text>
</g>
""")
TABLE = T("""
<g opacity="{opacity}">
    {title}
    {wall}
    {items}
    {a}
    {b}
    {c}
</g>
""")
NUMBERS = Slam(150.0, 300.0, "THE NUMBERS", DISPLAY, 110.0, BONE)
TABLE_LABELS = {
    "wall": label(1740.0, 400.0, "WALL CLOCK", GREY, 18.0, "end"),
    "a": label(154.0, 860.0, "RENDER + ENCODE + MP4", BONE, 18.0, "start"),
    "b": label(154.0, 900.0, BENCH_NOTE, GREY, 18.0, "start"),
    "c": label(
        154.0,
        940.0,
        "REPRODUCE: RENDER-BENCH/VS-REMOTION IN THE FFRAMES REPO",
        ORANGE,
        18.0,
        "start",
    ),
}


def table(l):
    items = []
    for i, (name, secs, color) in enumerate(TABLE_ROWS):
        at = F(0.3) + F(i) * F(0.5)
        y = F(520.0) + F(i) * F(130.0)
        items.append(
            TABLE_ROW(
                opacity=f(prog(l, at, at + F(0.08))),
                transform=f"translate({s32((F(1.0) - snap(l - at)) * F(80.0))} 0)",
                y_box=f(y - F(70.0)),
                color=color,
                y=f(y),
                name=text(name),
                secs=text(f"{float(secs):.3f} s"),
            )
        )
    return TABLE(
        opacity=f(F(1.0) - expo_in(prog(l, 9.6, 10.0))), title=NUMBERS.draw(l, 0.0, 120.0), items=items,
        **TABLE_LABELS,
    )  # fmt: skip


BENCH_FRAME = T('<g><image href="{grid}" x="0" y="0" width="1920" height="1080" />{body}</g>')


class BenchmarkScene(BeatScene):
    START, END = 96.0, 128.0

    def render_frame(self, frame, ctx):
        lb = self.lb(frame)
        if RESULT_AT <= lb < TABLE_AT:
            return result(lb - RESULT_AT)
        layer = GRID.draw(frame, {
            "uSpeed": 2.0, "uHorizon": 0.62, "uBright": 0.35, "uInk": GRID_INK, "uHot": ORANGE_C,
        })  # fmt: skip
        body = race(lb) if lb < RESULT_AT else table(lb - TABLE_AT)
        return BENCH_FRAME(grid=layer, body=body)


# --- 10 / PREVIEW: the native preview window playing this video in real time on the GPU

TAKEOVER = F(16.0)
TAKEOVER_ROWS = (
    ((("NO", 16.0), ("BROWSER", 17.0)), F(380.0), BONE, F(-1.0)),
    ((("AT", 18.0), ("ALL", 19.0)), F(690.0), ORANGE, F(1.0)),
    ((("ANYWHERE", 20.0),), F(1000.0), BONE, F(-1.0)),
)  # fmt: skip
WIN = (F(590.0), F(262.0), F(1180.0), F(660.8))
KEYS = (("SPACE", "PLAY / PAUSE"), ("H  L", "SEEK A SECOND"), ("J  K", "STEP A FRAME"))
PREVIEW_WINDOW = T("""
<g>
    <clipPath id="preview-win"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" /></clipPath>
    <rect x="{x}" y="{y_shadow}" width="{w}" height="{h}" rx="{r}" fill="#000000" opacity="{shadow}" filter="url(#preview-shadow)" />
    <g clip-path="url(#preview-win)">
        <image href="{img}" x="{x}" y="{y}" width="{w}" height="{h}" />
    </g>
    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="none" stroke="#3d3a35" stroke-width="1.5" opacity="{edge}" />
</g>
""")
PREVIEW_KEY = T("""
<g opacity="{opacity}" transform="{transform}">
    <rect x="150" y="{y_box}" width="120" height="54" rx="8" fill="#161514" stroke="{BONE}" stroke-opacity="0.5" stroke-width="1.5" />
    <text x="210" y="{y}" text-anchor="middle" font-family="{MONO}" font-weight="600" font-size="20" fill="{BONE}">{key}</text>
    <text x="290" y="{y}" font-family="{MONO}" font-weight="500" font-size="18" letter-spacing="2" fill="{GREY}">{what}</text>
</g>
""")
PREVIEW = T("""
<g opacity="{opacity}">
    <defs>
        <filter id="preview-shadow" x="-10%" y="-10%" width="120%" height="130%">
            <feGaussianBlur stdDeviation="24" />
        </filter>
    </defs>
    <image href="{grid}" x="0" y="0" width="1920" height="1080" />
    <g opacity="{side}">
        {watch}
        {live}
    </g>
    <g transform="{t}" opacity="{win_o}">{window}</g>
    <g opacity="{cmd}">
        <text x="150" y="330" font-family="{MONO}" font-weight="500" font-size="20" letter-spacing="3" fill="{GREY}">NATIVE PREVIEW WINDOW</text>
        <text x="150" y="380" font-family="{MONO}" font-weight="600" font-size="26" fill="{ORANGE}">$</text>
        <text x="180" y="380" font-family="{MONO}" font-weight="500" font-size="26" fill="{BONE}">cargo run -- preview</text>
        <text x="150" y="440" font-family="{MONO}" font-weight="500" font-size="20" letter-spacing="2" fill="{BONE}">GPU · WITH SOUND</text>
        <text x="150" y="472" font-family="{MONO}" font-weight="500" font-size="20" letter-spacing="2" fill="{BONE}">NO BROWSER, NO BUNDLER</text>
    </g>
    <g opacity="{side}">
        {keys}
        {realtime}
        {scrub}
    </g>
    {takeover}
</g>
""")
WATCH = Slam(150.0, 205.0, "WATCH IT", DISPLAY, 110.0, BONE)
LIVE = Slam(820.0, 205.0, "LIVE.", DISPLAY, 110.0, ORANGE)
TAKEOVER_FRAME = T(
    '<g><rect width="1920" height="1080" fill="#050505" opacity="{dim}" />{rows}</g>'
)


def takeover(lb):
    """NO BROWSER / AT ALL / ANYWHERE: rows that slam in word by word and drift apart."""
    l = lb - TAKEOVER
    if l < 0.0:
        return None
    rows = []
    for words, y, color, direction in TAKEOVER_ROWS:
        first = F(words[0][1]) - TAKEOVER
        shown = [w for w, at in words if lb >= F(at)]
        if not shown:
            rows.append(None)
            continue
        drift = direction * max(l - first, F(0.0)) * F(34.0)
        x = F(60.0) + drift + (F(-140.0) if direction > 0.0 else F(0.0))
        rows.append(
            GROUP(
                content=Slam(x, y, " ".join(shown), DISPLAY, 330.0, color).draw(
                    l - first, 0.0, 220.0
                )
            )
        )
    return TAKEOVER_FRAME(dim=f(prog(l, 0.0, 0.5) * F(0.6)), rows=rows)


class PreviewScene(BeatScene):
    START, END = 128.0, 160.0

    def render_frame(self, frame, ctx):
        lb = self.lb(frame)
        layer = GRID.draw(frame, {
            "uSpeed": 1.5, "uHorizon": 0.7, "uBright": 0.3, "uInk": GRID_INK, "uHot": ORANGE_C,
        })  # fmt: skip
        capture = clip_frame(frame, ctx, "preview_capture.mp4")
        full = expo_out(prog(lb, TAKEOVER, TAKEOVER + F(0.7)))
        x, y = lerp(WIN[0], 0.0, full), lerp(WIN[1], 0.0, full)
        w, h = lerp(WIN[2], 1920.0, full), lerp(WIN[3], 1075.2, full)
        radius = F(14.0) * (F(1.0) - full)
        enter = snap(lb - F(0.5))
        s = F(0.9) + F(0.1) * enter
        cx, cy = x + w / F(2.0), y + h / F(2.0)
        t = f"translate({s32(cx)} {s32(cy + (F(1.0) - enter) * F(120.0))}) scale({s32(s)}) translate({s32(-cx)} {s32(-cy)})"
        window = None
        if capture is not None:
            window = PREVIEW_WINDOW(
                x=f(x), y=f(y), w=f(w), h=f(h), r=f(radius), y_shadow=f(y + F(18.0)),
                shadow=f(F(0.55) * (F(1.0) - full)), img=capture, edge=f(F(1.0) - full),
            )  # fmt: skip
        keys = []
        for i, (key, what) in enumerate(KEYS):
            at = F(3.0) + F(i) * F(0.5)
            ky = F(560.0) + F(i) * F(78.0)
            keys.append(
                PREVIEW_KEY(
                    opacity=f(prog(lb, at, at + F(0.1))),
                    transform=f"translate({s32((F(1.0) - snap(lb - at)) * F(-60.0))} 0)",
                    y_box=f(ky - F(38.0)),
                    y=f(ky - F(3.0)),
                    key=text(key),
                    what=text(what),
                )
            )
        side = F(1.0) - prog(lb, TAKEOVER - F(0.2), TAKEOVER + F(0.1))
        return PREVIEW(
            opacity=f(F(1.0) - expo_in(prog(lb, 31.5, 32.0))), grid=layer, side=f(side),
            watch=WATCH.draw(lb, 0.0, 150.0), live=LIVE.draw(lb - F(1.0), 0.0, 150.0), t=t,
            win_o=f(prog(lb, 0.5, 0.6)), window=window, cmd=f(prog(lb, 2.0, 2.4) * side), keys=keys,
            realtime=callout(WIN[0] + F(720.0), WIN[1] + F(12.0), WIN[0] + F(720.0), 170.0,
                             "REAL-TIME, FRAME BY FRAME", ORANGE, prog(lb, 6.0, 6.8)),
            scrub=callout(WIN[0] + F(354.0), WIN[1] + F(630.0), 560.0, 975.0, "PLAY · SEEK · LOOP · SCRUB",
                          BONE, prog(lb, 8.0, 8.8)),
            takeover=takeover(lb),
        )  # fmt: skip


# --- 11 / AGENTS: the loop an agent runs while it makes a video, with real CLI output on the hits

# global beats of the stutter hits that bring in a new card
CARD_BEATS = (175.0, 179.0, 183.0, 187.0, 191.0, 195.0)
AGENT_NODES = ("WRITE", "TIMELINE", "INSPECT", "STRIP", "FRAME", "RENDER")
CARDS = (
    (1, "cargo run -- timeline", (
        ("1920x1080 @ 60 fps, 7650 frames (127.50s)", BONE), ("#0   PromptScene      0.00s..2.15s", GREY),
        ("#1   OriginScene      2.15s..16.70s", GREY), ("#2   CodeScene       16.70s..23.97s", GREY),
        ("#3   GpuScene        23.97s..27.60s", GREY), ("audio music.wav       0.000s..127.500s", ORANGE),
    )),
    (2, "cargo run -- inspect", (
        ("checked 540 frames: 13 findings", BONE), ("0 errors · 13 warnings: marquee rows and", GREY),
        ("type that overflows the canvas on purpose", GREY),
    )),
    (3, "cargo run -- strip all -n 30", ("strip_self.jpg", F(1.887))),
    (4, "cargo run -- frame Shader@2.7s", ("frame_self.jpg", F(1.778))),
    (0, "cargo run -- audio analyze", (
        ("integrated -14.1 LUFS, range 10.3 LU", BONE), ("true peak -1.2 dBTP, clipped samples 0", BONE),
        ("GpuScene        23.97s..27.60s   -13.0 LUFS", GREY), ("BenchmarkScene  45.78s..60.33s   -13.0 LUFS", GREY),
    )),
    (5, "cargo run -- render --draft", (("out.mp4 frames 0..7650 (0.00s..127.50s)", GREY), ("960x540 in 5.3s", ORANGE))),
)  # fmt: skip
RING_X, RING_Y, RING_R = F(1370.0), F(590.0), F(250.0)
CONTOUR_INK = ff.Color.hex("#8a857c")
RING_NODE = T("""
<g opacity="{opacity}">
    <rect x="{x}" y="{y}" width="{size}" height="{size}"
          fill="{fill}" stroke="{stroke}" stroke-width="2" />
    <text x="{lx}" y="{ly}" text-anchor="{anchor}" font-family="{MONO}" font-weight="600" font-size="22" letter-spacing="3"
          fill="{text_fill}">{name}</text>
</g>
""")
COMET = T('<circle cx="{x}" cy="{y}" r="{r}" fill="{ORANGE}" opacity="{o}" />')
RING = T("""
<g>
    <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{GREY}" stroke-width="1.5"
            stroke-dasharray="{dash}" transform="{rotate}" />
    <circle cx="{cx}" cy="{cy}" r="{r_in}" fill="none" stroke="{DIM}" stroke-width="1" stroke-dasharray="4 8" opacity="{draw}" />
    {comet}
    {nodes}
    <g opacity="{center}">
        <text x="{cx}" y="{y_a}" text-anchor="middle" font-family="{SERIF}" font-style="italic" font-size="64" fill="{BONE}">the agent</text>
        <text x="{cx}" y="{y_b}" text-anchor="middle" font-family="{MONO}" font-weight="500" font-size="18" letter-spacing="3" fill="{GREY}">NEVER WATCHES A VIDEO</text>
    </g>
</g>
""")
RING_ROTATE = f"rotate(-90 {s32(RING_X)} {s32(RING_Y)})"


def ring(lb, lit):
    draw = cubic_in_out(prog(lb, 2.0, 5.0))
    circ = TAU * RING_R
    nodes = []
    for i, name in enumerate(AGENT_NODES):
        a = -FRAC_PI_2 + F(i) / F(len(AGENT_NODES)) * TAU
        sa, ca = sin_cos32(a)
        x, y = RING_X + ca * RING_R, RING_Y + sa * RING_R
        at = F(2.5) + F(i) * F(0.4)
        s = snap(lb - at)
        on = lit == i
        size = F(18.0) + (F(8.0) if on else F(0.0))
        side = size * max(s, F(0.05))
        nodes.append(
            RING_NODE(
                opacity=f(prog(lb, at, at + F(0.1))),
                x=f(x - size / F(2.0)),
                y=f(y - size / F(2.0)),
                size=f(side),
                fill=ORANGE if on else BG,
                stroke=ORANGE if on else BONE,
                lx=f(RING_X + ca * (RING_R + F(44.0))),
                ly=f(RING_Y + sa * (RING_R + F(44.0)) + F(8.0)),
                anchor="start" if ca > 0.3 else ("end" if ca < -0.3 else "middle"),
                text_fill=ORANGE if on else BONE,
                name=text(name),
            )
        )
    comet = []
    if lb > 5.0:
        for k in range(10):
            a = -FRAC_PI_2 + ((lb - F(5.0)) / F(8.0) - F(k) * F(0.008)) * TAU
            sa, ca = sin_cos32(a)
            comet.append(
                COMET(
                    x=f(RING_X + ca * RING_R),
                    y=f(RING_Y + sa * RING_R),
                    r=f(F(7.0) - F(k) * F(0.5)),
                    o=f(F(1.0) - F(k) / F(10.0)),
                )
            )
    return RING(
        cx=f(RING_X), cy=f(RING_Y), r=f(RING_R), dash=f"{s32(circ * draw)} {s32(circ)}", rotate=RING_ROTATE,
        r_in=f(RING_R - F(30.0)), draw=f(draw), comet=comet, nodes=nodes, center=f(prog(lb, 4.0, 4.5)),
        y_a=f(RING_Y - F(6.0)), y_b=f(RING_Y + F(36.0)),
    )  # fmt: skip


CARD_LINE = T(
    '<text x="{x}" y="{y}" font-family="{MONO}" font-weight="500" font-size="23" fill="{fill}" opacity="{o}">{t}</text>'
)
CARD_IMAGE_BODY = T('<g opacity="{o}">{img}</g>')
CARD = T("""
<g opacity="{opacity}" transform="{transform}">
    <rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#0e0d0c" fill-opacity="0.92" stroke="#3d3a35" stroke-width="1.5" />
    <rect x="{x}" y="{y}" width="4" height="{h}" fill="{ORANGE}" />
    <text x="{x_text}" y="{y_cmd}" font-family="{MONO}" font-weight="600" font-size="25" fill="{ORANGE}">$</text>
    <text x="{x_cmd}" y="{y_cmd}" font-family="{MONO}" font-weight="500" font-size="25" fill="{BONE}">{command}</text>
    <rect x="{x_text}" y="{y_rule}" width="{w_rule}" height="1" fill="#3d3a35" />
    {body}
</g>
""")


def card(ctx, spec, l):
    """A terminal card: the command, then its output lines or image."""
    _node, command, body_spec = spec
    x, y, w = F(150.0), F(440.0), F(800.0)
    typed = usize(min((l / F(0.5)) * F(len(command)), F(len(command))))
    if isinstance(body_spec[0], str):
        name, aspect = body_spec
        iw = w - F(56.0)
        ih = iw / aspect
        img = ctx.image(name)
        img = (
            None
            if img is None
            else IMAGE(href=img, x=f(x + F(28.0)), y=f(y + F(84.0)), width=f(iw), height=f(ih))
        )
        body, h = CARD_IMAGE_BODY(o=f(prog(l, 0.45, 0.6)), img=img), F(84.0) + ih + F(28.0)
    else:
        rows = [
            CARD_LINE(x=f(x + F(28.0)), y=f(y + F(110.0) + F(i) * F(36.0)), fill=color,
                      o=f(prog(l, F(0.5) + F(i) * F(0.08), F(0.55) + F(i) * F(0.08))), t=text(line))
            for i, (line, color) in enumerate(body_spec)
        ]  # fmt: skip
        body, h = GROUP(content=rows), F(90.0) + F(len(body_spec)) * F(36.0) + F(20.0)
    return CARD(
        opacity=f(prog(l, 0.0, 0.08)), transform=f"translate({s32((F(1.0) - snap(l)) * F(-80.0))} 0)",
        x=f(x), y=f(y), w=f(w), h=f(h), x_text=f(x + F(28.0)), y_cmd=f(y + F(52.0)), x_cmd=f(x + F(58.0)),
        command=text(command[:typed]), y_rule=f(y + F(70.0)), w_rule=f(w - F(56.0)), body=body,
    )  # fmt: skip


CONFESSION = T("""
<g opacity="{opacity}" transform="{transform}">
    {a}
    {b}
    <text x="156" y="712" font-family="{SERIF}" font-style="italic" font-size="54" fill="{BONE}" opacity="{c}">in Rust, with fframes. No timeline editor was opened.</text>
</g>
""")
THIS_VIDEO = Slam(150.0, 470.0, "THIS VIDEO WAS", DISPLAY, 138.0, BONE)
MADE_BY = Slam(150.0, 630.0, "MADE BY AN AGENT.", DISPLAY, 138.0, ORANGE)


def confession(l):
    """THIS VIDEO WAS / MADE BY AN AGENT."""
    collapse = expo_in(prog(l, 7.3, 8.0))
    s = F(1.0) - collapse * F(0.15)
    return CONFESSION(
        opacity=f(F(1.0) - collapse), transform=f"translate(960 540) scale({s32(s)}) translate(-960 -540)",
        a=THIS_VIDEO.draw(l, 0.0, 160.0), b=MADE_BY.draw(l - F(1.0), 0.0, 160.0), c=f(prog(l, 3.0, 3.4)),
    )  # fmt: skip


PROMPT_CARD = T("""
<g opacity="{opacity}" transform="{transform}">
    <text x="150" y="480" font-family="{MONO}" font-weight="500" font-size="20" letter-spacing="3" fill="{GREY}">IT STARTS WITH A PROMPT</text>
    <rect x="150" y="510" width="800" height="150" fill="#0e0d0c" fill-opacity="0.92" stroke="{ORANGE}" stroke-width="2" />
    <text x="180" y="572" font-family="{MONO}" font-weight="600" font-size="32" fill="{ORANGE}">›</text>
    <text x="220" y="572" font-family="{MONO}" font-weight="500" font-size="32" fill="{BONE}">{first}</text>
    <text x="220" y="620" font-family="{MONO}" font-weight="500" font-size="32" fill="{BONE}">{second}</text>
</g>
""")


def prompt_card(l):
    """Before the first command: the prompt from the cold open, again."""
    if l < 0.0:
        return None
    shown = PROMPT[: usize(min((l / F(3.0)) * F(len(PROMPT)), F(len(PROMPT))))]
    first, second = (shown[:33], shown[33:]) if len(shown) > 33 else (shown, "")
    return PROMPT_CARD(
        opacity=f(prog(l, 0.0, 0.1)), transform=f"translate({s32((F(1.0) - snap(l)) * F(-80.0))} 0)",
        first=text(first), second=text(second),
    )  # fmt: skip


AGENTS = T("""
<g>
    {bg}
    <g opacity="{opacity}">
        <g transform="{t_a}" opacity="{o_a}">
            <text x="150" y="235" font-family="{DISPLAY}" font-size="110" letter-spacing="-4" fill="{BONE}">BUILT FOR THE</text>
        </g>
        <g transform="{t_b}" opacity="{o_b}">
            <text x="150" y="345" font-family="{DISPLAY}" font-size="110" letter-spacing="-4" fill="{ORANGE}">AGENTIC LOOP.</text>
        </g>
        {ring}
        {card}
    </g>
</g>
""")
LOCAL_CARDS = tuple(F(b) - F(160.0) for b in CARD_BEATS)
WELL = (f(RING_X / F(1920.0)), f(RING_Y / F(1080.0)))


class AgentsScene(BeatScene):
    START, END = 160.0, 208.0

    def render_frame(self, frame, ctx):
        lb = self.lb(frame)
        layer = CONTOUR.draw(frame, {
            "uWell": WELL, "uDepth": 0.9, "uDensity": 20.0, "uBright": f(F(0.3) * prog(lb, 0.0, 2.0)),
            "uInk": CONTOUR_INK, "uHot": ORANGE_C,
        })  # fmt: skip
        bg = FULL_IMAGE(href=layer)
        if lb >= 40.0:
            return GROUP(content=[bg, confession(lb - F(40.0))])
        active = next((i for i in reversed(range(len(LOCAL_CARDS))) if lb >= LOCAL_CARDS[i]), None)
        if active is None:
            card_svg, lit = prompt_card(lb - F(6.0)), None
        else:
            card_svg, lit = card(ctx, CARDS[active], lb - LOCAL_CARDS[active]), CARDS[active][0]
        return AGENTS(
            bg=bg, opacity=f(F(1.0) - expo_in(prog(lb, 39.6, 40.0))),
            t_a=f"translate(0 {s32((F(1.0) - snap(lb)) * F(60.0))})", o_a=f(prog(lb, 0.0, 0.1)),
            t_b=f"translate(0 {s32((F(1.0) - snap(lb - F(1.5))) * F(60.0))})", o_b=f(prog(lb, 1.5, 1.6)),
            ring=ring(lb, lit), card=card_svg,
        )  # fmt: skip


RENDER_CARD = T(
    '<g opacity="{o}"><image href="{img}" x="{x}" y="{y}" width="{w}" height="{h}" />'
    '<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="{BONE}" stroke-opacity="0.35" stroke-width="1" /></g>'
)
RENDER = T("""
<g opacity="{opacity}">
    <image href="{grid}" x="0" y="0" width="1920" height="1080" />
    {cards}
    <rect x="0" y="600" width="1920" height="480" fill="url(#render-fade)" />
    <defs>
        <linearGradient id="render-fade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#0b0b0b" stop-opacity="0" />
            <stop offset="1" stop-color="#0b0b0b" stop-opacity="0.9" />
        </linearGradient>
    </defs>
    <g transform="{t_title}" opacity="{o_title}">
        <rect x="120" y="120" width="{title_w}" height="150" fill="{ORANGE}" />
        <text x="150" y="232" font-family="{DISPLAY}" font-size="120" letter-spacing="-4" fill="{INK}">THIS VIDEO.</text>
    </g>
    <g transform="{t_a}" opacity="{o_a}">
        <text x="150" y="820" font-family="{DISPLAY}" font-size="190" letter-spacing="-8" fill="{BONE}">{count}</text>
        <text x="160" y="880" font-family="{MONO}" font-weight="600" font-size="30" letter-spacing="6" fill="{BONE}">FRAMES · 1920×1080 · 60 FPS</text>
    </g>
    <g transform="{t_b}" opacity="{o_b}">
        <text x="1770" y="820" text-anchor="end" font-family="{DISPLAY}" font-size="190" letter-spacing="-8" fill="{ORANGE}">{secs}</text>
        <text x="1770" y="880" text-anchor="end" font-family="{MONO}" font-weight="600" font-size="30" letter-spacing="6" fill="{BONE}">TO RENDER · SKIA ON METAL</text>
    </g>
    <g opacity="{c}">
        <rect x="1330" y="170" width="440" height="64" fill="{ORANGE}" />
        <text x="1550" y="214" text-anchor="middle" font-family="{MONO}" font-weight="700" font-size="30" letter-spacing="3" fill="{INK}">{realtime}</text>
    </g>
</g>
""")
REALTIME = TOTAL_SECONDS / RENDER_SECONDS if RENDER_SECONDS > 0.0 else F(0.0)


class RenderScene(BeatScene):
    """The second drop: frames of this video fly out of the grid, next to their render time."""

    START, END = 208.0, 224.0
    THUMBS = 10

    def render_frame(self, frame, ctx):
        lb = self.lb(frame)
        layer = GRID.draw(frame, {
            "uSpeed": 6.0, "uHorizon": 0.5, "uBright": f(F(0.9) + pulse(lb, 6.0) * F(0.4)),
            "uInk": GRID_INK, "uHot": ORANGE_C,
        })  # fmt: skip
        t = lb * BEAT
        cards = []
        for k in range(14):
            phase = fract(t * F(0.45) + F(k) / F(14.0))
            z = lerp(7.0, 0.35, phase)
            side = F(-1.0) if k % 2 == 0 else F(1.0)
            xw = side * (F(620.0) + hash32(F(k) * F(3.1)) * F(520.0))
            yw = F(-330.0) + hash32(F(k) * F(7.7)) * F(300.0)
            x, y = F(960.0) + xw / z, F(540.0) + yw / z
            w = F(520.0) / z
            h = w * F(9.0) / F(16.0)
            o = prog(phase, 0.0, 0.2) * (F(1.0) - prog(phase, 0.85, 1.0)) * prog(lb, 0.0, 0.3)
            img = ctx.image(f"fly_{k % self.THUMBS}.jpg")
            if img is not None:
                card_svg = RENDER_CARD(
                    o=f(o), img=img, x=f(x - w / F(2.0)), y=f(y - h / F(2.0)), w=f(w), h=f(h)
                )
                cards.append((z, card_svg))
        cards.sort(key=lambda c: -c[0])
        title_w = F(measure(frame, ctx, DISPLAY, 120, 400, False, "THIS VIDEO.")) - F(44.0)
        count = round_u(F(FRAMES) * expo_out(prog(lb, 0.0, 3.0)))
        secs = RENDER_SECONDS * expo_out(prog(lb, 4.0, 6.0))
        return RENDER(
            opacity=f(F(1.0) - expo_in(prog(lb, 15.7, 16.0))), grid=layer, cards=[c for _, c in cards],
            t_title=f"translate({s32((F(1.0) - snap(lb - F(0.5))) * F(-200.0))} 0)", o_title=f(prog(lb, 0.5, 0.6)),
            title_w=f(title_w + F(60.0)),
            t_a=f"translate(0 {s32((F(1.0) - snap(lb)) * F(70.0))})", o_a=f(prog(lb, 0.0, 0.08)),
            count=text(thousands(count)),
            t_b=f"translate(0 {s32((F(1.0) - snap(lb - F(4.0))) * F(70.0))})", o_b=f(prog(lb, 4.0, 4.08)),
            secs=text(f"{float(secs):.1f}s"), c=f(prog(lb, 8.0, 8.3)), realtime=text(f"{float(REALTIME):.1f}× REAL TIME"),
        )  # fmt: skip


RECAP_WORDS = ("TEXT", "IMAGES", "VIDEO", "SHADERS", "AUDIO", "GPU", "EFFECTS", "AGENTS")
RECAP_WORD = T("""
<g>
    <rect width="1920" height="1080" fill="{bg}" />
    <g transform="{transform}">
        <text x="960" y="690" text-anchor="middle" font-family="{DISPLAY}" font-size="360" letter-spacing="-16" fill="{fg}">{word}</text>
    </g>
    <text x="150" y="200" font-family="{MONO}" font-weight="600" font-size="30" letter-spacing="6" fill="{fg}">{n}</text>
    <text x="1770" y="200" text-anchor="end" font-family="{MONO}" font-weight="600" font-size="30" letter-spacing="6" fill="{fg}">/ 08</text>
</g>
""")
RECAP_END = T('<g opacity="{opacity}"><rect width="1920" height="1080" fill="{BG}" />{a}{b}</g>')
RECAP_SLAM_A = Slam(960.0, 520.0, "ALL OF IT.", DISPLAY, 220.0, BONE).anchored("middle")
RECAP_SLAM_B = Slam(960.0, 760.0, "in Rust.", SERIF, 220.0, ORANGE).anchored("middle").italicized()


class RecapScene(BeatScene):
    """One word per beat on alternating full-bleed colors."""

    START, END = 224.0, 236.0

    def render_frame(self, frame, ctx):
        lb = self.lb(frame)
        i = math.floor(max(float(lb), 0.0))
        local = lb - F(i)
        if i < len(RECAP_WORDS):
            bg, fg = ((ORANGE, INK), (BG, BONE), (PAPER, INK))[i % 3]
            punch = F(1.0) + (F(1.0) - expo_out(local / F(0.4))) * F(0.12)
            return RECAP_WORD(
                bg=bg, fg=fg, transform=f"translate(960 560) scale({s32(punch)}) translate(-960 -560)",
                word=text(RECAP_WORDS[i]), n=text(f"{i + 1:02}"),
            )  # fmt: skip
        l = lb - F(8.0)
        return RECAP_END(
            opacity=f(F(1.0) - expo_in(prog(l, 3.7, 4.0))),
            a=RECAP_SLAM_A.draw(l, 0.0, 170.0), b=RECAP_SLAM_B.draw(l - F(2.0), 0.0, 170.0),
        )  # fmt: skip


DONE_COMMAND = "cargo fframes new my-video"
DONE = T("""
<g>
    <rect width="1920" height="1080" fill="#050505" />
    <text x="{x0}" y="555" font-family="{MONO}" font-weight="600" font-size="40" fill="{ORANGE}">$</text>
    <text x="{x1}" y="555" font-family="{MONO}" font-weight="500" font-size="40" fill="{BONE}">{shown}</text>
    <rect x="{caret_x}" y="522" width="20" height="44" fill="{ORANGE}" opacity="{caret}" />
</g>
""")


class DoneScene(BeatScene):
    """The silent bar: only a command being typed."""

    START, END = 236.0, 240.0

    def render_frame(self, frame, ctx):
        lb = self.lb(frame)
        n = F(len(DONE_COMMAND))
        typed = int(prog(lb, 0.2, 3.2) * n)
        # text is centered on the full command so it does not shift while typing
        adv = F(40.0) * F(0.6)
        x0 = F(960.0) - (n + F(2.0)) * adv / F(2.0)
        caret_x = x0 + (F(2.0) + F(typed)) * adv
        caret_on = (F(typed) >= n and fract(lb * F(2.0)) > 0.5) or F(typed) < n
        return DONE(
            x0=f(x0), x1=f(x0 + F(2.0) * adv), shown=text(DONE_COMMAND[:typed]),
            caret_x=f(caret_x + F(2.0)), caret=1.0 if caret_on else 0.0,
        )  # fmt: skip


OUTRO_WORD_SIZE = 300
OUTRO_INK = ff.Color.hex("#8a857c")
OUTRO_ECHO = T(
    '<text x="{x}" y="{y}" font-family="{SERIF}" font-style="italic" font-size="{size}" fill="{color}" opacity="{o}">f</text>'
)
OUTRO_CMD = T("""
<g opacity="{opacity}" transform="{transform}">
    <rect x="400" y="{ry}" width="1120" height="62" fill="#0f0e0d" fill-opacity="0.9" stroke="#3d3a35" stroke-width="1.5" />
    <text x="428" y="{y}" font-family="{MONO}" font-weight="600" font-size="26" fill="{ORANGE}">$</text>
    <text x="458" y="{y}" font-family="{MONO}" font-weight="500" font-size="26" fill="{BONE}">{cmd}</text>
    <text x="1500" y="{y}" text-anchor="end" font-family="{MONO}" font-weight="500" font-size="15" letter-spacing="2" fill="{GREY}">{note}</text>
</g>
""")
OUTRO_CMDS = (
    ("npx skills add https://fframes.studio", "WITH YOUR CODING AGENT"),
    ("cargo fframes new my-video", "OR BY HAND"),
)
OUTRO = T("""
<g>
    <image href="{bg}" x="0" y="0" width="1920" height="1080" />
    <g opacity="{visible}">
        {echoes}
        <g transform="{word_t}" opacity="{word_o}">
            <text x="{x0}" y="{y}" font-family="{SERIF}" font-style="italic" font-size="{size}" fill="{BONE}">fframes</text>
        </g>
        <text x="1470" y="265" text-anchor="end" font-family="{MONO}" font-weight="500" font-size="28" letter-spacing="2" fill="{GREY}" opacity="{tag}">{release}</text>
        <text x="960" y="590" text-anchor="middle" font-family="{MONO}" font-weight="500" font-size="30" letter-spacing="2" fill="{BONE}" opacity="{tag}">video vibe coding framework that is actually fast</text>
        {cmd_rows}
        <g opacity="{url}">
            <text x="960" y="990" text-anchor="middle" font-family="{MONO}" font-weight="600" font-size="26" letter-spacing="3" fill="{ORANGE}">GITHUB.COM/DMTRKOVALENKO/FFRAMES</text>
        </g>
    </g>
    <rect width="1920" height="1080" fill="{BONE}" opacity="{flash}" />
    <rect width="1920" height="1080" fill="#000000" opacity="{fade_out}" />
</g>
""")


class OutroScene(BeatScene):
    """The fframes wordmark slams in with its trail of f's, then the install commands."""

    START, END = 240.0, None

    def render_frame(self, frame, ctx):
        lb = self.lb(frame)
        fade_out = prog(F(1.6) - (TOTAL_SECONDS - gsec(frame)), 0.0, 1.6)
        layer = CONTOUR.draw(frame, {
            "uWell": (0.5, 0.47), "uDepth": 1.1, "uDensity": 18.0,
            "uBright": f(F(0.25) + F(0.5) * (F(1.0) - expo_out(prog(lb, 0.0, 6.0)))),
            "uInk": OUTRO_INK, "uHot": ORANGE_C,
        })  # fmt: skip
        w = F(measure(frame, ctx, SERIF, OUTRO_WORD_SIZE, 400, True, "fframes"))
        fw = F(measure(frame, ctx, SERIF, OUTRO_WORD_SIZE, 400, True, "f"))
        # the trail makes the whole mark wider: center mark + trail
        trail = F(3.0)
        step = fw * F(0.78)
        x0 = F(960.0) - (w + step * trail) / F(2.0) + step * trail
        y = F(520.0)
        echoes = []
        for k in (2, 1, 0):
            s = soft(lb - F(0.5) - F(k) * F(0.5))
            dx = -step * (F(k) + F(1.0)) * s
            o = F(min(max(float(s), 0.0), 1.0)) * (F(1.0) - F(k) * F(0.18))
            color = (ORANGE, "#c4531c", EMBER)[k]
            echoes.append(
                OUTRO_ECHO(x=f(x0 + dx), y=f(y), size=OUTRO_WORD_SIZE, color=color, o=f(o))
            )
        cmd_rows = []
        for i, (cmd, note) in enumerate(OUTRO_CMDS):
            at = F(8.0) + F(i) * F(1.0)
            ry = F(760.0) + F(i) * F(78.0)
            cmd_rows.append(OUTRO_CMD(
                opacity=f(prog(lb, at, at + F(0.1))), transform=f"translate(0 {s32((F(1.0) - snap(lb - at)) * F(30.0))})",
                ry=f(ry - F(44.0)), y=f(ry), cmd=text(cmd), note=text(note),
            ))  # fmt: skip
        word_s = F(1.0) + (F(1.0) - expo_out(lb / F(0.5))) * F(0.25)
        tag = f(prog(lb, 4.0, 4.6))
        return OUTRO(
            bg=layer, visible=f(F(1.0) - fade_out), echoes=echoes,
            word_t=f"translate(960 {s32(y)}) scale({s32(word_s)}) translate(-960 -{s32(y)})",
            word_o=f(min(spring(lb * BEAT, 260.0, 20.0), F(1.0))), x0=f(x0), y=f(y), size=OUTRO_WORD_SIZE,
            tag=tag, release=text(RELEASE_LABEL), cmd_rows=cmd_rows, url=f(prog(lb, 12.0, 12.5)),
            flash=f(exp32(-lb * F(9.0))), fade_out=f(fade_out),
        )  # fmt: skip


SCENES = (
    PromptScene, OriginScene, CodeScene, GpuScene, TextScene, ImageScene, VideoScene, ShaderScene, ScaleScene, BenchmarkScene, PreviewScene, AgentsScene, RenderScene, RecapScene, DoneScene, OutroScene,
)  # fmt: skip


# --- the video: the beat-grid scenes under a pumping, glitching, flashing frame and a HUD

SECTIONS = (
    (-99.0, "00 / PROMPT"), (0.0, "01 / ORIGIN"), (32.0, "02 / CODE"), (48.0, "03 / GPU"),
    (56.0, "04 / TEXT"), (62.0, "05 / IMAGE"), (66.0, "06 / VIDEO"), (72.0, "07 / SHADER"),
    (80.0, "08 / SCALE"), (96.0, "09 / BENCHMARK"), (128.0, "10 / PREVIEW"),
    (160.0, "11 / AGENTS"), (208.0, "12 / GPU"), (224.0, "13 / RECAP"), (236.0, "14 / DONE"),
    (240.0, "15 / FFRAMES"),
)  # fmt: skip
PUMPING = ((48.0, 80.0), (96.0, 160.0), (208.0, 236.0), (240.0, 268.0))
GLITCH_CUTS = (32.0, 56.0, 62.0, 66.0, 72.0, 80.0, 128.0, 144.0, 224.0)
DROPS = (48.0, 96.0, 144.0, 208.0)


def sfx(name, at, gain):
    """A sound effect placed on the beat minus the file's attack."""
    return ff.AudioTrack(name, f(max(F(at), F(0.0))), ff.Timestamp.EOF).gain_db(gain)


def audio_tracks():
    tracks = [
        ff.AudioTrack("music.wav", 0.0, ff.Timestamp.EOF).fade_out(1.5),
        sfx("sfx_typing.mp3", 0.02, -15.0),
        sfx("sfx_enter.mp3", beat_time(-1.0) - F(0.067), -9.0),
        sfx("sfx_impact.mp3", beat_time(48.0), -10.0),
        sfx("sfx_shutter.mp3", beat_time(62.0) - F(0.02), -2.0),
        sfx("sfx_glitch.mp3", beat_time(70.0) - F(0.2), -8.0),
        sfx("sfx_impact.mp3", beat_time(96.0), -10.0),
        sfx("sfx_impact.mp3", beat_time(144.0), -12.0),
        sfx("sfx_impact.mp3", beat_time(208.0), -11.0),
        sfx("sfx_typing.mp3", beat_time(236.2), -18.0),
        sfx("sfx_impact.mp3", beat_time(240.0), -7.0),
        sfx("sfx_braam.mp3", beat_time(240.0), -9.0),
    ]
    tracks += [
        sfx("sfx_whoosh.mp3", beat_time(b) - F(0.18), -15.0)
        for b in (56.0, 62.0, 66.0, 72.0, 80.0, 128.0, 160.0, 224.0)
    ]
    tracks += [sfx("sfx_blip.mp3", beat_time(b), -9.0) for b in CARD_BEATS]
    return tracks


HUD = T("""
<g opacity="{appear}" style="mix-blend-mode:difference">
    {corners}
    {title}
    {bpm}
    <rect x="1840" y="92" width="14" height="14" fill="{ORANGE}" opacity="{tick}" />
    {tc}
    {fnum}
    {section}
</g>
""")
HUD_CORNERS = corners(36.0, 36.0, 1848.0, 1008.0, 26.0, "#d8d4cc", 2.0)
HUD_TITLE = label(66.0, 78.0, "FFRAMES — INTRO", "#d8d4cc", 17.0, "start")


def hud(frame, b):
    """The HUD sits out the silent bar and the logo slam."""
    appear = prog(gsec(frame), 0.1, 0.5)
    if 236.0 <= b < 244.0 or appear <= 0.0:
        return None
    section = next((name for start, name in reversed(SECTIONS) if b >= F(start)), "")
    bar = 0 if b < 0.0 else math.floor(b / F(4.0)) + 1
    beat_in_bar = 0 if b < 0.0 else math.floor(rem_euclid(b, F(4.0))) + 1
    tick = F(0.0) if b < 0.0 else pulse(b, 7.0)
    return HUD(
        appear=f(appear * F(0.9)), corners=HUD_CORNERS, title=HUD_TITLE,
        bpm=label(1854.0, 78.0, f"132 BPM   BAR {bar:03}.{beat_in_bar}", "#d8d4cc", 17.0, "end"),
        tick=f(F(0.25) + tick * F(0.75)),
        tc=label(66.0, 1018.0, timecode(gsec(frame)), "#d8d4cc", 17.0, "start"),
        fnum=label(290.0, 1018.0, f"F {frame.global_index:05}", "#77736d", 17.0, "start"),
        section=label(1854.0, 1018.0, section, "#d8d4cc", 17.0, "end"),
    )  # fmt: skip


GLITCH_BAND = T("""
<g>
    <clipPath id="{id}"><rect x="0" y="{y}" width="1920" height="180" /></clipPath>
    <g clip-path="{url}" transform="{transform}">{scene}</g>
</g>
""")
ENERGY = T("""
<g>
    <g transform="{transform}">{scene}</g>
    <rect width="1920" height="1080" fill="{BONE}" opacity="{flash}" />
</g>
""")


def energy(frame, ctx, b):
    pumping = any(F(s) <= b < F(e) for s, e in PUMPING)
    pump = pulse(b, 9.0) if pumping else F(0.0)
    s = F(1.0) + pump * F(0.008)
    flash = F(0.0)
    for d in DROPS:
        if b >= F(d):
            flash = max(flash, exp32(-(b - F(d)) * F(7.0)))
    since_cut = next(
        (x for x in ((b - F(c)) * BEAT * F(FPS) for c in GLITCH_CUTS) if 0.0 <= x < 3.0), None
    )
    if since_cut is not None:
        bands = []
        for i in range(6):
            dx = (hash32(F(i) * F(13.0) + F(math.floor(since_cut)) * F(7.0)) - F(0.5)) * F(140.0)
            dx = dx * (F(1.0) - since_cut / F(3.0))
            bands.append(
                GLITCH_BAND(
                    id=f"glitch-{i}",
                    y=f(F(i) * F(180.0)),
                    url=f"url(#glitch-{i})",
                    transform=f"translate({s32(dx)} 0)",
                    scene=ctx.render_scenes(frame),
                )
            )
        scene = GROUP(content=bands)
    else:
        scene = ctx.render_scenes(frame)
    return ENERGY(
        transform=f"translate(960 540) scale({s32(s)}) translate(-960 -540)", scene=scene,
        flash=f(flash * F(0.55)),
    )  # fmt: skip


INTRO = T("""
<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
    <rect width="1920" height="1080" fill="{BG}" />
    {energy}
    <image href="{grain}" x="0" y="0" width="1920" height="1080" />
    {hud}
</svg>
""")


class IntroVideo:
    fps = FPS
    width = 1920
    height = 1080
    background_color = ff.Color.BLACK
    duration = ff.Duration.AUTO

    def __init__(self):
        self.audio = audio_tracks()
        self.scenes = [scene() for scene in SCENES]

    def render_frame(self, frame, ctx):
        b = gbeat(frame)
        grain = GRAIN.draw(frame, {"uGrain": 0.07, "uVignette": 0.55})
        return INTRO(energy=energy(frame, ctx, b), grain=grain, hud=hud(frame, b))


def main() -> int:
    return ff.cli(
        IntroVideo(),
        media=ff.Media(_media.folder(EXAMPLE), _media.folder(EXAMPLE, "dynamic_media")),
        codec_params={"crf": "16", "preset": "medium", "tune": "film"},
        master_gain_db=3.5,
        limiter={"ceiling_db": -1.3},
        renderer="gpu",
        gpu_contexts="max",
    )


if __name__ == "__main__":
    sys.exit(main())
