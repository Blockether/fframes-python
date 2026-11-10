import sys
from pathlib import Path

import numpy as np
from PIL import Image

a, b = Path(sys.argv[1]), Path(sys.argv[2])
fa = sorted(a.glob("*.png"))
fb = sorted(b.glob("*.png"))
assert [p.name for p in fa] == [p.name for p in fb] and fa, (fa, fb)
worst = 0
for x, y in zip(fa, fb):
    ia = np.asarray(Image.open(x).convert("RGBA"), dtype=np.int16)
    ib = np.asarray(Image.open(y).convert("RGBA"), dtype=np.int16)
    assert ia.shape == ib.shape, (x.name, ia.shape, ib.shape)
    d = np.abs(ia - ib)
    worst = max(worst, int(d.max()))
    print(
        f"{x.name}: max={d.max()} differing_px={(d.max(axis=2) > 0).sum()} / {d.shape[0] * d.shape[1]}"
    )
print("WORST", worst)
