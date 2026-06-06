#!/usr/bin/env python3
#
# Copyright 2025 Google LLC
#
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
"""Builds Dawn using CMake.

This script configures and builds Dawn using CMake and Ninja. It then
discovers all object files for the specified libraries and combines them
into static archives (.a files) using `ar`. It also copies Dawn's generated
headers to the location GN expects.
"""

import argparse
import os
import shutil
import subprocess
import sys

from cmake_utils import (add_common_cmake_args, combine_into_library,
                         discover_dependencies, get_cmake_os_cpu,
                         get_windows_settings, quote_if_needed, write_depfile,
                         get_third_party_locations)


def gn_bool_to_cmake(s):
  if s.lower() == "true":
    return "ON"
  return "OFF"


def main():
  parser = argparse.ArgumentParser(description="Build Dawn using CMake.")
  add_common_cmake_args(parser)
  parser.add_argument(
      "--gen_dir",
      required=True,
      help="Directory for generated files (e.g., depfile and headers).")
  parser.add_argument(
      "--android_ndk_path", default="", help="Path to the Android NDK.")
  parser.add_argument(
      "--android_platform",
      default="",
      help="Android platform (e.g., android-29).")
  parser.add_argument(
      "--dawn_enable_d3d11", default="false", help="Enable D3D11 backend.")
  parser.add_argument(
      "--dawn_enable_d3d12", default="false", help="Enable D3D12 backend.")
  parser.add_argument(
      "--dawn_enable_opengles", default="false", help="Enable GLES backend.")
  parser.add_argument(
      "--dawn_enable_metal", default="false", help="Enable Metal backend.")
  parser.add_argument(
      "--dawn_enable_vulkan", default="false", help="Enable Vulkan backend.")
  args = parser.parse_args()

  cmake_exe = shutil.which("cmake")
  if not cmake_exe:
    print("Error: cmake not found in PATH.")
    sys.exit(1)

  ninja_exe = shutil.which("ninja")
  if not ninja_exe:
    print("Error: ninja not found in PATH.")
    sys.exit(1)

  target_os, target_cpu = get_cmake_os_cpu(args.target_os, args.target_cpu)

  output_path = args.output_path
  gen_dir = args.gen_dir
  # The headers are a dependency for all libraries.
  # We want to build the other listed dawn components into one big library.
  build_targets = ["webgpu_headers_gen", "dawn_proc", "dawn_native"]
  depfile_path = args.depfile_path

  script_dir = os.path.dirname(os.path.realpath(__file__))

  dawn_dir = os.path.join(script_dir, "..", "externals", "dawn")
  build_dir = args.build_dir

  configure_cmd = [
      cmake_exe,
      "-S",
      dawn_dir,
      "-B",
      build_dir,
      "-G",
      "Ninja",
      f"-DCMAKE_MAKE_PROGRAM={ninja_exe}",
      f"--install-prefix={os.path.abspath(gen_dir)}",
      f"-DCMAKE_SYSTEM_NAME={target_os}",
      f"-DCMAKE_SYSTEM_PROCESSOR={target_cpu}",
      "-DDAWN_BUILD_MONOLITHIC_LIBRARY=OFF",
      f"-DCMAKE_BUILD_TYPE={args.build_type}",
      # Explicitly set the C++ standard to avoid issues with CMake's feature
      # detection for Clang on Windows.
      "-DCMAKE_CXX_STANDARD=20",
      "-DCMAKE_CXX_STANDARD_REQUIRED=ON",
      "-DCMAKE_CXX_EXTENSIONS=OFF",
      "-DDAWN_FORCE_SYSTEM_COMPONENT_LOAD=ON", # https://g-issues.chromium.org/issues/399358291
      "-DDAWN_ENABLE_INSTALL=OFF",
      "-DTINT_ENABLE_INSTALL=OFF",
      f"-DDAWN_ENABLE_D3D11={gn_bool_to_cmake(args.dawn_enable_d3d11)}",
      f"-DDAWN_ENABLE_D3D12={gn_bool_to_cmake(args.dawn_enable_d3d12)}",
      "-DDAWN_ENABLE_DESKTOP_GL=OFF",
      f"-DDAWN_ENABLE_OPENGLES={gn_bool_to_cmake(args.dawn_enable_opengles)}",
      f"-DDAWN_ENABLE_METAL={gn_bool_to_cmake(args.dawn_enable_metal)}",
      f"-DDAWN_ENABLE_VULKAN={gn_bool_to_cmake(args.dawn_enable_vulkan)}",
  ]
  configure_cmd += get_third_party_locations()

  if args.enable_rtti:
    configure_cmd.append("-DDAWN_ENABLE_RTTI=ON")

  cxx_flags = args.cxx_flags or []
  ld_flags = args.ld_flags or []

  if target_os == "Windows":
    win_cfgs, win_cxx, win_ld = get_windows_settings(args)
    configure_cmd += win_cfgs
    cxx_flags += win_cxx
    ld_flags += win_ld

    # The D3D backend requires the HLSL writer.
    configure_cmd.append("-DTINT_BUILD_HLSL_WRITER=ON")
  else:
    configure_cmd.append("-DTINT_BUILD_HLSL_WRITER=OFF")
    cxx_flags.append("-w") # Silence warnings

  if cxx_flags:
    c_cxx_flags_str = " ".join(cxx_flags)
    # -fno-rtti is not a valid C flag.
    c_flags = [f for f in cxx_flags if f != "-fno-rtti"]
    c_flags_str = " ".join(c_flags)
    configure_cmd.append(f"-DCMAKE_C_FLAGS={c_flags_str}")
    configure_cmd.append(f"-DCMAKE_CXX_FLAGS={c_cxx_flags_str}")

  if ld_flags:
    ld_flags_str = " ".join(ld_flags)
    configure_cmd.append(f"-DCMAKE_EXE_LINKER_FLAGS={ld_flags_str}")
    configure_cmd.append(f"-DCMAKE_SHARED_LINKER_FLAGS={ld_flags_str}")
    configure_cmd.append(f"-DCMAKE_MODULE_LINKER_FLAGS={ld_flags_str}")

  if target_os == "Android":
    configure_cmd.append(f"-DCMAKE_TOOLCHAIN_FILE={args.android_ndk_path}/build/cmake/android.toolchain.cmake")
    configure_cmd.append(f"-DANDROID_ABI={target_cpu}")
    configure_cmd.append(f"-DANDROID_PLATFORM={args.android_platform}")
  else:
    configure_cmd.append(f"-DCMAKE_C_COMPILER={args.cc.replace(os.sep, '/')}")
    configure_cmd.append(f"-DCMAKE_CXX_COMPILER={args.cxx.replace(os.sep, '/')}")

  if target_os == "Darwin" or target_os == "iOS":
    configure_cmd.append(f"-DCMAKE_OSX_ARCHITECTURES={target_cpu}")

  env = os.environ.copy()
  # Don't write .pyc files, which can cause race conditions when building
  # tint and dawn in parallel.
  env["PYTHONDONTWRITEBYTECODE"] = "1"

  if target_os == "Windows":
    # Set the WINDOWSSDKDIR environment variable to ensure that Dawn's
    # DetectWindowsSDK function uses the correct, hermetic SDK path.
    env["WINDOWSSDKDIR"] = args.win_sdk

  print(" ".join(configure_cmd))
  print("with environment", env)
  subprocess.run(configure_cmd, check=True, env=env)

  # Dawn/Tint currently fails under Linux clang with -pedantic-errors unless
  # this dependent type is explicitly marked as a typename.
  tint_vector = os.path.join(dawn_dir, "src", "tint", "utils", "containers",
                             "vector.h")
  with open(tint_vector, "r", encoding="utf-8") as f:
    tint_vector_contents = f.read()
  tint_vector_contents = tint_vector_contents.replace(
      "using VectorCommonType =\n"
      "    tint::internal::VectorCommonType<IsCastable<std::remove_pointer_t<Ts>...>, Ts...>::type;",
      "using VectorCommonType =\n"
      "    typename tint::internal::VectorCommonType<IsCastable<std::remove_pointer_t<Ts>...>, Ts...>::type;")
  with open(tint_vector, "w", encoding="utf-8") as f:
    f.write(tint_vector_contents)

  tint_multiplanar = os.path.join(dawn_dir, "src", "tint", "lang", "core",
                                  "ir", "transform",
                                  "multiplanar_external_texture.cc")
  with open(tint_multiplanar, "r", encoding="utf-8") as f:
    tint_multiplanar_contents = f.read()
  tint_multiplanar_contents = tint_multiplanar_contents.replace(
      "struct overloaded : Ts... {\n"
      "    using Ts::operator()...;\n"
      "};\n",
      "struct overloaded : Ts... {\n"
      "    using Ts::operator()...;\n"
      "};\n"
      "template <class... Ts>\n"
      "overloaded(Ts...) -> overloaded<Ts...>;\n")
  with open(tint_multiplanar, "w", encoding="utf-8") as f:
    f.write(tint_multiplanar_contents)

  dawn_mutex_protected = os.path.join(dawn_dir, "src", "dawn", "common",
                                      "MutexProtected.h")
  with open(dawn_mutex_protected, "r", encoding="utf-8") as f:
    dawn_mutex_protected_contents = f.read()
  dawn_mutex_protected_contents = dawn_mutex_protected_contents.replace(
      "Guard(T* obj, Traits::LockType&& lock, class Defer* defer = nullptr)",
      "Guard(T* obj, typename Traits::LockType&& lock, class Defer* defer = nullptr)")
  dawn_mutex_protected_contents = dawn_mutex_protected_contents.replace(
      "CondVarGuard(T* obj, Traits::MutexType& mutex, std::condition_variable* cv)",
      "CondVarGuard(T* obj, typename Traits::MutexType& mutex, std::condition_variable* cv)")
  dawn_mutex_protected_contents = dawn_mutex_protected_contents.replace(
      "mutable Traits::MutexType mMutex;",
      "mutable typename Traits::MutexType mMutex;")
  with open(dawn_mutex_protected, "w", encoding="utf-8") as f:
    f.write(dawn_mutex_protected_contents)

  dawn_tint_utils = os.path.join(dawn_dir, "src", "dawn", "native",
                                 "TintUtils.h")
  with open(dawn_tint_utils, "r", encoding="utf-8") as f:
    dawn_tint_utils_contents = f.read()
  dawn_tint_utils_contents = dawn_tint_utils_contents.replace(
      "for (const auto& [bindingNumber, apiBindingIndex] : bgl->GetBindingMap()) {\n"
      "            if (!(bgl->GetAPIBindingInfo(apiBindingIndex).visibility & StageBit(stage))) {",
      "for (const auto& bindingEntry : bgl->GetBindingMap()) {\n"
      "            const auto& bindingNumber = bindingEntry.first;\n"
      "            const auto& apiBindingIndex = bindingEntry.second;\n"
      "\n"
      "            if (!(bgl->GetAPIBindingInfo(apiBindingIndex).visibility & StageBit(stage))) {")
  with open(dawn_tint_utils, "w", encoding="utf-8") as f:
    f.write(dawn_tint_utils_contents)

  dawn_command_buffer_vk = os.path.join(dawn_dir, "src", "dawn", "native",
                                        "vulkan", "CommandBufferVk.cpp")
  with open(dawn_command_buffer_vk, "r", encoding="utf-8") as f:
    dawn_command_buffer_vk_contents = f.read()
  dawn_command_buffer_vk_contents = dawn_command_buffer_vk_contents.replace(
      "using PipelineSpecialization = Pipeline::Specialization;",
      "using PipelineSpecialization = typename Pipeline::Specialization;")
  with open(dawn_command_buffer_vk, "w", encoding="utf-8") as f:
    f.write(dawn_command_buffer_vk_contents)

  dawn_queue = os.path.join(dawn_dir, "src", "dawn", "native", "Queue.cpp")
  with open(dawn_queue, "r", encoding="utf-8") as f:
    dawn_queue_contents = f.read()
  dawn_queue_contents = dawn_queue_contents.replace(
      "for (auto [j, texture] : Enumerate(scope.textures)) {\n"
      "                    if (!texture->HasPinnedUsage()) {\n"
      "                        continue;\n"
      "                    }\n"
      "\n"
      "                    DAWN_TRY(scope.textureSyncInfos[j].Iterate(\n"
      "                        [&](const SubresourceRange&, const TextureSyncInfo& info) -> MaybeError {\n"
      "                            DAWN_INVALID_IF(info.usage != texture->GetPinnedUsage(),\n"
      "                                            \"%s is used as %s while pinned to %s.\", texture,\n"
      "                                            info.usage, texture->GetPinnedUsage());\n"
      "                            return {};\n"
      "                        }));\n"
      "                }",
      "for (size_t j = 0; j < scope.textures.size(); ++j) {\n"
      "                    TextureBase* texture = scope.textures[j];\n"
      "                    if (!texture->HasPinnedUsage()) {\n"
      "                        continue;\n"
      "                    }\n"
      "\n"
      "                    DAWN_TRY(scope.textureSyncInfos[j].Iterate(\n"
      "                        [&](const SubresourceRange&, const TextureSyncInfo& info) -> MaybeError {\n"
      "                            DAWN_INVALID_IF(info.usage != texture->GetPinnedUsage(),\n"
      "                                            \"%s is used as %s while pinned to %s.\", texture,\n"
      "                                            info.usage, texture->GetPinnedUsage());\n"
      "                            return {};\n"
      "                        }));\n"
      "                }")
  dawn_queue_contents = dawn_queue_contents.replace(
      "for (auto [j, texture] : Enumerate(scope.textures)) {\n"
      "                        if (!texture->HasPinnedUsage()) {\n"
      "                            continue;\n"
      "                        }\n"
      "\n"
      "                        DAWN_TRY(scope.textureSyncInfos[j].Iterate(\n"
      "                            [&](const SubresourceRange&,\n"
      "                                const TextureSyncInfo& info) -> MaybeError {\n"
      "                                DAWN_INVALID_IF(info.usage != texture->GetPinnedUsage(),\n"
      "                                                \"%s is used as %s while pinned to %s.\", texture,\n"
      "                                                info.usage, texture->GetPinnedUsage());\n"
      "                                return {};\n"
      "                            }));\n"
      "                    }",
      "for (size_t j = 0; j < scope.textures.size(); ++j) {\n"
      "                        TextureBase* texture = scope.textures[j];\n"
      "                        if (!texture->HasPinnedUsage()) {\n"
      "                            continue;\n"
      "                        }\n"
      "\n"
      "                        DAWN_TRY(scope.textureSyncInfos[j].Iterate(\n"
      "                            [&](const SubresourceRange&,\n"
      "                                const TextureSyncInfo& info) -> MaybeError {\n"
      "                                DAWN_INVALID_IF(info.usage != texture->GetPinnedUsage(),\n"
      "                                                \"%s is used as %s while pinned to %s.\", texture,\n"
      "                                                info.usage, texture->GetPinnedUsage());\n"
      "                                return {};\n"
      "                            }));\n"
      "                    }")
  with open(dawn_queue, "w", encoding="utf-8") as f:
    f.write(dawn_queue_contents)

  absl_options = os.path.join(dawn_dir, "..", "abseil-cpp", "absl", "base",
                              "options.h")
  with open(absl_options, "r", encoding="utf-8") as f:
    absl_options_contents = f.read()
  absl_options_contents = absl_options_contents.replace(
      "#define ABSL_OPTION_USE_STD_SOURCE_LOCATION 2",
      "#define ABSL_OPTION_USE_STD_SOURCE_LOCATION 0")
  with open(absl_options, "w", encoding="utf-8") as f:
    f.write(absl_options_contents)

  absl_config = os.path.join(dawn_dir, "..", "abseil-cpp", "absl", "base",
                             "config.h")
  with open(absl_config, "r", encoding="utf-8") as f:
    absl_config_contents = f.read()
  absl_config_contents = absl_config_contents.replace(
      "#define ABSL_HAVE_STD_SOURCE_LOCATION 1",
      "#undef ABSL_HAVE_STD_SOURCE_LOCATION")
  with open(absl_config, "w", encoding="utf-8") as f:
    f.write(absl_config_contents)

  build_cmd = [ninja_exe, "-C", build_dir, "-dkeepdepfile"] + build_targets
  subprocess.run(build_cmd, check=True, env=env)

  # The install target is broken, so we manually copy the headers.
  # The headers are located in the build directory in a gen/include folder.
  # The Skia build expects to find headers in subdirectories of the include path.
  generated_headers_src = os.path.join(build_dir, "gen", "include")
  generated_headers_dest = os.path.join(gen_dir, "include")

  if os.path.exists(generated_headers_dest):
    shutil.rmtree(generated_headers_dest)

  # Copy the contents of the 'dawn' and 'webgpu' directories into the destination.
  shutil.copytree(
      os.path.join(generated_headers_src, "dawn"),
      os.path.join(generated_headers_dest, "dawn"),
      dirs_exist_ok=True)
  shutil.copytree(
      os.path.join(generated_headers_src, "webgpu"),
      os.path.join(generated_headers_dest, "webgpu"),
      dirs_exist_ok=True)

  dependencies, object_files = discover_dependencies(build_dir, build_targets)
  write_depfile(output_path, depfile_path, dependencies)

  combine_into_library(args, output_path, build_dir, target_os, object_files)

if __name__ == "__main__":
  main()
