#!/bin/bash
# Launch astro-gui (GTK4 chart app).
#  1. Ensure the astrology API server is up on localhost:8081 (start if dead).
#  2. Launch the GUI with the SYSTEM python (has PyGObject; the Hermes venv does NOT).
set -u

API_URL="http://localhost:8081/v1/people"

if ! curl -sf --max-time 2 "$API_URL" >/dev/null 2>&1; then
  cd /home/xephyr/astro/src || exit 1
  nohup /usr/bin/python3 astro_api/server.py >/tmp/astro-api.log 2>&1 &
  # wait up to ~10s for the server to answer before giving up
  for _ in $(seq 1 20); do
    if curl -sf --max-time 1 "$API_URL" >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done
fi

cd /home/xephyr/astro || exit 1
exec env PYTHONPATH=/home/xephyr/astro/src /usr/bin/python3 -m astro_gui
