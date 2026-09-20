Python API
==========

The supported embedding boundary is deliberately small. Import compiler
operations from ``tslc.api``; modules below the facade remain implementation
details unless another documented contract says otherwise.

Basic generation
----------------

.. code-block:: python

   from pathlib import Path

   from tslc.api import generate_project, write_artifacts

   result = generate_project(
       (Path("tsldata"),),
       machine_profiles_path=Path(
           "supplementary/buildsystem/machine_profiles.json"
       ),
       primitives=("add",),
       profiles=("scalar", "avx2"),
       backends=("cpp", "rust"),
       generation_mode="strict",
   )
   for diagnostic in result.diagnostics:
       print(diagnostic.severity, diagnostic.code, diagnostic.message)
   if not any(item.severity == "error" for item in result.diagnostics):
       write_artifacts(result.artifacts, Path("tslctmp/generated"))

Generation returns immutable artifacts and structured diagnostics. Filesystem
writes occur only when ``write_artifacts`` is called. Build verification is a
separate explicit operation and consumes the verification plan from the same
rendered generation result.

Facade reference
----------------

.. automodule:: tslc.api
   :members:
   :member-order: bysource
