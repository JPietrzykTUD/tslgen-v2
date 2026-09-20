Getting started
===============

Requirements
------------

``tslc`` requires Python 3.14 or newer. C++ and Rust toolchains are optional
until a generated project is built or tested. Documentation and editor support
have separate development dependencies.

Install an editable checkout from the repository root:

.. code-block:: console

   python -m pip install -e ./tslc
   tslc --version

The repository also supports an uninstalled invocation:

.. code-block:: console

   PYTHONPATH=tslc/src python -m tslc --version

Repository defaults
-------------------

Commands discover ``tslc.toml`` by walking upward from the current directory.
The repository configuration supplies the TSL source paths, machine-profile
file, default backends, and scratch output root. Explicit command-line options
override those defaults.

Run commands from the repository root unless a command says otherwise. Keep
generated projects, builds, and caches under ``./tslctmp``.

First checks
------------

Validate the complete authored corpus without rendering a project:

.. code-block:: console

   tslc check
   tslc list primitives
   tslc show extension avx2

Inspect one concrete specialization before generating anything:

.. code-block:: console

   tslc explain --primitive add --profile avx2 --type si32 --backend cpp
   tslc preview --primitive add --profile avx2 --type si32 --backend cpp

Generate and verify a small C++ and Rust slice:

.. code-block:: console

   tslc generate --primitives add --profiles scalar,avx2 --backends cpp,rust
   tslc build --primitives add --profiles scalar,avx2 --backends cpp,rust

Use ``tslc test`` when generated executable value tests should also run:

.. code-block:: console

   tslc test --primitives add --profiles avx2 --backends cpp

Next steps
----------

Continue with :doc:`cli` for command groups and diagnostics, or
:doc:`authoring` if the next task changes the TSL corpus.
