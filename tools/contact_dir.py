"""QA contact sheet: paste every PNG matching the given prefixes onto a grass-coloured board."""
import sys, glob, os
from PIL import Image
out, folder = sys.argv[1], sys.argv[2]
names = sys.argv[3:]
files = [f for f in sorted(glob.glob(os.path.join(folder, "*.png"))) if not names or any(os.path.basename(f).startswith(n) for n in names)]
ims = [Image.open(f).convert("RGBA") for f in files]
x = y = rowh = 0; W = 1800; pos = []
for im in ims:
    if x + im.width > W: x = 0; y += rowh + 10; rowh = 0
    pos.append((x, y)); x += im.width + 10; rowh = max(rowh, im.height)
board = Image.new("RGB", (W, y + rowh), (92, 118, 60))
for im, p in zip(ims, pos): board.paste(im, p, im)
if board.height > 1900: board = board.resize((int(W*1900/board.height), 1900))
board.save(out); print(len(ims), board.size)
