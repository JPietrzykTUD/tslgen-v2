FROM ubuntu:26.04

ARG ZIG_VERSION=0.16.0
ARG ZIG_ARCH=x86_64-linux

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    sudo \
    build-essential gdb cmake clang clang-format ninja-build doxygen \
    git curl xz-utils unzip pkg-config ca-certificates nodejs npm jq \
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

RUN /opt/venv/bin/pip install --no-cache-dir \
    prompt_toolkit \
    lark jinja2 mkdocs-material sphinx breathe \
    numpy xxhash cyclopts networkx psutil \
    pytest mypy ruff black build \
    "mkdocstrings[python]" \
    mkdocs-git-revision-date-localized-plugin


COPY .devcontainer/download_sde.py /tmp/download_sde.py

RUN ACCEPT_INTEL_SDE_LICENSE=yes \
    python3 /tmp/download_sde.py --out-dir /tmp/sde && \
    mkdir -p /opt/intel-sde && \
    tar -xf /tmp/sde/sde-external-10.8.0-2026-03-15-lin.tar.xz \
        --strip-components=1 \
        -C /opt/intel-sde && \
    rm -rf /tmp/sde

ENV PATH="/opt/intel-sde:${PATH}"
# codon-jit
# RUN yes | /bin/bash -c "$(curl -fsSL https://exaloop.io/install.sh)"

WORKDIR /workspace
