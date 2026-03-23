#ifndef WASM_SJLJ_STUBS_H
#define WASM_SJLJ_STUBS_H

// Stub setjmp/longjmp for wasm32-unknown-unknown.
//
// Skia's PNG and JPEG codecs use setjmp/longjmp for error recovery from
// malformed images. On WASM this normally requires exception handling
// instructions (-mllvm -wasm-enable-sjlj), which produce EH opcodes
// incompatible with wasm-bindgen. Instead we stub: setjmp always returns 0
// (normal path) and longjmp traps. A malformed image crashes instead of
// gracefully failing — acceptable since we only decode validated uploads.
//
// This header is force-included (-include) before all source files, so the
// _SETJMP_H guard prevents the real setjmp.h from loading (which would
// #error without __wasm_exception_handling__).

#define _SETJMP_H

#ifdef __cplusplus
extern "C" {
#endif

typedef unsigned long __jmp_buf[8];

typedef struct __jmp_buf_tag {
    __jmp_buf __jb;
    unsigned long __fl;
    unsigned long __ss[128 / sizeof(long)];
} jmp_buf[1];

static inline int setjmp(jmp_buf __env) {
    (void)__env;
    return 0;
}

static inline _Noreturn void longjmp(jmp_buf __env, int __val) {
    (void)__env;
    (void)__val;
    __builtin_trap();
}

#define setjmp setjmp

#ifdef __cplusplus
}
#endif

#endif
