// Minimal libc stubs for wasm32-unknown-unknown linking.
// The C/C++ code is compiled as wasm32-wasi-threads which references
// errno as a TLS symbol. We provide it here so the linker can resolve
// the TLS relocation without pulling in the full WASI libc.

_Thread_local int errno;
