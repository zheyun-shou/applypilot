#!/usr/bin/env sh
# Unattended sweep for cron or launchd. Usage: run_sweep.sh <region>
cd "$(dirname "$0")/../.." || exit 1
mkdir -p workspace/runs
exec "${PYTHON:-python3}" pipeline/ap.py sweep --region "$1" >> workspace/runs/scheduled.log 2>&1
