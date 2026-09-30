#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Golden-answer check against the running ninfer server (docs section 6 gate)."""
import json
import urllib.request

URL = "http://127.0.0.1:8099/v1/chat/completions"
CASES = [
    ("The capital of France is", "Paris"),
    ("\u4e2d\u56fd\u7684\u9996\u90fd\u662f\u54ea\u4e2a\u57ce\u5e02\uff1f", "\u5317\u4eac"),
    ("What is 17 * 23?", "391"),
]


def ask(prompt, max_tokens=128):
    body = json.dumps({
        "model": "qwen3.8-27b",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
    }).encode("utf-8")
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"]


ok = 0
for prompt, expect in CASES:
    got = ask(prompt).strip()
    hit = expect in got
    ok += hit
    print("  %-28s -> %-24s expect %-8s %s" % (prompt, repr(got)[:24], expect, "PASS" if hit else "FAIL"))
print("golden: %d/%d" % (ok, len(CASES)))
