// Minimal Emscripten API stubs for compiling emdawnwebgpu's webgpu.cpp
// on non-Emscripten WASM targets (wasm32-unknown-unknown, wasm32-wasi).
//
// Only provides the macros and declarations that webgpu.cpp actually uses.

#pragma once

#define EMSCRIPTEN_KEEPALIVE __attribute__((used))
#define EM_IMPORT(name) __attribute__((import_module("env")))

static inline int emscripten_has_asyncify(void) { return 0; }
