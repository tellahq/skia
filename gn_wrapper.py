#!/usr/bin/env python3
"""
GN/Ninja wrapper for building Skia with Meson.

- Configures Skia using GN with appropriate arguments
- Builds Skia using Ninja
- Copies libraries to the build directory
- Generates depfiles for Meson dependency tracking
"""

import argparse
import os
import platform
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List


class SkiaBuilder:
    """Handles Skia build configuration and execution."""

    def __init__(self, args):
        self.args = args
        self.host_system = platform.system().lower()
        self.build_dir = Path(args.build_dir)
        self.src_dir = Path(args.src_dir)
        self.target = args.target
        self.prefix = Path(args.prefix)
        self.libdir = Path(args.libdir)
        self.is_debug = self.target == "debug"
        self.features = set(args.features) if args.features else set()
        self.use_system_libs = args.use_system_libraries

        # Determine library extensions
        if self.host_system == "windows":
            self.ext_shared = "dll"
            self.ext_static = "lib"
        elif self.host_system == "darwin":
            self.ext_shared = "dylib"
            self.ext_static = "a"
        else:  # Linux and others
            self.ext_shared = "so"
            self.ext_static = "a"

        # Determine which library types to build
        self.build_shared = args.library_type == "shared"
        self.build_static = not self.build_shared

        self.output_dir = (
            self.build_dir
            / "skia_build"
            / ("shared" if self.build_shared else "static")
        )

        # Open log file
        logdir = args.root_dir / "meson-logs"
        logdir.mkdir(parents=True, exist_ok=True)
        self.logfile = open(
            logdir / "gn-wrapper.log", "w", buffering=1, encoding="utf-8"
        )
        print(f"Args: {args}", file=self.logfile)

    def log(self, msg: str):
        """Log a message to logfile only."""
        print(msg, file=self.logfile)

    def get_target_triple(self) -> str:
        """Get the target triple for the current platform."""
        if self.host_system == "darwin":
            # Get arch
            arch = platform.machine()
            if arch == "arm64":
                return "aarch64-apple-darwin"
            else:
                return "x86_64-apple-darwin"
        elif self.host_system == "linux":
            arch = platform.machine()
            if arch == "x86_64":
                return "x86_64-unknown-linux-gnu"
            elif arch == "aarch64":
                return "aarch64-unknown-linux-gnu"
            else:
                return f"{arch}-unknown-linux-gnu"
        elif self.host_system == "windows":
            arch = platform.machine()
            if arch == "AMD64":
                return "x86_64-pc-windows-msvc"
            else:
                return f"{arch}-pc-windows-msvc"
        return ""

    def get_gn_args(self) -> List[str]:
        """Build GN arguments based on features and configuration."""
        gn_args = []

        if self.args.compiler == "clang":
            cc = "clang"
            cxx = "clang++"
        elif self.args.compiler == "gcc":
            cc = "gcc"
            cxx = "g++"
        elif self.args.compiler == "msvc":
            cc = "cl"
            cxx = "cl"
        else:
            raise ValueError(f"Unsupported compiler: {self.args.compiler}")

        # Basic build configuration
        gn_args.append(f"is_official_build={str(not self.is_debug).lower()}")
        gn_args.append(f"is_debug={str(self.is_debug).lower()}")
        gn_args.append("treat_warnings_as_errors=false")

        # Set compilers
        gn_args.append(f'cc="{cc}"')
        gn_args.append(f'cxx="{cxx}"')

        # Set target OS and architecture
        target_cpu = platform.machine()
        if target_cpu == "aarch64":
            target_cpu = "arm64"
        elif target_cpu == "x86_64" or target_cpu == "AMD64":
            target_cpu = "x64"
        elif target_cpu == "i686" or target_cpu == "i386":
            target_cpu = "x86"
        elif target_cpu == "riscv64gc":
            target_cpu = "riscv64"

        if self.host_system == "darwin":
            gn_args.append('target_os="mac"')
            gn_args.append(f'target_cpu="{target_cpu}"')
        elif self.host_system == "linux":
            gn_args.append('target_os="linux"')
            gn_args.append(f'target_cpu="{target_cpu}"')
        elif self.host_system == "windows":
            gn_args.append('target_os="win"')
            gn_args.append(f'target_cpu="{target_cpu}"')

        # Add extra_cflags if needed (deployment target defines for macOS)
        extra_cflags = []
        extra_cflags_cc = []

        # For shared libraries, override default symbol visibility
        # Skia's BUILD.gn sets -fvisibility=hidden by default, but we need symbols exported
        if self.build_shared:
            extra_cflags.append('"-fvisibility=default"')

        # Add macOS deployment target defines and C++ include path if set
        if self.host_system == "darwin":
            # Get CPPFLAGS from environment if set (for C++ include paths)
            cppflags = os.environ.get("CPPFLAGS", "")
            if cppflags:
                # Parse CPPFLAGS and add to extra_cflags_cc
                for flag in cppflags.split():
                    if flag.strip():
                        extra_cflags_cc.append(f'"{flag}"')

            deployment_target = os.environ.get("MACOSX_DEPLOYMENT_TARGET")
            if deployment_target:
                # Convert to 6-digit format (e.g., "10.16" -> "101600")
                parts = deployment_target.split(".")
                joined = "".join(parts)
                target_6 = joined.ljust(6, "0")
                extra_cflags.append(f'"-D__MAC_OS_X_VERSION_MIN_REQUIRED={target_6}"')
                extra_cflags.append(f'"-D__MAC_OS_X_VERSION_MAX_ALLOWED={target_6}"')

        if extra_cflags:
            gn_args.append(f"extra_cflags=[{','.join(extra_cflags)}]")

        if extra_cflags_cc:
            gn_args.append(f"extra_cflags_cc=[{','.join(extra_cflags_cc)}]")

        # Features
        gn_args.append(
            f"skia_enable_svg={'true' if 'svg' in self.features else 'false'}"
        )
        gn_args.append(
            f"skia_enable_pdf={'true' if 'pdf' in self.features else 'false'}"
        )

        # GPU backends
        has_gpu = any(f in self.features for f in ["gl", "vulkan", "metal", "d3d"])
        gn_args.append(f"skia_enable_ganesh={str(has_gpu).lower()}")
        gn_args.append(f"skia_use_gl={'true' if 'gl' in self.features else 'false'}")
        gn_args.append(f"skia_use_egl={'true' if 'egl' in self.features else 'false'}")
        gn_args.append(f"skia_use_x11={'true' if 'x11' in self.features else 'false'}")

        if "vulkan" in self.features:
            gn_args.append("skia_use_vulkan=true")
            gn_args.append("skia_enable_spirv_validation=false")

        if "metal" in self.features:
            gn_args.append("skia_use_metal=true")

        if "d3d" in self.features:
            gn_args.append("skia_use_direct3d=true")

        # Text layout
        if "textlayout" in self.features:
            gn_args.append("skia_enable_skshaper=true")
            gn_args.append("skia_use_icu=true")
            gn_args.append(f"skia_use_system_icu={str(self.use_system_libs).lower()}")
            gn_args.append("skia_use_harfbuzz=true")
            gn_args.append("skia_pdf_subset_harfbuzz=true")
            gn_args.append(
                f"skia_use_system_harfbuzz={str(self.use_system_libs).lower()}"
            )
            gn_args.append("skia_enable_skparagraph=true")
        else:
            gn_args.append("skia_use_icu=false")
            gn_args.append("skia_use_harfbuzz=false")

        # WebP support
        if "webp-encode" in self.features or "webp-decode" in self.features:
            gn_args.append(
                f"skia_use_system_libwebp={str(self.use_system_libs).lower()}"
            )
        gn_args.append(
            f"skia_use_libwebp_encode={'true' if 'webp-encode' in self.features else 'false'}"
        )
        gn_args.append(
            f"skia_use_libwebp_decode={'true' if 'webp-decode' in self.features else 'false'}"
        )

        # System libraries
        gn_args.append(f"skia_use_system_libpng={str(self.use_system_libs).lower()}")
        gn_args.append(f"skia_use_system_zlib={str(self.use_system_libs).lower()}")
        gn_args.append(
            f"skia_use_system_libjpeg_turbo={str(self.use_system_libs).lower()}"
        )

        # FreeType (Linux/Unix)
        if self.host_system in ["linux", "freebsd", "openbsd"]:
            use_freetype = True
            gn_args.append("skia_use_freetype=true")
            if "embed-freetype" in self.features:
                gn_args.append("skia_use_system_freetype2=false")
            else:
                gn_args.append(
                    f"skia_use_system_freetype2={str(not self.use_system_libs).lower()}"
                )
                # Add system freetype include path to extra_cflags list
                extra_cflags.append('"-I/usr/include/freetype2"')

            if "freetype-woff2" in self.features:
                gn_args.append("skia_use_freetype_woff2=true")
        else:
            gn_args.append("skia_use_freetype=false")

        # Disable unused features
        gn_args.append("skia_enable_skottie=false")
        gn_args.append("skia_use_xps=false")
        gn_args.append("skia_use_dng_sdk=false")
        gn_args.append("skia_use_expat=true")
        gn_args.append(f"skia_use_system_expat={str(self.use_system_libs).lower()}")

        # Debug-specific settings
        if self.is_debug:
            gn_args.append("skia_enable_spirv_validation=false")
            gn_args.append("skia_enable_tools=false")
            gn_args.append("skia_enable_vulkan_debug_layers=false")
            gn_args.append("skia_use_libheif=false")
            gn_args.append("skia_use_lua=false")

        # Library type - GN builds static by default, shared needs special handling
        if self.build_shared:
            gn_args.append("is_component_build=true")

        return gn_args

    def fetch_gn(self):
        """Fetch GN binary if not present."""
        gn_binary = self.src_dir / "bin" / "gn"
        if gn_binary.exists():
            return

        self.log("GN binary not found, fetching...")
        fetch_gn_script = self.src_dir / "bin" / "fetch-gn"

        if not fetch_gn_script.exists():
            raise FileNotFoundError(f"fetch-gn script not found at {fetch_gn_script}")

        python = self.find_python3()
        result = subprocess.run(
            [python, str(fetch_gn_script)],
            cwd=self.src_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        print(result.stdout, file=self.logfile)
        if result.returncode != 0:
            self.log(f"fetch-gn failed with exit code {result.returncode}")
            raise RuntimeError("Failed to fetch GN binary")

        if not gn_binary.exists():
            raise FileNotFoundError(
                f"GN binary still not found after fetch at {gn_binary}"
            )

        self.log("GN binary fetched successfully")

    def run_gn(self):
        """Configure Skia build with GN."""
        self.fetch_gn()
        gn_binary = self.src_dir / "bin" / "gn"

        # Find Python 3
        python = self.find_python3()

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Build GN command
        gn_args = self.get_gn_args()
        args_str = " ".join(gn_args)

        self.log(f"Configuring Skia with GN:")
        self.log(f"  Output dir: {self.output_dir}")
        self.log(f"  GN args: {args_str}")

        cmd = [
            str(gn_binary),
            "gen",
            str(self.output_dir),
            f"--script-executable={python}",
            f"--args={args_str}",
        ]

        self.log(f"Running: {shlex.join(cmd)}")
        result = subprocess.run(
            cmd,
            cwd=self.src_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        print(result.stdout, file=self.logfile)
        if result.returncode != 0:
            self.log(f"GN failed with exit code {result.returncode}")
            self.log(result.stdout)
            sys.exit(1)

        # Extract and print defines for pkg-config
        self.extract_and_print_defines()

    def run_ninja(self):
        """Build Skia with Ninja."""
        ninja = shutil.which("ninja")
        if not ninja:
            raise FileNotFoundError("Ninja not found in PATH")

        # Determine which libraries to build
        targets = ["skia"]
        if "textlayout" in self.features:
            targets.extend(
                ["skparagraph", "skshaper", "skunicode_core", "skunicode_icu"]
            )
        if "svg" in self.features:
            targets.extend(["svg", "skresources"])

        self.log(f"Building Skia with Ninja:")
        self.log(f"  Targets: {targets}")

        cmd = [ninja, "-C", str(self.output_dir)] + targets

        self.log(f"Running: {shlex.join(cmd)}")
        result = subprocess.run(cmd)

        if result.returncode != 0:
            self.log(f"Ninja failed with exit code {result.returncode}")
            sys.exit(1)

    def copy_libraries(self):
        """Copy built libraries to the build directory."""
        self.log("Copying libraries to build directory:")

        # Libraries to copy
        libs = ["libskia"]
        if "textlayout" in self.features:
            libs.extend(
                [
                    "libskparagraph",
                    "libskshaper",
                    "libskunicode_core",
                    "libskunicode_icu",
                ]
            )
        if "svg" in self.features:
            libs.extend(["libsvg", "libskresources"])

        for lib in libs:
            if self.build_static:
                static_lib = f"{lib}.{self.ext_static}"
                src = self.output_dir / static_lib
                dst = self.build_dir / static_lib
                if src.exists():
                    shutil.copy2(src, dst)
                    self.log(f"  Copied {static_lib}")
                else:
                    self.log(f"  Warning: {static_lib} not found")
            else:
                shared_lib = f"{lib}.{self.ext_shared}"
                src = self.output_dir / shared_lib
                dst = self.build_dir / shared_lib
                if src.exists():
                    shutil.copy2(src, dst)
                    self.log(f"  Copied {shared_lib}")
                else:
                    self.log(f"  Warning: {shared_lib} not found")

        # Copy additional files (like icudtl.dat for Windows textlayout)
        if "textlayout" in self.features and self.host_system == "windows":
            icudtl = self.output_dir / "icudtl.dat"
            if icudtl.exists():
                shutil.copy2(icudtl, self.build_dir / "icudtl.dat")
                self.log("  Copied icudtl.dat")

    def generate_depfile(self):
        """Generate Meson depfile using Ninja's dependency database."""
        if not self.args.depfile:
            return

        ninja = shutil.which("ninja")

        # Query Ninja's dependency database for all dependencies
        try:
            result = subprocess.run(
                [ninja, "-C", str(self.output_dir), "-t", "deps"],
                capture_output=True,
                text=True,
                check=False,
            )

            deps = set()
            for line in result.stdout.split("\n"):
                # Dependency lines are indented and start with whitespace
                if line.startswith("    "):
                    dep_line = line.strip()
                    # Only include source files from the Skia source tree
                    if dep_line.startswith("../../"):
                        dep_path = self.src_dir / dep_line[6:]  # Remove ../../
                        if dep_path.exists():
                            deps.add(str(dep_path))

            # Generate Makefile-style depfile
            # Output files are the built libraries
            outputs = []
            if self.build_static:
                outputs.append(str(self.build_dir / f"libskia.{self.ext_static}"))
            else:
                outputs.append(str(self.build_dir / f"libskia.{self.ext_shared}"))

            # Write depfile
            if deps:
                with open(self.args.depfile, "w") as f:
                    f.write(f"{' '.join(outputs)}: \\\n")
                    dep_list = sorted(deps)
                    for i, dep in enumerate(dep_list):
                        if i < len(dep_list) - 1:
                            f.write(f"  {dep} \\\n")
                        else:
                            f.write(f"  {dep}\n")

                self.log(
                    f"Generated depfile: {self.args.depfile} ({len(deps)} dependencies)"
                )
            else:
                self.log("Warning: No dependencies found, skipping depfile generation")

        except Exception as e:
            self.log(f"Warning: Failed to generate depfile: {e}")
            import traceback

            traceback.print_exc(file=self.logfile)

    def extract_and_print_defines(self):
        """Extract defines from ninja files and print per-library to stdout."""
        # Map library names to their ninja files
        ninja_file_map = {
            "skia": ["obj/skia.ninja"],
        }

        # Add GPU defines to skia if any GPU backend enabled
        if any(f in self.features for f in ["gl", "vulkan", "metal", "d3d"]):
            ninja_file_map["skia"].append("obj/gpu.ninja")

        if "textlayout" in self.features:
            ninja_file_map["skshaper"] = ["obj/modules/skshaper/skshaper.ninja"]
            ninja_file_map["skparagraph"] = [
                "obj/modules/skparagraph/skparagraph.ninja"
            ]
            ninja_file_map["skunicode_core"] = [
                "obj/modules/skunicode/skunicode_core.ninja"
            ]
            ninja_file_map["skunicode_icu"] = [
                "obj/modules/skunicode/skunicode_icu.ninja"
            ]

            # ICU defines also needed for skia when using textlayout
            if not self.use_system_libs:
                ninja_file_map["skia"].append("obj/third_party/icu/icu.ninja")

        if "svg" in self.features:
            ninja_file_map["svg"] = ["obj/modules/svg/svg.ninja"]

        # Extract defines for each library
        for lib_name, ninja_files in ninja_file_map.items():
            lib_defines = set()

            for ninja_file in ninja_files:
                full_path = self.output_dir / ninja_file
                if not full_path.exists():
                    self.log(f"ERROR: Required ninja file not found: {full_path}")
                    sys.exit(1)

                with open(full_path, "r") as f:
                    for line in f:
                        if line.startswith("defines = "):
                            defines_str = line[10:].strip()
                            lib_defines.update(defines_str.split())
                            break
                    else:
                        self.log(f"ERROR: No 'defines =' line in {full_path}")
                        sys.exit(1)

            # Print in format: SKIA_DEFINES:libname:defines
            if lib_defines:
                print(f"SKIA_DEFINES:{lib_name}:{' '.join(sorted(lib_defines))}")

    def find_python3(self) -> str:
        """Find Python 3 executable."""
        for cmd in ["python3", "python"]:
            try:
                result = subprocess.run(
                    [cmd, "--version"], capture_output=True, text=True
                )
                if "Python 3" in result.stdout or "Python 3" in result.stderr:
                    return cmd
            except FileNotFoundError:
                continue
        raise FileNotFoundError("Python 3 not found")

    def sync_deps(self):
        """Synchronize Skia dependencies using git-sync-deps."""
        if self.args.offline:
            self.log("Offline mode, skipping dependency sync")
            return

        python = self.find_python3()
        sync_script = self.src_dir / "tools" / "git-sync-deps"

        if not sync_script.exists():
            self.log("Warning: git-sync-deps not found, skipping")
            return

        self.log("Synchronizing Skia dependencies...")

        env = os.environ.copy()
        env["GIT_SYNC_DEPS_PATH"] = str(self.src_dir / "DEPS")
        env["GIT_SYNC_DEPS_SKIP_EMSDK"] = "1"

        result = subprocess.run(
            [python, str(sync_script)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        print(result.stdout, file=self.logfile)
        if result.returncode != 0:
            self.log(
                f"Warning: git-sync-deps failed with exit code {result.returncode}"
            )

    def build(self):
        """Execute the complete build process."""
        start_time = time.time()

        try:
            self.log(f"Starting Skia build in {self.output_dir}")
            self.log(f"Features: {sorted(self.features)}")
            self.log(f"Library type: {self.args.library_type}")

            if self.args.build_only:
                # Build-only mode: just run ninja
                self.run_ninja()
                self.copy_libraries()
                self.generate_depfile()
            elif self.args.configure_only:
                # Configure-only mode: just run GN
                self.sync_deps()
                self.run_gn()
            else:
                # Full build: sync, configure, build
                self.sync_deps()
                self.run_gn()
                self.run_ninja()
                self.copy_libraries()
                self.generate_depfile()

            elapsed = time.time() - start_time
            self.log(f"Completed successfully in {elapsed:.1f}s")

        except Exception as e:
            self.log(f"Build failed: {e}")
            import traceback

            traceback.print_exc(file=self.logfile)
            sys.exit(1)
        finally:
            self.logfile.close()


def main():
    parser = argparse.ArgumentParser(description="GN/Ninja wrapper for building Skia")
    parser.add_argument("compiler", help="The compiler ID")
    parser.add_argument("build_dir", type=Path, help="Meson build directory")
    parser.add_argument("src_dir", type=Path, help="Skia source directory")
    parser.add_argument("root_dir", type=Path, help="Meson root build directory")
    parser.add_argument("target", choices=["debug", "release"], help="Build target")
    parser.add_argument("prefix", type=Path, help="Installation prefix")
    parser.add_argument(
        "libdir", type=Path, help="Library directory relative to prefix"
    )
    parser.add_argument(
        "--features", nargs="+", default=[], help="Skia features to enable"
    )
    parser.add_argument(
        "--library-type",
        choices=["static", "shared"],
        default="static",
        help="Library type to build",
    )
    parser.add_argument(
        "--use-system-libraries",
        action="store_true",
        help="Use system libraries instead of bundled ones",
    )
    parser.add_argument("--depfile", type=Path, help="Output depfile for Meson")
    parser.add_argument("--version")
    parser.add_argument("--offline", action="store_true", help="Skip dependency sync")
    parser.add_argument(
        "--configure-only",
        action="store_true",
        help="Only run GN configuration, skip build",
    )
    parser.add_argument(
        "--build-only", action="store_true", help="Only run Ninja build, skip GN"
    )

    args = parser.parse_args()

    builder = SkiaBuilder(args)
    builder.build()


if __name__ == "__main__":
    main()
