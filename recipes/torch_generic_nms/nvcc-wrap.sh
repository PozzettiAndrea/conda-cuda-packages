#!/bin/bash
# Wrapper around nvcc that records peak RSS per .cu file via getrusage.
# Installed in place of $PREFIX/bin/nvcc; real nvcc moved to nvcc.real.
self="$(readlink -f "$0")"
real="$(dirname "$self")/nvcc.real"
[ -x "$real" ] || real=$(which -a nvcc | grep -v "$self" | head -1)
cu=$(printf '%s\n' "$@" | grep -E '\.cu$' | tail -1)
log=${NVCC_MEM_LOG:-/tmp/nvcc-mem.log}
out=$(mktemp)
/usr/bin/time -v -o "$out" "$real" "$@"; rc=$?
peak=$(awk -F': ' '/Maximum resident set size/ {print $2}' "$out")
printf '%s\tpeak_kib=%s\trc=%d\n' "${cu:-?}" "$peak" "$rc" >> "$log"
rm -f "$out"; exit $rc
