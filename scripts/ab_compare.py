# -*- coding: utf-8 -*-
"""A/B：官方预编译 3090 包 vs 自编译 franken 补丁版。同参同prompt，比 tok/s + 输出MD5"""
import hashlib, json, subprocess, sys, time, urllib.request

PORT = 8908
BASE = f"http://127.0.0.1:{PORT}"
MODEL = r"E:\AI\models\Ternary-Bonsai-2-27B-ninfer-v3.ninfer"
A = r"E:\AI\ninfer-master-build\apps\ninfer-serve.exe"
ONLY = "official"

REPEAT_PROMPT = ("Repeat the following sentence exactly twelve times, one per line, then say DONE: "
                 "The quick brown fox jumps over the lazy dog. " * 12)
NORMAL_PROMPT = ("Explain in two sentences why mixture-of-experts models use fewer active "
                 "parameters than dense models of the same size.")

def chat(prompt, max_tokens):
    payload = json.dumps({"model": "bonsai2-27b",
                          "messages": [{"role": "user", "content": prompt}],
                          "max_tokens": max_tokens, "temperature": 0}).encode("utf-8")
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=payload,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        resp = json.loads(r.read())
    dt = time.time() - t0
    ct = resp["usage"]["completion_tokens"]
    return {"dt": dt, "tok_s": ct / dt, "tokens": ct, "text": resp["choices"][0]["message"]["content"]}

def run_one(name, exe, log):
    subprocess.run(["taskkill", "/F", "/IM", "ninfer-serve.exe"], capture_output=True)
    time.sleep(2)
    logf = open(log, "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen([exe, MODEL, "--spec", "dflash2", "--draft-tokens", "7",
                             "--port", str(PORT)], stdout=logf, stderr=subprocess.STDOUT)
    t0 = time.time()
    ready = False
    while time.time() - t0 < 180:
        try:
            with urllib.request.urlopen(BASE + "/v1/models", timeout=3) as r:
                if r.status == 200:
                    ready = True
                    break
        except Exception:
            time.sleep(2)
    if not ready:
        print(f"[{name}] serve failed to start")
        subprocess.run(["taskkill", "/F", "/IM", "ninfer-serve.exe"], capture_output=True)
        return None
    print(f"[{name}] ready in {time.time()-t0:.1f}s")
    chat("warmup: say OK", 8)  # 预热
    out = {"P1_repeat": [chat(REPEAT_PROMPT, 420) for _ in range(2)],
           "P2_normal": [chat(NORMAL_PROMPT, 256) for _ in range(2)]}
    for k, runs in out.items():
        for i, r in enumerate(runs):
            r["md5"] = hashlib.md5(r["text"].encode("utf-8")).hexdigest()
            print(f"[{name}] {k}[{i}]: {r['tok_s']:.1f} tok/s ({r['tokens']} tok, {r['dt']:.2f}s) md5={r['md5'][:8]}")
    subprocess.run(["taskkill", "/F", "/IM", "ninfer-serve.exe"], capture_output=True)
    time.sleep(2)
    return out

ra = run_one("official", A, r"E:\AI\bench_lookup\ab_official_serve.log")
rb = None
if ONLY != "official":
    rb = run_one("franken", B, r"E:\AI\bench_lookup\ab_franken_serve.log")

print("\n================ SUMMARY ================")
if ra and rb:
    for k in ("P1_repeat", "P2_normal"):
        a_avg = sum(x["tok_s"] for x in ra[k]) / 2
        b_avg = sum(x["tok_s"] for x in rb[k]) / 2
        print(f"{k}: official={a_avg:.1f} tok/s | franken={b_avg:.1f} tok/s | diff={100*(b_avg-a_avg)/a_avg:+.1f}%")
    same = all(ra[k][i]["md5"] == rb[k][i]["md5"] for k in ra for i in (0, 1))
    print("output MD5 identical:", same)
    if not same:
        for k in ra:
            for i in (0, 1):
                if ra[k][i]["md5"] != rb[k][i]["md5"]:
                    print(f"  DIFF {k}[{i}]: off={ra[k][i]['md5'][:8]} frk={rb[k][i]['md5'][:8]}")
