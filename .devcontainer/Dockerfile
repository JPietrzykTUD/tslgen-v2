FROM ubuntu:25.10

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    build-essential sudo gdb \
    cmake \
    git \
    wget \
    curl \
    unzip \
    python3.14 \
    python3-pip \
    python3.14-venv \
    g++ \
    ninja-build \
    libssl-dev \
    libboost-all-dev \
    libcurl4-gnutls-dev \
    libspdlog-dev \
    qemu-user \
    g++-aarch64-linux-gnu \
    gcc-aarch64-linux-gnu \
    libc6-dev-arm64-cross \
    clang \
    lld \
    pkg-config \
    python3.14-dev && \
    python3.14 -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip setuptools wheel && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo

# Put cargo/rustup shims on PATH (rustup/cargo live in $CARGO_HOME/bin)
ENV PATH="/opt/venv/bin:${CARGO_HOME}/bin:${PATH}"

RUN set -eux; \
    mkdir -p "${RUSTUP_HOME}" "${CARGO_HOME}"; \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
      | sh -s -- -y --no-modify-path --profile minimal --default-toolchain stable; \
    rustup --version; \
    rustup component add rustfmt clippy

RUN /opt/venv/bin/pip install --no-cache-dir prompt_toolkit lark jinja2 mkdocs-material codon-jit numpy && \
    /opt/venv/bin/pip install "mkdocstrings[python]" mkdocs-git-revision-date-localized-plugin
RUN yes | /bin/bash -c "$(curl -fsSL https://exaloop.io/install.sh)"

WORKDIR /workspace