"""Extracts the static low-poly artwork of the upstream low-poly-art example.

python tools/convert_low_poly_art.py [FFRAMES_DIR]

Writes examples/low_poly_art/owl.svg: the `<svg viewBox="0 0 2560 3840">` element of
`src/low_poly_art/owl.rs`. That element has no Rust expressions, so it is copied as is. The
example renders only the owl; the other animals are unused upstream.
"""

import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "fframes")
SOURCE = ROOT / "examples" / "low-poly-art" / "src" / "low_poly_art"
TARGET = Path(__file__).resolve().parents[1] / "examples" / "low_poly_art"


def artwork(rust: str) -> str:
    start = rust.index('viewBox="0 0 2560 3840"')
    start = rust.rindex("<svg", 0, start)
    end = rust.rindex("</svg>") + len("</svg>")
    lines = [line.strip() for line in rust[start:end].splitlines()]
    svg = "\n".join(line for line in lines if line and not line.startswith("//"))
    if "{" in svg:
        raise SystemExit("the artwork has Rust expressions; update this tool")
    return svg + "\n"


def main() -> None:
    TARGET.mkdir(exist_ok=True)
    target = TARGET / "owl.svg"
    target.write_text(artwork((SOURCE / "owl.rs").read_text()))
    print(target.relative_to(TARGET.parents[1]), target.stat().st_size)


if __name__ == "__main__":
    main()
