#!/bin/bash
# Wrapper script to run astro_calc tests with proper library path
export LD_LIBRARY_PATH=/home/xephyr/swisseph_test/pyswisseph-2.10.3.2/libswe:$LD_LIBRARY_PATH
cd /home/xephyr/astro
exec python3 "$@"
