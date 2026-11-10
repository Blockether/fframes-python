"""The clock of the video. The music runs at 120 BPM, so one beat is 30 frames. Every cut, pop
and keystroke is on this beat grid. `soundtrack.py` reads the same constants, so the sound
follows the picture. Values are f32, like in the Rust example."""

import numpy as np

F = np.float32

FPS = 60
BEAT = F(0.5)
FRAMES_PER_BEAT = 30

# First beat of each scene.
HOOK = F(0.0)
GRID = F(8.0)
CODE = F(16.0)
ZOOM = F(24.0)
OUTRO = F(28.0)
END = F(36.0)

# "NOW PLAYS" comes on beat 1, with its words 50 ms apart. The letters of "LOTTIE" come on
# beat 2, 30 ms apart.
WORD_NOW = F(1.0)
WORD_PLAYS = F(1.1)
LETTERS = F(2.0)
LETTER_STEP = F(0.06)

# The tiles of the grid pop on sixteenth notes (125 ms apart).
TILE_POP = GRID + F(0.5)
TILE_STEP = F(0.25)
TILES = 12

# The code types from TYPE_START, CHARS_PER_BEAT characters per beat.
TYPE_START = CODE + F(0.5)
CHARS_PER_BEAT = F(30.0)
# "one call." comes after the code and stays 2 s.
CAPTION = CODE + F(4.0)

# The outro types the `features = ["lottie"]` line from this beat.
FEATURE_TYPE_START = OUTRO + F(1.0)
FEATURE_CHARS_PER_BEAT = F(16.0)


def beat_time(beat) -> np.float32:
    return F(beat) * BEAT


def beat_frames(beats) -> int:
    return round(float(F(beats) * F(FRAMES_PER_BEAT)))


def global_beat(frame) -> np.float32:
    """Position on the beat grid of the whole video."""
    return F(frame.global_index) / F(FRAMES_PER_BEAT)


PLAIN, PUNCT, METHOD, STR, TYPE, KEY = range(6)

# The code of the code scene, line by line. Leading spaces are the indentation.
CODE_LINES = [
    [
        ("frame", PLAIN),
        (".", PUNCT),
        ("play_lottie", METHOD),
        ("(", PUNCT),
        ("ctx", PLAIN),
        (", ", PUNCT),
        ('"tiger.json"', STR),
        (",", PUNCT),
    ],
    [("    ", PLAIN), ("LottieOptions", TYPE), (" {", PUNCT)],
    [("        ", PLAIN), ("looping", PLAIN), (": ", PUNCT), ("true", KEY), (",", PUNCT)],
    [
        ("        ", PLAIN),
        ("..", PUNCT),
        ("Default", TYPE),
        ("::", PUNCT),
        ("default", METHOD),
        ("()", PUNCT),
    ],
    [("    ", PLAIN), ("})", PUNCT)],
]


def code_chars() -> int:
    """Characters typed in the code scene, indentation excluded."""
    return sum(
        len(text.lstrip()) if column == 0 else len(text)
        for line in CODE_LINES
        for column, (text, _) in enumerate(line)
    )


FEATURE_LINE = 'features = ["lottie"]'


def key_beats() -> list[np.float32]:
    """The beats of the keystrokes, for the typing sound."""
    code = [TYPE_START + F(i) / CHARS_PER_BEAT for i in range(code_chars())]
    feature = [FEATURE_TYPE_START + F(i) / FEATURE_CHARS_PER_BEAT for i in range(len(FEATURE_LINE))]
    return code + feature
