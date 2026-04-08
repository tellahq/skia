// Minimal Emscripten API stubs for compiling emdawnwebgpu's webgpu.cpp
// on non-Emscripten WASM targets (wasm32-unknown-unknown, wasm32-wasi).
//
// Only provides the macros and declarations that webgpu.cpp actually uses.

#pragma once

// EMSCRIPTEN_KEEPALIVE: prevent dead-code elimination AND export from WASM.
// visibility("default") ensures wasm-ld includes the symbol in the export
// table, so the JS side can call emwgpuCreate*/emwgpuOn* functions.
#define EMSCRIPTEN_KEEPALIVE __attribute__((used, visibility("default")))
#define EM_IMPORT(name) __attribute__((import_module("env")))

// Return 1 to satisfy emdawnwebgpu's TimedWaitAny guard.
// We don't actually have Asyncify, but the WaitAny implementation
// falls through to emwgpuWaitAny (JS) which we implement as immediate
// resolution. The assert(emscripten_has_asyncify()) is stripped in NDEBUG.
static inline int emscripten_has_asyncify(void) { return 1; }
