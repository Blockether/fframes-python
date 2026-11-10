"""Port of fframes/examples/fframes-intro: a 128 second introduction to fframes, made with fframes.

Everything sits on the beat grid of the soundtrack (see _fframes_intro_ui.py). Needs the media of
fframes/examples/fframes-intro (fonts, images, music, sound effects and clips).

python examples/fframes_intro.py timeline
python examples/fframes_intro.py render -o fframes-intro.mp4
"""

import math
import subprocess
import sys
import tomllib

import _media
import fframes as ff
import numpy as np
from _fframes_intro_ui import (
    BEAT, BG, BONE, COND, DIM, DISPLAY, EMBER, FPS, GREY, INK, MONO, ORANGE, PAPER, SERIF,
    TOTAL_SECONDS, F, Slam, T, beat_time, callout, corners, cubic_in_out, exp32, expo_in,
    expo_out, fract, gbeat, gsec, hash32, hash_array, label, lerp, letters, measure, prog,
    pulse, quart_out, rem_euclid, s32, snap, soft, span_frames, spring, text, thousands,
    timecode, usize,
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


def sin32(x):
    return F(math.sin(float(x)))


def cos32(x):
    return F(math.cos(float(x)))


def powf(x, y):
    return F(float(x) ** float(y))


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
                    o=f(prog(t, at, at + F(0.06))), marker=marker, x=200.0 if call else 236.0,
                    y=f(y), text=text(line),
                )  # fmt: skip
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
            return F(0.0), (F(1.0) - s) * F(160.0), prog(lb, i, F(i) + F(0.15)), F(0.85) + F(0.15) * s

        year = letters(frame, ctx, 150.0, 690.0, date[:4] or "2021", DISPLAY, 440, 400, BONE, -8.0, digit)
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
        first = int(math.floor(pos)) - 11
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
                    o=f(o), y=f(y), hash_fill=ORANGE if is_current else "#6d4a36", hash=text(hash_),
                    date=text(date), text_fill=BONE if is_current else "#8f8a82", msg=text(msg),
                )  # fmt: skip
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
    return SILENCE(o=f(prog(l, 0.0, 0.2)), x=f(F(960.0) - F(30.0) * w), w=f(max(F(60.0) * w, F(0.5))))


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
                        spans.append(CODE_SPAN(x=f(CODE_X + F(col + lead) * ADV), y=f(y), size=f(CODE_SIZE), fill=color, text=text(part)))
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
                fill=ORANGE if hot else "#121110", stroke=ORANGE if hot else "#5a564f",
                name_fill=INK if hot else BONE, name=text(name), sub_fill=INK if hot else GREY, sub=text(sub),
            )  # fmt: skip
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
LIT_COPY = T('<text x="{x}" y="{y}" font-family="{COND}" font-size="{size}" fill="{ORANGE}">{t}</text>')
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
        lit = (int(math.floor(max(lb, F(0.0)))) * 3 + 1) % len(TEXT_ROWS)
        rows = []
        for i, value in enumerate(TEXT_ROWS):
            w = measure(frame, ctx, COND, TEXT_SIZE, 400, False, value)
            direction = F(-1.0) if i % 2 == 0 else F(1.0)
            speed = F(260.0) + F(math.fmod(float(F(i) * F(37.0)), 140.0))
            enter = expo_out(prog(lb, F(i) * F(0.05), F(0.6) + F(i) * F(0.05)))
            offset = rem_euclid(lb * BEAT * speed * direction, w) - w + (F(1.0) - enter) * F(900.0) * direction
            y = f(F(150.0) + F(i) * ROW_H)
            is_lit = i == lit
            flash = pulse(lb, 5.0) if is_lit else F(0.0)
            copy = LIT_COPY if is_lit else DIM_COPY
            copies = [copy(x=f(offset + F(k) * w), y=y, size=TEXT_SIZE, t=text(value)) for k in range(4)]
            rows.append(TEXT_ROW(o=f(F(0.7) + flash * F(0.3)), copies=copies))
        return TEXT_WALL(opacity=f(F(1.0) - exit_), rows=rows, number=TEXT_NUMBER, caption=TEXT_CAPTION)


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
        left_img = None if left is None else IMAGE(href=left, x=f(lx), y=f(ly), width=f(lw), height=f(lh))
        if keyed:
            flicker = (1.0 if hash32(lb * F(211.0)) > 0.5 else 0.0) if lb < 4.25 else 1.0
            right_img = KEYED_RIGHT(
                x=f(rx), y=f(ry), w=f(rw), h=f(rh), tunnel=tunnel(frame, 3.0, 1.0), flicker=flicker,
                guest=keyed_guest(frame, ctx, RIGHT, 0.0, 1.0),
            )  # fmt: skip
        else:
            right_img = None if right is None else IMAGE(href=right, x=f(rx), y=f(ry), width=f(rw), height=f(rh))
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
SOURCE_LINE = T('<text x="150" y="{y}" font-family="{MONO}" font-size="17" fill="#d8d0c4" opacity="{o}">{t}</text>')
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
SHADER_CAPTION = label(140.0, 935.0, "TUNNEL.SKSL · RAYMARCHED · 80 STEPS/PIXEL", ORANGE, 18.0, "start")
SHADER_NUMBER = label(154.0, 110.0, "04", ORANGE, 26.0, "start")


class ShaderScene(BeatScene):
    START, END = 72.0, 80.0

    def render_frame(self, frame, ctx):
        lb = self.lb(frame)
        open_ = expo_out(prog(lb, 0.0, 1.0))
        rx, ry, rw, rh = RIGHT
        guest_rect = (lerp(rx, 860.0, open_), lerp(ry, 150.0, open_), lerp(rw, 1280.0, open_), lerp(rh, 720.0, open_))
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
WALL_NODE = T('<text x="{x}" y="{y}" font-family="{MONO}" font-size="13" font-weight="500" fill="{fill}">{word}</text>')
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
WALL_FRAMES = label(150.0, 940.0, f"ONE FRAME = {thousands(100_000)} TEXT NODES  ×  300 FRAMES", GREY, 20.0, "start")


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


# --- STUB scenes (to be ported)
_EMPTY = T("<g></g>")


def _stub(name, start, end):
    return type(name, (BeatScene,), {"START": start, "END": end, "render_frame": lambda self, frame, ctx: _EMPTY()})


BenchmarkScene = _stub("BenchmarkScene", 96.0, 128.0)
PreviewScene = _stub("PreviewScene", 128.0, 160.0)
AgentsScene = _stub("AgentsScene", 160.0, 208.0)
RenderScene = _stub("RenderScene", 208.0, 224.0)
RecapScene = _stub("RecapScene", 224.0, 236.0)
DoneScene = _stub("DoneScene", 236.0, 240.0)
OutroScene = _stub("OutroScene", 240.0, None)

SCENES = (
    PromptScene, OriginScene, CodeScene, GpuScene, TextScene, ImageScene, VideoScene, ShaderScene, ScaleScene, BenchmarkScene, PreviewScene, AgentsScene, RenderScene, RecapScene, DoneScene, OutroScene,
)  # fmt: skip


# --- the video: the beat-grid scenes under a pumping, glitching, flashing frame and a HUD

CARD_BEATS = (175.0, 179.0, 183.0, 187.0, 191.0, 195.0)
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
    tracks += [sfx("sfx_whoosh.mp3", beat_time(b) - F(0.18), -15.0) for b in (56.0, 62.0, 66.0, 72.0, 80.0, 128.0, 160.0, 224.0)]
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
    bar = 0 if b < 0.0 else int(math.floor(b / F(4.0))) + 1
    beat_in_bar = 0 if b < 0.0 else int(math.floor(rem_euclid(b, F(4.0)))) + 1
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
                    id=f"glitch-{i}", y=f(F(i) * F(180.0)), url=f"url(#glitch-{i})",
                    transform=f"translate({s32(dx)} 0)", scene=ctx.render_scenes(frame),
                )  # fmt: skip
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
