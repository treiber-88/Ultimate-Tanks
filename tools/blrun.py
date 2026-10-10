import sys, time
sys.path.insert(0, r"C:\Users\mk-ki\Desktop\Ultimate Tanks\tools")
import bl
pre, path = sys.argv[1], sys.argv[2]
t = time.time()
code = pre + "\n" + open(path, encoding="utf-8").read()
res = bl.run_code(code)
print("status:", res.get("status"), "%.1fs" % (time.time() - t))
if res.get("stdout"): print(res["stdout"][-1500:])
if res.get("status") != "ok": print(res.get("message"))
