"""Turn the raw Blender ground renders into seamless tiles (assets/terrain/raw/*.png -> assets/terrain/*.png)."""
import glob
import os

import numpy as np
from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "terrain")


def _wrap_axis(a, axis):
    """Make one axis wrap by blending with a half-shifted copy; the copy's own seam sits where its weight is 0."""
    n = a.shape[axis]
    edge = np.abs(np.linspace(-1, 1, n))                  # 0 centre .. 1 border
    wgt = np.clip((1.0 - edge) / 0.42, 0, 1)
    wgt = wgt * wgt * (3 - 2 * wgt)
    shape = [1, 1, 1]
    shape[axis] = n
    wgt = wgt.reshape(shape)
    b = np.roll(a, n // 2, axis=axis)
    mean = a.mean(axis=(0, 1), keepdims=True)
    # variance-preserving blend so the mixed band does not look washed out
    return mean + ((a - mean) * wgt + (b - mean) * (1 - wgt)) / np.sqrt(wgt ** 2 + (1 - wgt) ** 2)


def tileable(a):
    return np.clip(_wrap_axis(_wrap_axis(a, 1), 0), 0, 255)


def main():
    for f in sorted(glob.glob(os.path.join(ROOT, "raw", "*.png"))):
        a = np.asarray(Image.open(f).convert("RGB")).astype(np.float32)
        Image.fromarray(tileable(a).astype(np.uint8)).save(os.path.join(ROOT, os.path.basename(f)))
        print("tiled", os.path.basename(f))


if __name__ == "__main__":
    main()
