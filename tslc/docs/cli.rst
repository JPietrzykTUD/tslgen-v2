Command-line workflow
=====================

The installed ``tslc`` command and ``PYTHONPATH=tslc/src python -m tslc`` expose
the same interface. Run ``tslc COMMAND --help`` for every accepted option; this
page describes which command owns each part of the workflow.

Validate and discover
---------------------

``tslc check`` validates parsing, catalog promotion, invariants, and TSIL region
shells without rendering a project. Concrete primitive/profile/backend/type
filters opt into selection and lowering for the requested slots.

``tslc list`` and ``tslc show`` inspect the same typed catalog and registries
used by generation:

.. code-block:: console

   tslc check
   tslc check --watch
   tslc list primitives
   tslc list extensions
   tslc list regions
   tslc show primitive add
   tslc show extension avx2

Use JSON diagnostics when another tool consumes the result. Human-readable
diagnostics remain source-located and include stable diagnostic codes.

Inspect a target
----------------

``doctor`` reports compiler, profile, feature, and runner readiness. ``explain``
shows selection and lowering decisions. ``preview`` renders one primitive
through its registered backend without writing a full project. ``analyze``
adds the concrete dependency tree.

.. code-block:: console

   tslc doctor --profile avx2 --backend cpp
   tslc explain --primitive add --profile avx2 --type si32 --backend cpp
   tslc preview --primitive add --profile avx2 --type si32 --backend cpp
   tslc analyze --primitive add --profile avx2 --extension avx2 \
     --type si32 --backend cpp

Generate, build, and test
-------------------------

``generate`` writes artifacts. ``build`` generates and runs compile-time
verification. ``test`` additionally runs generated value tests. All three use
the same selection, lowering, dependency, backend-validation, and render path.

.. code-block:: console

   tslc generate --primitives add,sub --profiles scalar --backends cpp,rust
   tslc build --primitives add,sub --profiles scalar,avx2 --backends cpp,rust
   tslc test --primitives add,sub --profiles avx2 --backends cpp

Use ``--generation-mode strict`` when any requested coverage gap must fail the
command. Partial mode retains unsupported cases as structured skips.

Maintenance and editor commands
-------------------------------

Coverage, metadata, release, and benchmark commands are explicit maintenance
projections of compiler-owned typed facts. They do not form additional
selection or lowering pipelines. ``tslc lsp`` runs the editor-neutral language
server used by the VS Code client.

For the exhaustive option and exit-code reference, see the repository's
`command-line tools guide <https://github.com/JPietrzykTUD/tslgen-v2/blob/main/docs/tslc-cli.md>`_.
