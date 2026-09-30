#!/usr/bin/env bash
# Feasibility probe: can the dflash2 artifact start on a 12 GB card?
# The engine fails fast (~2 s) at "planning runtime" when the reservation does not fit,
# so this only needs max-new 8.
ENGINE="D:/build/ninfer86/apps/ninfer.exe"
MODEL="D:/27b/pkg1-fast-pq2/model/bonsai2_27b_ternary_v2-dflash2.ninfer"
MSGS="D:/build/msgs.json"
cd "D:/build/ninfer86/apps" || exit 1

try() {
  local label="$1"; shift
  local log="/d/build/sweep/feas_${label}.err"
  timeout 300 "$ENGINE" "$MODEL" --messages "$MSGS" \
      --kv-dtype int8 --greedy --no-thinking --max-new 8 --log-level warning \
      --spec dflash2 --draft-tokens 7 --lm-head-draft "$@" \
      > "/d/build/sweep/feas_${label}.out" 2> "$log"
  local rc=$?
  if grep -qa "decode" "$log"; then
    local w=$(grep -a "gpu weights used" "$log" | head -1 | sed 's/.*summary *//')
    local f=$(grep -a "free after weights" "$log" | head -1 | sed 's/.*summary *//')
    local r=$(grep -a "runtime reservation" "$log" | head -1 | sed 's/.*summary *//')
    printf "%-26s OK    rc=%d | %s | %s | %s\n" "$label" "$rc" "$w" "$f" "$r"
  else
    local err=$(grep -a "^error:" "$log" | head -1 | cut -c1-140)
    printf "%-26s FAIL  rc=%d | %s\n" "$label" "$rc" "$err"
  fi
}

try ctx32k_auto   --max-context 32768 --kv-capacity auto
try ctx16k_expl   --max-context 16384 --kv-capacity 16384
try ctx8k_expl    --max-context 8192  --kv-capacity 8192
try ctx16k_wddm   --max-context 16384 --kv-capacity auto --wddm-evictable-budget
echo DONE
