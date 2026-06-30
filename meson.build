# Root meson build for astro Python package (meson-python backend)

project('astro', 'c',
  version : '0.5.0',
  default_options : ['warning_level=2', 'c_std=c11']
)

# Python installation
py_mod = import('python')
py = py_mod.find_installation()
install_dir = py.get_install_dir()

# Install existing Python packages via subdirectories.
# New packages (astro_text, astro_display, astro_hours, astro/cli) are added
# as their meson.build entries are created in later sprints.

install_subdir('src/astro_api', install_dir: install_dir / 'astro_api', strip_directory: true)
install_subdir('src/astro_calc', install_dir: install_dir / 'astro_calc', strip_directory: true)
install_subdir('src/astro_data', install_dir: install_dir / 'astro_data', strip_directory: true)
install_subdir('src/astro_analyze', install_dir: install_dir / 'astro_analyze', strip_directory: true)
install_subdir('src/astro_api_client', install_dir: install_dir / 'astro_api_client', strip_directory: true)
install_subdir('src/astro_text', install_dir: install_dir / 'astro_text', strip_directory: true)

# Build the C shared library (Swiss Ephemeris wrapper)
se_src = '/home/xephyr/swisseph_test/pyswisseph-2.10.3.2'
se_lib = se_src + '/libswe'
se_inc = include_directories(se_src, se_lib)

libastro_calc = shared_library('astro-calc',
  'src/astro_calc/astro_calc.c',
  include_directories: se_inc,
  link_args: ['-L' + se_lib, '-lswe', '-lm'],
  install: true,
  install_dir: install_dir / 'astro_calc',
  install_rpath: se_lib,
)
