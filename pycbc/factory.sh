#!/bin/bash
#
# Start a vine_factory that sizes the worker pool of regulated_vine_ligo.py
# by the resource signal its manager reports. The factory finds the manager
# through the catalog by its name, so start both with the same NAME.
#
# usage: factory.sh [vine_factory options]
#
# Settings come from these variables (defaults in parentheses):
#   BATCH (condor)  NAME (vine-regulated-ligo-$USER)
#   CORES (12)  MEMORY (16000)  DISK (25000)  per worker
#   MIN_WORKERS (1)  MAX_WORKERS (20)  SIGNAL_STEP (1): workers added per cycle when under-allocated
#   WORKER_TIMEOUT (300): seconds an idle worker waits before exiting
#   FACTORY_PERIOD (30): seconds between factory cycles
#   LOG (factory-<time>.debug)
#
# Extra vine_factory options pass through, e.g. -B "<batch submit options>".
# vine_factory must come from a cctools build with the resource signal.

if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
	sed -n '3,19p' "$0" | sed 's/^# \{0,1\}//'
	exit 0
fi

BATCH=${BATCH:-condor}
NAME=${NAME:-vine-regulated-ligo-$USER}
CORES=${CORES:-12}
MEMORY=${MEMORY:-16000}
DISK=${DISK:-25000}
MIN_WORKERS=${MIN_WORKERS:-1}
MAX_WORKERS=${MAX_WORKERS:-20}
SIGNAL_STEP=${SIGNAL_STEP:-1}
WORKER_TIMEOUT=${WORKER_TIMEOUT:-300}
FACTORY_PERIOD=${FACTORY_PERIOD:-30}
LOG=${LOG:-factory-$(date +%Y%m%dT%H%M%S).debug}

set -x
exec vine_factory -T "$BATCH" -M "$NAME" \
	--cores "$CORES" --memory "$MEMORY" --disk "$DISK" \
	--min-workers "$MIN_WORKERS" --max-workers "$MAX_WORKERS" --workers-per-cycle "$MAX_WORKERS" \
	--signal-step "$SIGNAL_STEP" -t "$WORKER_TIMEOUT" --factory-period "$FACTORY_PERIOD" \
	-d all -o "$LOG" \
	"$@"
