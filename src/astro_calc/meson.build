# astrologycalc — C wrapper for Swiss Ephemeris

project('astro-calc', 'c',
  version: '0.1.0',
  default_options: ['warning_level=2', 'c_std=c11']
)

# Swiss Ephemeris from the audit build
se_src = '/home/xephyr/swisseph_test/pyswisseph-2.10.3.2'
se_lib = se_src + '/libswe'

# Include directories
se_inc = include_directories(se_src, se_lib)

# Our library
libastro_calc = shared_library('astro-calc',
  'astro_calc.c',
  include_directories: se_inc,
  link_args: ['-L' + se_lib, '-lswe', '-lm'],
  install_rpath: se_lib,
  install: false,
)

# Phase0 test
test0 = executable('test_phase0',
  '../../tests/test_phase0.c',
  include_directories: se_inc,
  link_with: libastro_calc,
  link_args: ['-L' + se_lib, '-lswe', '-lm'],
)
test('phase0', test0)

# Phase2 test
test2 = executable('test_phase2',
  '../../tests/test_phase2.c',
  include_directories: se_inc,
  link_with: libastro_calc,
  link_args: ['-L' + se_lib, '-lswe', '-lm'],
)
test('phase2', test2)
