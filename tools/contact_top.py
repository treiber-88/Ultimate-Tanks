"""Top-down QA sheet: every tank, hull+turret composited and tinted, at 3 headings."""
import sys, json
from PIL import Image
import numpy as np
meta = json.load(open("assets/tanks/tanks.json"))
cols = [(70,120,210),(200,60,50),(80,150,70),(215,170,50),(140,80,190),(220,120,40)]
def tint(name, c):
    a = np.asarray(Image.open(f"assets/tanks/{name}.png").convert("RGBA")).astype(np.float32)/255
    m = np.asarray(Image.open(f"assets/tanks/{name}_mask.png").convert("RGBA")).astype(np.float32)/255
    mk = m[...,:1]; col = np.array(c, np.float32)/255
    rgb = a[...,:3]*(1-mk) + np.clip(a[...,:3]*col*1.5,0,1)*mk
    return Image.fromarray((np.dstack([rgb, a[...,3:]])*255).astype(np.uint8))
W = Image.new("RGB", (300*6, 300*3), (86,104,62))
for i,(k,c) in enumerate(zip(meta, cols)):
    m = meta[k]; hs = tint(k+"_hull", c); ts = tint(k+"_turret", c)
    hf, tf = m["hull_frame"], m["turret_frame"]
    for j,(fh,ft) in enumerate(((0,3),(5,9),(20,14))):
        h = hs.crop(((fh%8)*hf,(fh//8)*hf,(fh%8+1)*hf,(fh//8+1)*hf))
        t = ts.crop(((ft%8)*tf,(ft//8)*tf,(ft%8+1)*tf,(ft//8+1)*tf))
        cx, cy = i*300+150, j*300+150
        W.paste(h, (cx-hf//2, cy-hf//2), h)
        import math
        a = fh*2*math.pi/32
        px = cx + math.cos(a)*m["turret_x"]*20; py = cy + math.sin(a)*m["turret_x"]*20
        W.paste(t, (int(px-tf/2), int(py-tf/2)), t)
W.save(sys.argv[1])
