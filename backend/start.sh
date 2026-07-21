#!/bin/sh
set -eu

backend_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
: "${PORT:=8000}"
: "${DATA_DIR:=$backend_dir}"

export PORT DATA_DIR
mkdir -p \
  "$DATA_DIR/private" \
  "$DATA_DIR/uploads" \
  "$DATA_DIR/outputs/audio" \
  "$DATA_DIR/outputs/video" \
  "$DATA_DIR/jobs" \
  "$DATA_DIR/models"

cd "$backend_dir"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
