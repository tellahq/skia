# ============================================================================
# Install Skia headers
# ============================================================================
# This file handles the installation of all Skia headers required for:
# 1. Public API usage (include/ directory)
# 2. Language bindings that need access to implementation headers
# 3. Modules like textlayout (skparagraph, skshaper, skunicode)
# ============================================================================

# Install main public headers
install_subdir('.',
  install_dir: get_option('includedir') / 'skia' / 'include',
  strip_directory: true,
  exclude_files: ['meson.build', 'BUILD.bazel', 'OWNERS'],
)

# The list_headers script generates a list of all headers in a directory
list_headers = find_program('list_headers.py')

# modules/skcms headers:
#    - Public Skia headers like include/core/SkColorSpace.h include
#      "modules/skcms/skcms.h" and "modules/skcms/src/skcms_public.h"
#    - These are transitively required by any code using color management APIs
install_headers('../modules/skcms/skcms.h',
  subdir: 'skia' / 'modules' / 'skcms',
)
install_headers(
  files(run_command(
    list_headers,
    meson.current_source_dir(),
    meson.current_source_dir() / '..' / 'modules' / 'skcms' / 'src',
    check: true,
    capture: true
  ).stdout().strip().split('\n')),
  subdir: 'skia' / 'modules' / 'skcms' / 'src',
  preserve_path: false,
)

# src/gpu/ganesh headers:
#    - FFI wrapper code needs internal GPU headers like
#      "src/gpu/ganesh/gl/GrGLDefines.h" to expose low-level GL functionality
#    - Without these: fatal error: src/gpu/ganesh/gl/GrGLDefines.h: No such file
#
install_headers(
  files(run_command(
    list_headers,
    meson.current_source_dir(),
    meson.current_source_dir() / '..' / 'src' / 'gpu' / 'ganesh' / 'gl',
    check: true,
    capture: true
  ).stdout().strip().split('\n')),
  subdir: 'skia' / 'src' / 'gpu' / 'ganesh' / 'gl',
  preserve_path: false,
)

# src/base and src/core headers:
#   - Module public headers (svg, skparagraph) include private utilities like
#     "src/base/SkTLazy.h", "src/core/SkTHash.h", and "src/core/SkLRUCache.h"
#   - These are needed when compiling against the skparagraph or svg modules
install_headers(
  files(run_command(
    list_headers,
    meson.current_source_dir(),
    meson.current_source_dir() / '..' / 'src' / 'base',
    check: true,
    capture: true
  ).stdout().strip().split('\n')),
  subdir: 'skia' / 'src' / 'base',
  preserve_path: false,
)

install_headers(
  files(run_command(
    list_headers,
    meson.current_source_dir(),
    meson.current_source_dir() / '..' / 'src' / 'core',
    check: true,
    capture: true
  ).stdout().strip().split('\n')),
  subdir: 'skia' / 'src' / 'core',
  preserve_path: false,
)

# Install module-specific headers for textlayout libraries
if 'textlayout' in features
  # skparagraph headers
  install_subdir('../modules/skparagraph/include',
    install_dir: get_option('includedir') / 'skia' / 'include' / 'modules' / 'skparagraph',
    strip_directory: true,
  )

  # Also install under skia/modules/skparagraph/include so includes starting at "modules/..."
  # resolve when consumers only pass -I/usr/include/skia (common with pkg-config cflags)
  install_subdir('../modules/skparagraph/include',
    install_dir: get_option('includedir') / 'skia' / 'modules' / 'skparagraph' / 'include',
    strip_directory: true,
  )

  # skshaper headers
  install_subdir('../modules/skshaper/include',
    install_dir: get_option('includedir') / 'skia' / 'include' / 'modules' / 'skshaper',
    strip_directory: true,
  )

  install_subdir('../modules/skshaper/include',
    install_dir: get_option('includedir') / 'skia' / 'modules' / 'skshaper' / 'include',
    strip_directory: true,
  )

  # skunicode headers
  install_subdir('../modules/skunicode/include',
    install_dir: get_option('includedir') / 'skia' / 'include' / 'modules' / 'skunicode',
    strip_directory: true,
  )

  install_subdir('../modules/skunicode/include',
    install_dir: get_option('includedir') / 'skia' / 'modules' / 'skunicode' / 'include',
    strip_directory: true,
  )
endif

# Install SVG module headers if enabled
if 'svg' in features
  install_subdir('../modules/svg/include',
    install_dir: get_option('includedir') / 'skia' / 'include' / 'modules' / 'svg',
    strip_directory: true,
  )

  install_subdir('../modules/svg/include',
    install_dir: get_option('includedir') / 'skia' / 'modules' / 'svg' / 'include',
    strip_directory: true,
  )

  # skresources headers (needed by svg)
  install_subdir('../modules/skresources/include',
    install_dir: get_option('includedir') / 'skia' / 'include' / 'modules' / 'skresources',
    strip_directory: true,
  )

  install_subdir('../modules/skresources/include',
    install_dir: get_option('includedir') / 'skia' / 'modules' / 'skresources' / 'include',
    strip_directory: true,
  )
endif
