# -*- coding: utf-8 -*-
# lookup-ngram A/B test: R1 baseline (dflash2) vs R2 (+lookup-ngram 8)
import json, time, sys, io, urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8906
BASE = "http://127.0.0.1:%d" % PORT

REPEAT_PROMPT = (
    "Repeat the following sentence exactly twelve times, one per line, then say DONE: "
    "The quick brown fox jumps over the lazy dog. " * 12
)
NORMAL_PROMPT = (
    "Explain in two sentences why mixture-of-experts models use fewer active "
    "parameters than dense models of the same size."
)

def chat(prompt, max_tokens=256):
    payload = json.dumps({
        "model": "bonsai-27b",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,  # greedy for deterministic token streams
    }).encode("utf-8")
    req = urllib.request.Request(
        BASE + "/v1/chat/completions", data=payload,
        headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.loads(r.read().decode("utf-8"))
    dt = time.time() - t0
    u = out.get("usage", {})
    comp = u.get("completion_tokens", 0)
    pref = u.get("prompt_tokens", 0)
    return {"sec": round(dt, 2), "completion_tokens": comp,
            "prompt_tokens": pref, "tok_s": round(comp / dt, 2) if dt > 0 else 0}

def main():
    results = {}
    for name, prompt in (("P1_repeat", REPEAT_PROMPT), ("P2_normal", NORMAL_PROMPT)):
        chat(prompt, max_tokens=32)  # warmup
        runs = [chat(prompt, max_tokens=256) for _ in range(2)]
        results[name] = runs
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()

