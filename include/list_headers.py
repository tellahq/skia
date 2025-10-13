#!/usr/bin/env python3
"""List all .h header files in a directory recursively, output paths relative to a base."""

import os
import sys

if len(sys.argv) != 3:
    print("Usage: list_headers.py <base_dir> <scan_dir>", file=sys.stderr)
    sys.exit(1)

base_dir = sys.argv[1]  # Directory to make paths relative to (e.g., where meson.build is)
scan_dir = sys.argv[2]  # Directory to scan for headers

headers = []
for root, dirs, files in os.walk(scan_dir):
    for f in files:
        if f.endswith('.h'):
            # Output path relative to base_dir
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, base_dir)
            headers.append(rel_path)

# Only print if we have headers (avoid empty lines)
if headers:
    print('\n'.join(headers))
