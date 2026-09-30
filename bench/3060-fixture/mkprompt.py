#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate a messages.json for the ninfer CLI with a long, verbatim-repeat prompt.

Usage: mkprompt.py <out.json> [mult]
  mult controls prompt length: ~140 token per unit -> mult=28 ~= 3900 tokens
"""
import json
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "msgs.json"
MULT = int(sys.argv[2]) if len(sys.argv) > 2 else 28

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

body = (
    "Repeat the following text verbatim, word for word, with no additions and no omissions:\n\n"
    + " ".join([PARA] * MULT)
)

payload = {"messages": [{"role": "user", "content": body}]}
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False)

print("wrote %s  mult=%d  prompt_chars=%d" % (OUT, MULT, len(body)))
