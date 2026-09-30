# -*- coding: utf-8 -*-
# Variant benchmark: test untested engine speed flags on bonsai27b, single GPU, serial.
# Outputs: E:\AI\bench_lookup\variant_results.json
import json, time, subprocess, sys, io, urllib.request, hashlib, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SERVE = r"E:\AI\ninfer-master-build\apps\ninfer-serve.exe"
MODEL = r"E:\AI\models\Ternary-Bonsai-2-27B-ninfer-v3.ninfer"
LOGD = r"E:\AI\bench_lookup"
OUT = os.path.join(LOGD, "variant_results.json")
PORT = 8906
BASE = "http://127.0.0.1:%d" % PORT

BASE_FLAGS = ["--spec", "dflash2", "--draft-tokens", "7", "--port", str(PORT)]

VARIANTS = [
    ("base",           []),
    ("lookup8",        ["--lookup-ngram", "8"]),
    ("mlp_a8_decode",  ["--mlp-a8-decode"]),
    ("prefill_cublas", ["--prefill-cublas"]),
    ("kv_k8v4",        ["--kv-dtype", "k8v4"]),
]

REPEAT_PROMPT = (
    "Repeat the following sentence exactly twelve times, one per line, then say DONE: "
    "The quick brown fox jumps over the lazy dog. " * 12
)
NORMAL_PROMPT = (
    "Explain in two sentences why mixture-of-experts models use fewer active "
    "parameters than dense models of the same size."
)
LONG_TEXT = ("The atmosphere of Jupiter is the largest planetary atmosphere in the Solar System. " * 90)
PREFILL_PROMPT = LONG_TEXT + "\nAnswer with a single word: what planet?"

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
    subprocess.run(["taskkill", "/F", "/IM", "ninfer-serve.exe"],
                   capture_output=True)
    time.sleep(3)

results = {}
for name, flags in VARIANTS:
    print("=== variant: %s %s" % (name, " ".join(flags)), flush=True)
    kill_serve()
    entry = {"flags": flags}
    logf = open(os.path.join(LOGD, "v_%s_serve.log" % name), "w", encoding="utf-8", errors="replace")
    errf = open(os.path.join(LOGD, "v_%s_err.log" % name), "w", encoding="utf-8", errors="replace")
    try:
        proc = subprocess.Popen([SERVE, MODEL] + BASE_FLAGS + flags,
                                stdout=logf, stderr=errf)
        if not wait_health():
            entry["status"] = "boot_failed"
            proc.terminate()
        else:
            entry["status"] = "ok"
            chat(NORMAL_PROMPT, 32)  # warmup
            entry["P1_repeat"] = [chat(REPEAT_PROMPT, 256) for _ in range(2)]
            entry["P2_normal"] = [chat(NORMAL_PROMPT, 256) for _ in range(2)]
            entry["P3_prefill"] = [chat(PREFILL_PROMPT, 4) for _ in range(2)]
            entry["P2_text_md5"] = hashlib.md5(
                entry["P2_normal"][0]["text"].encode("utf-8")).hexdigest()
            entry["P2_text_head"] = entry["P2_normal"][0]["text"][:80]
    except Exception as e:
        entry["status"] = "error: %r" % e
    finally:
        logf.close(); errf.close()
        kill_serve()
    results[name] = entry
    print(json.dumps({k: v for k, v in entry.items() if k != "text"}, ensure_ascii=False)[:400], flush=True)

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\n==== SUMMARY ====")
for name, entry in results.items():
    if entry.get("status") != "ok":
        print("%-16s %s" % (name, entry.get("status")))
        continue
    p1 = max(r["tok_s"] for r in entry["P1_repeat"])
    p2 = max(r["tok_s"] for r in entry["P2_normal"])
    p3 = min(r["sec"] for r in entry["P3_prefill"])
    print("%-16s repeat=%.1f tok/s  normal=%.1f tok/s  prefill~%.1fs" % (name, p1, p2, p3))
print("saved:", OUT)
