#!/bin/bash
# Wrapper around nvcc that records peak RSS per .cu file via getrusage.
# Activated by prepending its dir to PATH before invoking pip install.
real=$(which -a nvcc | grep -v "$(dirname "$0")" | head -1)
cu=$(printf '%s\n' "$@" | grep -E '\.cu$' | tail -1)
log=${NVCC_MEM_LOG:-/tmp/nvcc-mem.log}
out=$(mktemp)
/usr/bin/time -v -o "$out" "$real" "$@"; rc=$?
peak=$(awk -F': ' '/Maximum resident set size/ {print $2}' "$out")
printf '%s\tpeak_kib=%s\trc=%d\n' "${cu:-?}" "$peak" "$rc" >> "$log"
rm -f "$out"; exit $rc
