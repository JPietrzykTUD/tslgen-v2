FROM ubuntu:26.04

ARG ZIG_VERSION=0.16.0
ARG ZIG_ARCH=x86_64-linux

ENV DEBIAN_FRONTEND=noninteractive
ENV ONEAPI_ROOT=/opt/intel/oneapi

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    sudo \
    build-essential gdb cmake clang clang-format ninja-build doxygen \
    g++-aarch64-linux-gnu \
    git curl gnupg xz-utils unzip pkg-config ca-certificates nodejs npm jq \
    python3 python3-pip python3-venv \
    qemu-user qemu-user-binfmt && \
    python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip setuptools wheel && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Zig
RUN set -eux; \
    curl -L "https://ziglang.org/download/${ZIG_VERSION}/zig-${ZIG_ARCH}-${ZIG_VERSION}.tar.xz" \
      -o /tmp/zig.tar.xz; \
    mkdir -p /opt/zig; \
    tar -xf /tmp/zig.tar.xz -C /opt/zig --strip-components=1; \
    rm /tmp/zig.tar.xz; \
    /opt/zig/zig version

ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo
ENV PATH="/opt/venv/bin:/opt/zig:${CARGO_HOME}/bin:${PATH}"

ENV CC="zig cc"
ENV CXX="zig c++"

RUN set -eux; \
    mkdir -p "${RUSTUP_HOME}" "${CARGO_HOME}"; \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
      | sh -s -- -y --no-modify-path --profile minimal --default-toolchain stable; \
    rustup component add rustfmt clippy; \
    rustup target add \
      x86_64-unknown-linux-gnu \
      aarch64-unknown-linux-gnu \
      x86_64-unknown-linux-musl \
      aarch64-unknown-linux-musl; \
    cargo install --locked cargo-zigbuild

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

RUN apt-get update && apt-get install -y --no-install-recommends \
        intel-oneapi-compiler-dpcpp-cpp-2025.0 \
        intel-compiler-fpga-addon-2025.0 \
    && rm -rf /var/lib/apt/lists/*

RUN echo 'source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1' \
        > /etc/profile.d/oneapi.sh

# codon-jit
# RUN yes | /bin/bash -c "$(curl -fsSL https://exaloop.io/install.sh)"

WORKDIR /workspace
