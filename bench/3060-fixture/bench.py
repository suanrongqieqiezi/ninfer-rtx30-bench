#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reusable benchmark for the locally-built sm_86 ninfer engine.

Measurement discipline (docs/调参与扫参-速度怎么来的.md sec 0.1):
  - long prompt AND long output (>=400 output tokens)
  - greedy (temperature 0; engine also started with --greedy)
  - drop the first request (weight swap-in / cuda-graph capture)
  - read the engine's OWN timings (response.timings), not a client stopwatch
  - 3 rounds, report the MEDIAN

Usage:  bench.py <label> [url] [max_tokens] [rounds]
"""
import json
import statistics
import sys
import time
import urllib.request
import uuid

LABEL = sys.argv[1] if len(sys.argv) > 1 else "arm"
URL = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8099/v1/chat/completions"
MAX_TOKENS = int(sys.argv[3]) if len(sys.argv) > 3 else 700
ROUNDS = int(sys.argv[4]) if len(sys.argv) > 4 else 3
MULT = int(sys.argv[5]) if len(sys.argv) > 5 else 8
MODEL = "qwen3.8-27b"

PARA = (
    "The graphics processing unit executes many threads in parallel. Each thread runs the same "
    "instruction stream on a different element of data. For large language model inference, memory "
    "bandwidth usually limits token generation, while tensor core throughput limits prompt processing. "
    "A quantized weight matrix must be unpacked before it is multiplied by the activation matrix. "
    "The scheduler decides which kernel rung to use based on how many tokens this layer sees. "
    "When the context grows, the key value cache grows with it, and once it spills out of device "
    "memory every token pays a host transfer cost. Speculative decoding raises the number of tokens "
    "emitted per round by drafting several candidates and verifying them in a single pass. "
)
LONG_PROMPT = (
    "Repeat the following text verbatim, word for word, with no additions and no omissions:\n\n"
    + " ".join([PARA] * MULT)
)


def make_prompt():
    """A fresh nonce in the PREFIX forces a real prefill on every request.
    Without it the prefix cache makes prompt_n collapse to ~7 and no prefill
    actually happens (docs/调参与扫参 sec 4, time layer)."""
    return (
        "Session %s. Repeat the following text verbatim, word for word, "
        "with no additions and no omissions:\n\n%s" % (uuid.uuid4().hex, LONG_PROMPT)
    )


def call():
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": make_prompt()}],
        "max_tokens": MAX_TOKENS,
        "temperature": 0,
    }).encode("utf-8")
    req = urllib.request.Request(URL, data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=900) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data, time.perf_counter() - t0


def main():
    print("### arm=%s  max_tokens=%d  rounds=%d" % (LABEL, MAX_TOKENS, ROUNDS))
    print("### warmup (dropped)...")
    try:
        call()
    except Exception as exc:  # noqa: BLE001
        print("WARMUP FAILED: %r" % (exc,))
        return 1

    rows = []
    for i in range(ROUNDS):
        try:
            d, wall = call()
        except Exception as exc:  # noqa: BLE001
            print("ROUND %d FAILED: %r" % (i + 1, exc))
            continue
        t = d.get("timings", {})
        rows.append({
            "round": i + 1,
            "wall_s": round(wall, 2),
            "prompt_n": t.get("prompt_n"),
            "out_n": t.get("predicted_n"),
            "prefill_tps": round(t.get("prompt_per_second", 0), 1),
            "decode_tps": round(t.get("predicted_per_second", 0), 1),
            "ms_per_token": round(t.get("predicted_per_token_ms", 0), 2),
            "ttft_ms": round(t.get("prompt_ms", 0), 0),
            "finish": d.get("choices", [{}])[0].get("finish_reason"),
            "usage": d.get("usage", {}),
        })
        r = rows[-1]
        print("  round %d: prompt %s tok | out %s tok | prefill %s t/s | decode %s t/s | "
              "%.2f ms/tok | ttft %s ms | wall %.2fs | finish=%s"
              % (r["round"], r["prompt_n"], r["out_n"], r["prefill_tps"], r["decode_tps"],
                 r["ms_per_token"], r["ttft_ms"], r["wall_s"], r["finish"]))

    if not rows:
        print("NO VALID ROUNDS")
        return 1

    dec = [r["decode_tps"] for r in rows]
    pre = [r["prefill_tps"] for r in rows]
    out = [r["out_n"] for r in rows]
    print("--- MEDIAN ---")
    print("  decode  = %.1f t/s   (samples: %s)" % (statistics.median(dec), dec))
    print("  prefill = %.1f t/s   (samples: %s)" % (statistics.median(pre), pre))
    print("  out_n   = %s" % (out,))
    return 0


if __name__ == "__main__":
    sys.exit(main())
