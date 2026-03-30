#ifndef WASM_ICU_STUBS_H
#define WASM_ICU_STUBS_H

// Stub timezone APIs for WASM/WASI targets (ICU's putil.cpp needs these).
// WASI doesn't provide tzset/timezone/tzname. Skia only uses ICU for text
// shaping and line breaking, not timezone conversion. UTC is correct for WASM.
static inline void __wasm_tzset(void) {}
static int __wasm_timezone_offset = 0;
static char *__wasm_tzname[2] = {(char *)"UTC", (char *)"UTC"};

#define U_TZSET __wasm_tzset
#define U_TIMEZONE __wasm_timezone_offset
#define U_TZNAME __wasm_tzname

#endif
