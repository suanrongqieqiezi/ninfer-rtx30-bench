#!/usr/bin/env bash
# Sweep the ninfer CLI over speculative-decoding configs on the self-built sm_86 engine.
# Each run is a fresh process, so the weights are loaded once per arm (~20-40 s).
ENGINE="D:/build/ninfer86/apps/ninfer.exe"
MODEL="D:/27b/pkg1-fast-pq2/model/bonsai2_27b_ternary_v2.ninfer"
MSGS="D:/build/msgs.json"
OUT=/d/build/sweep
mkdir -p "$OUT"
cd "D:/build/ninfer86/apps" || exit 1

run() {
  local label="$1"; shift
  echo "=========== $label ==========="
  "$ENGINE" "$MODEL" --messages "$MSGS" \
      --max-context 32768 --kv-capacity auto --kv-dtype int8 \
      --greedy --no-thinking --max-new 700 --log-level info "$@" \
      > "$OUT/${label}.out" 2> "$OUT/${label}.err"
  echo "   exit=$?"
}

run nospec
run d2 --spec mtp --draft-tokens 2
run d3 --spec mtp --draft-tokens 3
run d4 --spec mtp --draft-tokens 4
run d5 --spec mtp --draft-tokens 5
run d6 --spec mtp --draft-tokens 6
run d4_lmhead --spec mtp --draft-tokens 4 --lm-head-draft
echo "ALL DONE"
