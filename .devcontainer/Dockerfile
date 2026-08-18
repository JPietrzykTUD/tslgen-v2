FROM ubuntu:26.04

ARG ZIG_VERSION=0.16.0
ARG ZIG_ARCH=x86_64-linux
ARG WASI_SDK_VERSION=33
ARG WASMTIME_VERSION=45.0.2
ARG LLVM_APT_VERSION=22

ENV DEBIAN_FRONTEND=noninteractive
ENV ONEAPI_ROOT=/opt/intel/oneapi

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    sudo \
    build-essential gdb cmake clang clang-format ninja-build doxygen \
    g++-aarch64-linux-gnu \
    g++-riscv64-linux-gnu binutils-riscv64-linux-gnu \
    git curl gnupg xz-utils unzip pkg-config ca-certificates nodejs npm jq \
    python3 python3-pip python3-venv \
    qemu-user qemu-user-binfmt \
    xvfb libgtk-3-0t64 libnss3 libasound2t64 libxss1 libsecret-1-0 fonts-liberation && \
    python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip setuptools wheel && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Ubuntu 26.04 ships Clang 21. Keep that fallback compiler and add a native
# Clang 22 from LLVM's signed repository for compiler-capability probes whose
# positive path first appears in Clang 22. WASI SDK's Clang targets wasm32 and
# cannot exercise the native generated-value binaries used by this gate.
RUN set -eux; \
    curl -fsSL https://apt.llvm.org/llvm-snapshot.gpg.key \
      -o /tmp/llvm-snapshot.gpg.key; \
    gpg --batch --yes --dearmor \
      --output /usr/share/keyrings/apt.llvm.org.gpg \
      /tmp/llvm-snapshot.gpg.key; \
    echo "deb [signed-by=/usr/share/keyrings/apt.llvm.org.gpg] https://apt.llvm.org/resolute/ llvm-toolchain-resolute-${LLVM_APT_VERSION} main" \
      > /etc/apt/sources.list.d/apt.llvm.org.list; \
    apt-get update -y; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      "clang-${LLVM_APT_VERSION}"; \
    /usr/bin/clang++-21 --version; \
    "/usr/bin/clang++-${LLVM_APT_VERSION}" --version; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/* /tmp/llvm-snapshot.gpg.key

# Install Zig
RUN set -eux; \
    curl -L "https://ziglang.org/download/${ZIG_VERSION}/zig-${ZIG_ARCH}-${ZIG_VERSION}.tar.xz" \
      -o /tmp/zig.tar.xz; \
    mkdir -p /opt/zig; \
    tar -xf /tmp/zig.tar.xz -C /opt/zig --strip-components=1; \
    rm /tmp/zig.tar.xz; \
    /opt/zig/zig version

# Install WASI SDK: clang/clang++ for C/C++ -> wasm32-wasip1.
RUN set -eux; \
    curl -L "https://github.com/WebAssembly/wasi-sdk/releases/download/wasi-sdk-${WASI_SDK_VERSION}/wasi-sdk-${WASI_SDK_VERSION}.0-x86_64-linux.tar.gz" \
      -o /tmp/wasi-sdk.tar.gz; \
    mkdir -p /opt; \
    tar -xzf /tmp/wasi-sdk.tar.gz -C /opt; \
    mv "/opt/wasi-sdk-${WASI_SDK_VERSION}.0-x86_64-linux" /opt/wasi-sdk; \
    rm /tmp/wasi-sdk.tar.gz; \
    /opt/wasi-sdk/bin/clang++ --version

ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo
ENV WASI_SDK_PATH=/opt/wasi-sdk
# Keep WASI's target-specific clang out of ambient compiler discovery. tslc
# addresses it explicitly through the wasi-cpp tool role.
ENV PATH="/opt/venv/bin:/opt/zig:${CARGO_HOME}/bin:${PATH}"

ENV CC="zig cc"
ENV CXX="zig c++"

# Install Rust and Cargo
RUN set -eux; \
    mkdir -p "${RUSTUP_HOME}" "${CARGO_HOME}"; \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
      | sh -s -- -y --no-modify-path --profile minimal --default-toolchain stable; \
    rustup component add rustfmt clippy; \
    rustup target add \
      x86_64-unknown-linux-gnu \
      aarch64-unknown-linux-gnu \
      x86_64-unknown-linux-musl \
      aarch64-unknown-linux-musl \
      wasm32-wasip1; \
    cargo install --locked cargo-zigbuild

# Install Wasmtime runtime for executing generated .wasm value-test binaries.
RUN set -eux; \
    curl -L "https://github.com/bytecodealliance/wasmtime/releases/download/v${WASMTIME_VERSION}/wasmtime-v${WASMTIME_VERSION}-x86_64-linux.tar.xz" \
      -o /tmp/wasmtime.tar.xz; \
    tar -xJf /tmp/wasmtime.tar.xz -C /tmp; \
    install -m 0755 "/tmp/wasmtime-v${WASMTIME_VERSION}-x86_64-linux/wasmtime" /usr/local/bin/wasmtime; \
    rm -rf "/tmp/wasmtime-v${WASMTIME_VERSION}-x86_64-linux" /tmp/wasmtime.tar.xz; \
    wasmtime --version

COPY requirements.txt /tmp/requirements.txt

RUN /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt

COPY .devcontainer/download_sde.py /tmp/download_sde.py

RUN ACCEPT_INTEL_SDE_LICENSE=yes \
    python3 /tmp/download_sde.py --out-dir /tmp/sde && \
    mkdir -p /opt/intel-sde && \
    tar -xf /tmp/sde/sde-external-10.8.0-2026-03-15-lin.tar.xz \
        --strip-components=1 \
        -C /opt/intel-sde && \
    rm -rf /tmp/sde

ENV PATH="/opt/intel-sde:${PATH}"

# prepare oneapi repository
RUN curl -fsSL https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB \
        | gpg --dearmor \
        > /usr/share/keyrings/oneapi-archive-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main" \
        > /etc/apt/sources.list.d/oneAPI.list

# Install Intel oneAPI compilers and FPGA addon
RUN apt-get update && apt-get install -y --no-install-recommends \
        intel-oneapi-compiler-dpcpp-cpp-2025.0 \
        intel-compiler-fpga-addon-2025.0 \
    && rm -rf /var/lib/apt/lists/*

# Set up environment variables for Intel oneAPI
RUN echo 'source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1' \
        > /etc/profile.d/oneapi.sh

# codon-jit
# RUN yes | /bin/bash -c "$(curl -fsSL https://exaloop.io/install.sh)"

WORKDIR /workspace
