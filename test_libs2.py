#!/usr/bin/env python3
import os
import ctypes
import sys

# Test loading both libraries in order with proper paths
_SE_LIB = os.path.expanduser("~/swisseph_test/pyswisseph-2.10.3.2/libswe/libswe.so")
_LIB_PATH = "/home/xephyr/astro/src/astro_calc/libastro-calc.so"

print(f"Loading {_SE_LIB} with RTLD_GLOBAL...")
try:
    _se_handle = ctypes.CDLL(_SE_LIB, mode=ctypes.RTLD_GLOBAL)
    print("SUCCESS: libswe.so loaded")
except OSError as e:
    print(f"FAILED: libswe.so - {e}")
    sys.exit(1)

print(f"\nLoading {_LIB_PATH}...")
try:
    _lib = ctypes.CDLL(_LIB_PATH)
    print("SUCCESS: libastro-calc.so loaded")
except OSError as e:
    print(f"FAILED: libastro-calc.so - {e}")
    sys.exit(1)

# Try calling ac_init
print("\nCalling ac_init()...")
try:
    _lib.ac_init.argtypes = [ctypes.c_char_p]
    _lib.ac_init.restype = ctypes.c_int
    result = _lib.ac_init(None)
    print(f"ac_init() returned {result}")
except Exception as e:
    print(f"ac_init() failed: {e}")
