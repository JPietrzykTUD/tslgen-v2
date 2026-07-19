fn main() {
    let host = std::env::var("HOST").expect("Cargo did not provide the build host triple");
    let target = std::env::var("TARGET").expect("Cargo did not provide the target triple");

    println!("cargo:rerun-if-env-changed=HOST");
    println!("cargo:rerun-if-env-changed=TARGET");
    println!("cargo:rustc-env=TSL_BUILD_HOST={host}");
    println!("cargo:rustc-env=TSL_BUILD_TARGET={target}");
}
