:orphan:

TSLc compiler
=============

``tslc`` compiles the TSL data language into deterministic C++ and Rust SIMD
libraries. It validates the source corpus, selects implementations for explicit
machine profiles, lowers recognized TSIL regions, renders generated projects,
and can build and test the result with real toolchains.

The compiler and the generated library have different documentation surfaces.
This section documents the Python compiler, its command line, authoring
workflow, and supported embedding API. The C++ and Rust sections in the site
header document the generated library.

.. toctree::
   :maxdepth: 2
   :caption: Compiler guide

   getting_started
   cli
   python_api
   architecture
   authoring

Choose a path
-------------

* Start with :doc:`getting_started` to install the compiler and generate a
  small project.
* Use :doc:`cli` for the normal validation, inspection, generation, and
  verification workflow.
* Use :doc:`python_api` when another Python program needs to drive the compiler.
* Read :doc:`architecture` before changing compiler stages or ownership.
* Read :doc:`authoring` before adding primitives, extensions, or TSIL regions.

The compiler is intentionally a compact pipeline rather than a framework.
Source data owns portable primitive and extension facts; typed compiler stages
own validation and lowering; backends translate already-decided semantics; and
templates only format final render values.
