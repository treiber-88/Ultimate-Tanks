"""Run a Blender art script inside the running Blender (Blender MCP add-on, port 9876).

Usage: python tools/blrun.py "<python to run first, may be empty>" tools/blender/render_tanks.py
"""
import os
import sys
import time

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import bl

pre, path = sys.argv[1], sys.argv[2]
t = time.time()
with open(path, encoding="utf-8") as f:
    code = "UT_HERE = %r\n%s\n%s" % (os.path.join(TOOLS, "blender"), pre, f.read())
res = bl.run_code(code)
print("status:", res.get("status"), "%.1fs" % (time.time() - t))
if res.get("stdout"):
    print(res["stdout"][-1500:])
if res.get("status") != "ok":
    print(res.get("message"))
    sys.exit(1)
