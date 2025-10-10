project('skia',
        'c', 'cpp',
        version: '141',
        meson_version: '>= 1.1',
        license: 'BSD-3-Clause')

fs = import('fs')
host_system = host_machine.system()

# Determine build target
if get_option('debug')
  target = 'debug'
else
  target = 'release'
endif

# Find required tools
python = import('python').find_installation()
gn_wrapper = find_program('gn_wrapper.py')
ninja = find_program('ninja', required: true)

# Track gn_wrapper.py for automatic reconfiguration
# Using configure_file with copy:true makes Meson track this file
# and reconfigure when it changes
configure_file(input: 'gn_wrapper.py', output: 'gn_wrapper.py', copy: true)

# We are now in the Skia source directory
skia_dir = meson.current_source_dir()

# Determine library extensions
if host_system == 'windows'
  ext_static = 'lib'
  ext_shared = 'dll'
elif host_system == 'darwin'
  ext_static = 'a'
  ext_shared = 'dylib'
else
  ext_static = 'a'
  ext_shared = 'so'
endif

# Build feature list from options
features = []

if get_option('gl').enabled()
  features += 'gl'
endif

if get_option('egl').enabled()
  features += 'egl'
endif

if get_option('x11').enabled()
  features += 'x11'
endif

if get_option('wayland').enabled()
  features += 'wayland'
endif

if get_option('vulkan').enabled()
  features += 'vulkan'
endif

if get_option('metal').enabled()
  features += 'metal'
endif

if get_option('d3d').enabled()
  features += 'd3d'
endif

if get_option('textlayout').enabled()
  features += 'textlayout'
endif

if get_option('svg').enabled()
  features += 'svg'
endif

if get_option('pdf').enabled()
  features += 'pdf'
endif

if get_option('webp-encode').enabled()
  features += 'webp-encode'
endif

if get_option('webp-decode').enabled()
  features += 'webp-decode'
endif

if get_option('embed-freetype').enabled()
  features += 'embed-freetype'
endif

if get_option('freetype-woff2').enabled()
  features += 'freetype-woff2'
endif

# Determine library type(s)
default_library = get_option('default_library')
build_static = default_library in ['static', 'both']
build_shared = default_library in ['shared', 'both']

if default_library == 'both'
  message('Building Skia as both static and shared libraries (will run build twice)')
elif default_library == 'shared'
  message('Building Skia as shared library')
elif default_library == 'static'
  message('Building Skia as static library')
else
  error('Unknown library type: ' + default_library)
endif

# Build output file list
outputs_static = []
outputs_shared = []

if build_static
  outputs_static += ['libskia.' + ext_static]
  if 'textlayout' in features
    outputs_static += [
      'libskparagraph.' + ext_static,
      'libskshaper.' + ext_static,
      'libskunicode_core.' + ext_static,
      'libskunicode_icu.' + ext_static,
    ]
  endif
  if 'svg' in features
    outputs_static += [
      'libsvg.' + ext_static,
      'libskresources.' + ext_static,
    ]
  endif
endif

if build_shared
  outputs_shared += ['libskia.' + ext_shared]
  if 'textlayout' in features
    outputs_shared += [
      'libskparagraph.' + ext_shared,
      'libskshaper.' + ext_shared,
      'libskunicode_core.' + ext_shared,
      'libskunicode_icu.' + ext_shared,
    ]
  endif
  if 'svg' in features
    outputs_shared += [
      'libsvg.' + ext_shared,
      'libskresources.' + ext_shared,
    ]
  endif
endif

cxx = meson.get_compiler('cpp')

# Configure GN for static build at setup time
static_defines_map = {}
if build_static
  configure_cmd_static = [
    python,
    gn_wrapper,
    cxx.get_id(),
    meson.current_build_dir(),
    meson.current_source_dir(),
    meson.global_build_root(),
    target,
    get_option('prefix'),
    get_option('libdir'),
    '--library-type', 'static',
    '--version', meson.project_version(),
    '--configure-only',
  ]

  if features.length() > 0
    configure_cmd_static += ['--features'] + features
  endif

  if get_option('use-system-libraries')
    configure_cmd_static += ['--use-system-libraries']
  endif

  message('Configuring Skia static build with GN...')
  configure_result = run_command(configure_cmd_static, capture: true, check: true)

  # Parse defines for each library from format: SKIA_DEFINES:libname:defines
  foreach line : configure_result.stdout().strip().split('\n')
    if line.startswith('SKIA_DEFINES:')
      parts = line.split(':')
      assert(parts.length() == 3, 'Invalid SKIA_DEFINES format: ' + line)
      lib_name = parts[1]
      defines_str = parts[2]
      static_defines_map += {lib_name: defines_str.split()}
    endif
  endforeach
endif

# Build static libraries if requested
skia_build_static = []
if build_static
  wrapper_cmd_static = [
    python,
    gn_wrapper,
    cxx.get_id(),
    meson.current_build_dir(),
    meson.current_source_dir(),
    meson.global_build_root(),
    target,
    get_option('prefix'),
    get_option('libdir'),
    '--library-type', 'static',
    '--version', meson.project_version(),
    '--build-only',
    '--depfile', '@DEPFILE@',
  ]

  if features.length() > 0
    wrapper_cmd_static += ['--features'] + features
  endif

  if get_option('use-system-libraries')
    wrapper_cmd_static += ['--use-system-libraries']
  endif

  skia_build_static = custom_target('skia-build-static',
    build_by_default: true,
    output: outputs_static,
    console: true,
    depfile: 'skia-static.dep',
    command: wrapper_cmd_static,
    install: true,
    install_dir: get_option('libdir'),
  )
endif

# Configure GN for shared build at setup time
shared_defines_map = {}
if build_shared
  configure_cmd_shared = [
    python,
    gn_wrapper,
    cxx.get_id(),
    meson.current_build_dir(),
    meson.current_source_dir(),
    meson.global_build_root(),
    target,
    get_option('prefix'),
    get_option('libdir'),
    '--library-type', 'shared',
    '--version', meson.project_version(),
    '--configure-only',
  ]

  if features.length() > 0
    configure_cmd_shared += ['--features'] + features
  endif

  if get_option('use-system-libraries')
    configure_cmd_shared += ['--use-system-libraries']
  endif

  message('Configuring Skia shared build with GN...')
  configure_result = run_command(configure_cmd_shared, capture: true, check: true)

  # Parse defines for each library from format: SKIA_DEFINES:libname:defines
  foreach line : configure_result.stdout().strip().split('\n')
    if line.startswith('SKIA_DEFINES:')
      parts = line.split(':')
      assert(parts.length() == 3, 'Invalid SKIA_DEFINES format: ' + line)
      lib_name = parts[1]
      defines_str = parts[2]
      shared_defines_map += {lib_name: defines_str.split()}
    endif
  endforeach
endif

# Build shared libraries if requested
skia_build_shared = []
if build_shared
  wrapper_cmd_shared = [
    python,
    gn_wrapper,
    cxx.get_id(),
    meson.current_build_dir(),
    meson.current_source_dir(),
    meson.global_build_root(),
    target,
    get_option('prefix'),
    get_option('libdir'),
    '--library-type', 'shared',
    '--version', meson.project_version(),
    '--build-only',
    '--depfile', '@DEPFILE@',
  ]

  if features.length() > 0
    wrapper_cmd_shared += ['--features'] + features
  endif

  if get_option('use-system-libraries')
    wrapper_cmd_shared += ['--use-system-libraries']
  endif

  skia_build_shared = custom_target('skia-build-shared',
    build_by_default: true,
    output: outputs_shared,
    console: true,
    depfile: 'skia-shared.dep',
    command: wrapper_cmd_shared,
    install: true,
    install_dir: get_option('libdir'),
  )

  # Choose which build to use for dependency declaration
  # Prefer shared if available (Meson's default), otherwise use static
  skia_build = skia_build_shared
else
  skia_build = skia_build_static
endif

# Extract individual library targets for dependency declarations
skia_libs = skia_build.to_list()
libskia = skia_libs[0]

if 'textlayout' in features
  libskparagraph = skia_libs[1]
  libskshaper = skia_libs[2]
  libskunicode_core = skia_libs[3]
  libskunicode_icu = skia_libs[4]
endif

if 'svg' in features
  lib_index += 2  # Skip svg libs for now
endif

# Create mapping from library names to library targets for pkg-config
pkg_lib_targets = {
  'skia': libskia,
}
if 'textlayout' in features
  pkg_lib_targets += {
    'skparagraph': libskparagraph,
    'skshaper': libskshaper,
    'skunicode_core': libskunicode_core,
    'skunicode_icu': libskunicode_icu,
  }
endif

# Collect system dependencies based on platform and features
skia_deps = []

if host_system == 'linux'
  thread_dep = dependency('threads')
  skia_deps += [thread_dep]

  if get_option('embed-freetype').disabled()
    freetype_dep = dependency('freetype2', required: true)
    fontconfig_dep = dependency('fontconfig', required: true)
    skia_deps += [freetype_dep, fontconfig_dep]
  endif

  if get_option('textlayout').enabled() and not get_option('use-system-libraries')
    # When not using system libraries, we still need some runtime deps
    icu_dep = dependency('icu-uc', required: false)
    harfbuzz_dep = dependency('harfbuzz', required: false)
    if icu_dep.found()
      skia_deps += [icu_dep]
    endif
    if harfbuzz_dep.found()
      skia_deps += [harfbuzz_dep]
    endif
  elif get_option('textlayout').enabled()
    icu_dep = dependency('icu-uc', required: true)
    harfbuzz_dep = dependency('harfbuzz', required: true)
    skia_deps += [icu_dep, harfbuzz_dep]
  endif

  if get_option('gl').enabled()
    gl_dep = dependency('gl', required: true)
    skia_deps += [gl_dep]
  endif

  if get_option('x11').enabled()
    x11_dep = dependency('x11', required: true)
    skia_deps += [x11_dep]
  endif

  if get_option('webp-encode').enabled() or get_option('webp-decode').enabled()
    if get_option('use-system-libraries')
      webp_dep = dependency('libwebp', required: true)
      skia_deps += [webp_dep]
    endif
  endif
endif

# Declare Skia dependency for other projects
skia_inc = include_directories('.')

skia_dep = declare_dependency(
  link_with: skia_build,
  include_directories: skia_inc,
  dependencies: skia_deps,
  version: meson.project_version(),
)

# Override the dependency so it can be found via dependency('skia')
meson.override_dependency('skia', skia_dep)

# Libraries are installed via the custom_target install: true parameter above

# Generate pkg-config files using Meson's pkgconfig module
pkg = import('pkgconfig')

# Common pkg-config settings
pkg_variables = {
  'skia_includedir': '${includedir}/skia',
}
pkg_uninstalled_variables = {
  'skia_includedir': '@0@'.format(meson.current_source_dir()),
}

# Use defines from whichever build type was configured
# Prefer static if both were built
defines_map = shared_defines_map
if defines_map == {} and shared_defines_map != {}
  defines_map = static_defines_map
endif

# Define all libraries and their metadata
pkg_libs = {}

# Add textlayout libraries if enabled
if 'textlayout' in features
  pkg_libs += {
    'skparagraph': {
      'description': 'Skia Paragraph Layout Library',
      'requires': ['skia'],
    },
    'skshaper': {
      'description': 'Skia Text Shaping Library',
      'requires': ['skia'],
    },
    'skunicode_core': {
      'description': 'Skia Unicode Core Library',
      'requires': ['skia'],
      'headers_dirs': 'skunicode',
    },
    'skunicode_icu': {
      'description': 'Skia Unicode ICU Library',
      'requires': ['skia', 'skunicode_core'],
      'no_headers': true,
    },
  }

endif

# Install headers
install_subdir('include',
  install_dir: get_option('includedir') / 'skia',
  strip_directory: false,
)

foreach libname, libinfo: pkg_libs
  if libinfo.get('no_headers', false)
    continue
  endif

  headers_dir = libinfo.get('headers_dirs', libname)
  install_subdir(f'modules/@headers_dir@/include',
    install_dir: get_option('includedir') / 'skia' / 'include' / 'modules' / headers_dir,
    strip_directory: false,
  )
endforeach

# Add the base skia library after installing othe libraries heade
pkg_libs += {
  'skia': {
    'description': 'Skia Graphics Library',
    'requires': [],
  },
}

# Add SVG libraries if enabled (when implemented)
if 'svg' in features
  # TODO: Add when svg libraries are properly tracked
  # pkg_libs += {
  #   'svg': {
  #     'description': 'Skia SVG Library',
  #     'requires': ['skia'],
  #   },
  # }
endif

# Generate pkg-config files for all libraries
foreach lib_name, lib_info : pkg_libs
  # Get defines for this specific library, default to empty
  lib_cflags = ['-I${skia_includedir}', '-I${skia_includedir}/include']
  if lib_name in defines_map
    lib_cflags += defines_map[lib_name]
  endif

  # For skia, use the actual target to get the library path (-L)
  # For other libraries, manually specify -L and library name to ensure correct order
  # Use ${prefix} which points to the build dir (uninstalled) or install prefix (installed)
  if lib_name == 'skia'
    lib_arg = [libskia]
  else
    lib_arg = ['-L' + meson.current_build_dir(), '-l' + lib_name]
  endif

  pkg.generate(
    libraries: lib_arg,
    version: meson.project_version(),
    name: lib_name,
    filebase: lib_name,
    description: lib_info['description'],
    unescaped_variables: pkg_variables,
    unescaped_uninstalled_variables: pkg_uninstalled_variables,
    extra_cflags: lib_cflags,
    requires: lib_info.get('requires', []),
  )
endforeach

devenv = environment()
library_path = 'LD_LIBRARY_PATH'
if host_machine.system() == 'darwin'
  library_path = 'DYLD_LIBRARY_PATH'
elif host_machine.system() == 'windows'
  library_path = 'PATH'
endif
devenv.prepend(library_path, meson.current_build_dir())
meson.add_devenv(devenv)

summary({
  'Features': features,
  'Library type': default_library,
  'Use system libraries': get_option('use-system-libraries'),
}, section: 'Configuration', bool_yn: true)
