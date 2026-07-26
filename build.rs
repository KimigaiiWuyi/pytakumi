fn main() {
  let engine = std::path::Path::new("vendor/takumi/takumi/Cargo.toml");
  if !engine.exists() {
    panic!(
      "Takumi engine submodule not found at vendor/takumi.\n\
       \n\
       Initialize submodules:\n\
         git submodule update --init --recursive\n\
       \n\
       Layout:\n\
         pytakumi/\n\
           vendor/takumi/   # git submodule → github.com/kane50613/takumi\n\
           src/             # PyO3 bindings\n\
       \n\
       Prefer a prebuilt wheel when available:  pip install pytakumi"
    );
  }
  println!("cargo:rerun-if-changed=vendor/takumi/takumi/Cargo.toml");
  println!("cargo:rerun-if-changed=vendor/takumi/takumi-core/Cargo.toml");
  println!("cargo:rerun-if-changed=vendor/takumi/takumi-bindings-common/Cargo.toml");
}
