#!/usr/bin/env python3
import os
import ctypes

# Test loading libswe.so directly
_SE_LIB = os.path.expanduser("~/swisseph_test/pyswisseph-2.10.3.2/libswe/libswe.so")
print(f"Checking {_SE_LIB}")
print(f"Exists: {os.path.exists(_SE_LIB)}")

try:
    handle = ctypes.CDLL(_SE_LIB, mode=ctypes.RTLD_GLOBAL)
    print("libswe.so loaded successfully with RTLD_GLOBAL")
except OSError as e:
    print(f"Failed to load libswe.so: {e}")

# Now try libastro-calc.so
_LIB_PATH = "/home/xephyr/astro/src/astro_calc/libastro-calc.so"
print(f"\nChecking {_LIB_PATH}")
print(f"Exists: {os.path.exists(_LIB_PATH)}")

try:
    astro_lib = ctypes.CDLL(_LIB_PATH)
    print("libastro-calc.so loaded successfully")
except OSError as e:
    print(f"Failed to load libastro-calc.so: {e}")
