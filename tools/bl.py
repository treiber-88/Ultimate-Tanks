"""Run a Python file inside the running Blender through the Blender Lab MCP addon socket.

Usage: python tools/bl.py script.py   (the script sets a dict named `result`)
"""
import json
import socket
import sys

HOST, PORT = "127.0.0.1", 9876


def run_code(code, timeout=3600):
    s = socket.create_connection((HOST, PORT), timeout=10)
    s.settimeout(timeout)
    req = json.dumps({"type": "execute", "code": code, "strict_json": False})
    s.sendall(req.encode("utf-8") + b"\0")
    buf = bytearray()
    while b"\0" not in buf:
        chunk = s.recv(65536)
        if not chunk:
            break
        buf.extend(chunk)
    s.close()
    return json.loads(bytes(buf).split(b"\0")[0].decode("utf-8"))


def run_file(path, timeout=3600):
    with open(path, "r", encoding="utf-8") as f:
        return run_code(f.read(), timeout)


if __name__ == "__main__":
    res = run_file(sys.argv[1]) if sys.argv[1] != "-c" else run_code(sys.argv[2])
    if res.get("stdout"):
        print(res["stdout"], end="")
    if res.get("stderr"):
        print("STDERR:", res["stderr"], end="")
    if res.get("status") == "ok":
        print(json.dumps(res.get("result"), indent=1))
    else:
        print("ERROR:", res.get("message"))
        sys.exit(1)
