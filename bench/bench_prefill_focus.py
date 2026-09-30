# -*- coding: utf-8 -*-
# Focused prefill test with ~7K-token prompt + mtp-experts-q4 decode check
import json, time, subprocess, sys, io, urllib.request, hashlib, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SERVE = r"E:\AI\ninfer-master-build\apps\ninfer-serve.exe"
MODEL = r"E:\AI\models\Ternary-Bonsai-2-27B-ninfer-v3.ninfer"
LOGD = r"E:\AI\bench_lookup"
PORT = 8906
BASE = "http://127.0.0.1:%d" % PORT

SENT = "The quick brown fox jumps over the lazy dog near the river bank at dawn. "
LONG_PROMPT = ("Below is a long reference text. Read it carefully. " + SENT * 470 +
               "\n\nHow many times does the word quick appear? Answer with just the number.")
NORMAL_PROMPT = ("Explain in two sentences why mixture-of-experts models use fewer active "
                 "parameters than dense models of the same size.")

def chat(prompt, max_tokens):
    payload = json.dumps({
        "model": "bonsai2-27b",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens, "temperature": 0}).encode("utf-8")
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=payload,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        out = json.loads(r.read().decode("utf-8"))
    dt = time.time() - t0
    u = out.get("usage", {})
    return {"sec": round(dt, 2), "prompt_tokens": u.get("prompt_tokens", 0),
            "completion_tokens": u.get("completion_tokens", 0),
            "text": (out.get("choices") or [{}])[0].get("message", {}).get("content", "")}

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

def kill():
    subprocess.run(["taskkill", "/F", "/IM", "ninfer-serve.exe"], capture_output=True)
    time.sleep(3)

CONFIGS = [
    ("base",       []),
    ("cublas",     ["--prefill-cublas"]),
    ("mtpq4",      ["--mtp-experts-q4"]),
]

results = {}
for name, flags in CONFIGS:
    kill()
    entry = {"flags": flags}
    logf = open(os.path.join(LOGD, "f_%s_serve.log" % name), "w", encoding="utf-8", errors="replace")
    try:
        proc = subprocess.Popen([SERVE, MODEL, "--spec", "dflash2", "--draft-tokens", "7",
                                 "--port", str(PORT)] + flags, stdout=logf, stderr=subprocess.STDOUT)
        if not wait_health():
            entry["status"] = "boot_failed"
        else:
            entry["status"] = "ok"
            chat(NORMAL_PROMPT, 32)
            entry["prefill7k"] = [chat(LONG_PROMPT, 1) for _ in range(3)]
            entry["decode"] = [chat(NORMAL_PROMPT, 256) for _ in range(2)]
            entry["decode_md5"] = hashlib.md5(entry["decode"][0]["text"].encode("utf-8")).hexdigest()
    except Exception as e:
        entry["status"] = "error: %r" % e
    finally:
        logf.close()
        kill()
    results[name] = entry
    print(name, json.dumps({k: v for k, v in entry.items() if k not in ("decode",)}, default=str)[:300], flush=True)

with open(os.path.join(LOGD, "prefill_results.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\n==== SUMMARY ====")
for name, e in results.items():
    if e.get("status") != "ok":
        print("%-8s %s" % (name, e.get("status")))
        continue
    pt = e["prefill7k"][0]["prompt_tokens"]
    best = min(r["sec"] for r in e["prefill7k"])
    rate = pt / best if best > 0 else 0
    dec = max(r["completion_tokens"] / r["sec"] for r in e["decode"])
    print("%-8s prefill(%d tok)=%.2fs (~%d tok/s)  decode=%.1f tok/s  md5=%s"
          % (name, pt, best, int(rate), dec, e["decode_md5"]))
print("saved prefill_results.json")
