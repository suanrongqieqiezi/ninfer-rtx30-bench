#!/usr/bin/env bash
# Can we recover context on the 12 GB card? --wddm-evictable-budget budgets against
# total VRAM instead of the WDDM process budget (+0.51 GiB headroom in the probe).
ENGINE="D:/build/ninfer86/apps/ninfer.exe"
DF2="D:/27b/pkg1-fast-pq2/model/bonsai2_27b_ternary_v2-dflash2.ninfer"
MSGS="D:/build/msgs.json"
OUT=/d/build/sweep
cd "D:/build/ninfer86/apps" || exit 1

run() {
  local label="$1"; shift
  echo "=========== $label ==========="
  timeout 900 "$ENGINE" "$DF2" --messages "$MSGS" \
      --kv-dtype int8 --greedy --no-thinking --max-new 700 --log-level warning \
      --spec dflash2 --draft-tokens 7 --lm-head-draft "$@" \
      > "$OUT/${label}.out" 2> "$OUT/${label}.err"
  echo "   exit=$?"
}

run df2_32k_wddm --max-context 32768 --kv-capacity 32768 --wddm-evictable-budget
run df2_24k_wddm --max-context 24576 --kv-capacity 24576 --wddm-evictable-budget
run df2_16k_wddm --max-context 16384 --kv-capacity auto  --wddm-evictable-budget
echo ALLDONE
