# -*- coding: utf-8 -*-
"""新编译 franken-v0.11 serve 冒烟测试：功能 + 单条速度探针"""
import json, subprocess, sys, time, urllib.request

SERVE = r"E:\AI\ninfer-3090-franken-v0.11\build-ninja\apps\ninfer-serve.exe"
MODEL = r"E:\AI\models\Ternary-Bonsai-2-27B-ninfer-v3.ninfer"
PORT = 8907
BASE = f"http://127.0.0.1:{PORT}"
LOG = r"E:\AI\bench_lookup\smoke_franken_serve.log"

subprocess.run(["taskkill", "/F", "/IM", "ninfer-serve.exe"], capture_output=True)
time.sleep(2)

flags = ["--spec", "dflash2", "--draft-tokens", "7", "--port", str(PORT)]
logf = open(LOG, "w", encoding="utf-8", errors="replace")
proc = subprocess.Popen([SERVE, MODEL] + flags, stdout=logf, stderr=subprocess.STDOUT)
print(f"[smoke] serve started pid={proc.pid}, waiting for model load...")

ok = False
t0 = time.time()
while time.time() - t0 < 180:
    try:
        with urllib.request.urlopen(BASE + "/v1/models", timeout=3) as r:
            if r.status == 200:
                ok = True
                break
    except Exception:
        pass
    time.sleep(2)

if not ok:
    print("[smoke] FAIL: serve not ready in 180s, log tail:")
    logf.flush()
    print(open(LOG, encoding="utf-8", errors="replace").read()[-2000:])
    subprocess.run(["taskkill", "/F", "/IM", "ninfer-serve.exe"], capture_output=True)
    sys.exit(1)

print(f"[smoke] serve ready in {time.time()-t0:.1f}s")

prompt = "用两句话解释为什么混合专家(MoE)模型比同参数量的稠密模型推理更省算力。"
body = json.dumps({
    "model": "bonsai2-27b",
    "messages": [{"role": "user", "content": prompt}],
    "max_tokens": 160,
    "temperature": 0,
}).encode()

req = urllib.request.Request(BASE + "/v1/chat/completions", data=body,
                             headers={"Content-Type": "application/json"})
t1 = time.time()
with urllib.request.urlopen(req, timeout=300) as r:
    resp = json.loads(r.read())
dt = time.time() - t1

u = resp.get("usage", {})
ct = u.get("completion_tokens", 0)
text = resp["choices"][0]["message"]["content"]
print(f"[smoke] gen time {dt:.2f}s, completion_tokens={ct}, decode={ct/dt:.1f} tok/s")
print("[smoke] output:")
print(text)
print("[smoke] usage:", u)

subprocess.run(["taskkill", "/F", "/IM", "ninfer-serve.exe"], capture_output=True)
print("[smoke] serve stopped. RESULT:", "OK" if ct > 50 else "SUSPECT")
