//! Link the clang runtime on macOS.
//!
//! A build for an older macOS than the SDK (pip sets `MACOSX_DEPLOYMENT_TARGET=11.0`)
//! compiles the `@available` checks of FFmpeg and Skia to calls to
//! `__isPlatformVersionAtLeast`. That function is in `libclang_rt.osx.a`, which rustc
//! does not link (`-nodefaultlibs`). A Python module links with dynamic lookup, so
//! without this the import fails with "symbol not found".

use std::process::Command;

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() != Ok("macos") {
        return;
    }
    let out = Command::new("clang")
        .arg("--print-runtime-dir")
        .output()
        .expect("run `clang --print-runtime-dir`");
    let dir = String::from_utf8(out.stdout).expect("clang prints a UTF-8 path");
    println!("cargo:rustc-link-search=native={}", dir.trim());
    println!("cargo:rustc-link-lib=static=clang_rt.osx");
}
