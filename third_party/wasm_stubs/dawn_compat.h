// Stubs for Dawn-specific types not in the standard webgpu-native webgpu.h.
// When building emdawnwebgpu against the webgpu-native header (rather than
// Dawn's generated header), some Dawn extension types are missing.

#pragma once

// Dawn extension struct for UTF-16 compilation messages.
// webgpu.cpp only uses this in a reinterpret_cast for free().
typedef struct WGPUDawnCompilationMessageUtf16 WGPUDawnCompilationMessageUtf16;
