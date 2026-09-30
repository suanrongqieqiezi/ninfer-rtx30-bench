#!/usr/bin/env bash
# DFlash2 vs MTP, same context, on the 12 GB sm_86 card.
ENGINE="D:/build/ninfer86/apps/ninfer.exe"
BASE="D:/27b/pkg1-fast-pq2/model/bonsai2_27b_ternary_v2.ninfer"
DF2="D:/27b/pkg1-fast-pq2/model/bonsai2_27b_ternary_v2-dflash2.ninfer"
MSGS="D:/build/msgs.json"
OUT=/d/build/sweep
cd "D:/build/ninfer86/apps" || exit 1

run() {
  local label="$1"; local model="$2"; shift 2
  echo "=========== $label ==========="
  timeout 900 "$ENGINE" "$model" --messages "$MSGS" \
      --kv-dtype int8 --greedy --no-thinking --max-new 700 --log-level warning "$@" \
      > "$OUT/${label}.out" 2> "$OUT/${label}.err"
  echo "   exit=$?"
}

run df2_k7_16k "$DF2"  --max-context 16384 --kv-capacity 16384 \
                      --spec dflash2 --draft-tokens 7 --lm-head-draft
run df2_k5_16k "$DF2"  --max-context 16384 --kv-capacity 16384 \
                      --spec dflash2 --draft-tokens 5 --lm-head-draft
run df2_k7_8k  "$DF2"  --max-context 8192  --kv-capacity 8192 \
                      --spec dflash2 --draft-tokens 7 --lm-head-draft
run mtp_d5_16k  "$BASE" --max-context 16384 --kv-capacity 16384 \
                      --spec mtp --draft-tokens 5
echo ALLDONE
