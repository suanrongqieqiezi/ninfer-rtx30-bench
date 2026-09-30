# -*- coding: utf-8 -*-
# Draft-depth scan on top of the full stack: dflash2 + lookup8, --draft-tokens in {5,7,9,12}.
# Greedy + MD5 probe. Output: E:\AI\bench_lookup\draft_tokens_scan.json
import json, time, subprocess, sys, io, urllib.request, hashlib, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SERVE = r"E:\AI\ninfer-master-build\apps\ninfer-serve.exe"
MODEL = r"E:\AI\models\Ternary-Bonsai-2-27B-ninfer-v3.ninfer"
LOGD  = r"E:\AI\bench_lookup"
OUT   = os.path.join(LOGD, "draft_tokens_scan.json")
PORT  = 8907
BASE  = "http://127.0.0.1:%d" % PORT

BASE_FLAGS = ["--spec", "dflash2", "--lookup-ngram", "8", "--port", str(PORT)]

VARIANTS = [("dt%d" % dt, ["--draft-tokens", str(dt)]) for dt in (5, 7, 9, 12)]

REPEAT_PROMPT = (
    "Repeat the following sentence exactly twelve times, one per line, then say DONE: "
    "The quick brown fox jumps over the lazy dog. " * 12
)
NORMAL_PROMPT = (
    "Explain in two sentences why mixture-of-experts models use fewer active "
    "parameters than dense models of the same size."
)

def chat(prompt, max_tokens):
    payload = json.dumps({
        "model": "bonsai2-27b",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
    }).encode("utf-8")
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=payload,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        out = json.loads(r.read().decode("utf-8"))
    dt = time.time() - t0
    u = out.get("usage", {})
    comp = u.get("completion_tokens", 0)
    text = (out.get("choices") or [{}])[0].get("message", {}).get("content", "")
    return {"sec": round(dt, 2), "completion_tokens": comp,
            "tok_s": round(comp / dt, 2) if dt > 0 else 0, "text": text}

def wait_health(timeout_s=240):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            with urllib.request.urlopen(BASE + "/v1/models", timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(2)
    return False

def kill_serve():
    subprocess.run(["taskkill", "/F", "/IM", "ninfer-serve.exe"], capture_output=True)
    time.sleep(3)

results = {}
for name, flags in VARIANTS:
    print("=== variant: %s %s" % (name, " ".join(flags)), flush=True)
    kill_serve()
    entry = {"flags": flags}
    logf = open(os.path.join(LOGD, "dt_%s_serve.log" % name), "w", encoding="utf-8", errors="replace")
    errf = open(os.path.join(LOGD, "dt_%s_err.log" % name), "w", encoding="utf-8", errors="replace")
    try:
        proc = subprocess.Popen([SERVE, MODEL] + BASE_FLAGS + flags,
                                stdout=logf, stderr=errf)
        if not wait_health():
            entry["status"] = "boot_failed"
            proc.terminate()
        else:
            entry["status"] = "ok"
            chat(NORMAL_PROMPT, 32)  # warmup
            entry["P1_repeat"] = [chat(REPEAT_PROMPT, 264) for _ in range(2)]
            entry["P2_normal"] = [chat(NORMAL_PROMPT, 256) for _ in range(2)]
            entry["P1_md5"] = hashlib.md5(entry["P1_repeat"][0]["text"].encode("utf-8")).hexdigest()
            entry["P2_md5"] = hashlib.md5(entry["P2_normal"][0]["text"].encode("utf-8")).hexdigest()
            entry["P2_text_head"] = entry["P2_normal"][0]["text"][:80]
    except Exception as e:
        entry["status"] = "error: %r" % e
    finally:
        logf.close(); errf.close()
        kill_serve()
    results[name] = entry
    print(json.dumps({k: v for k, v in entry.items() if not k.endswith("repeat") and k != "P2_normal"},
                     ensure_ascii=False)[:300], flush=True)

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\n==== SUMMARY ====")
md5s = {}
for name, entry in results.items():
    if entry.get("status") != "ok":
        print("%-6s %s" % (name, entry.get("status")))
        continue
    p1 = max(r["tok_s"] for r in entry["P1_repeat"])
    p2 = max(r["tok_s"] for r in entry["P2_normal"])
    md5s[name] = (entry["P1_md5"], entry["P2_md5"])
    print("%-6s repeat=%.1f tok/s  normal=%.1f tok/s  md5=%s/%s" % (name, p1, p2, entry["P1_md5"][:8], entry["P2_md5"][:8]))
uniq = set(md5s.values())
print("md5 consistency:", "ALL IDENTICAL (lossless)" if len(uniq) == 1 else "DIFFERS ACROSS VARIANTS")
print("saved:", OUT)
