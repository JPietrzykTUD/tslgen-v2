Authoring and extending TSL
===========================

TSL source changes should follow the smallest applicable vertical slice. The
source corpus declares target-independent facts and implementations; the
compiler promotes those declarations into typed semantics and diagnostics.

Add a primitive
---------------

Define the primitive's signature, documentation, tests, semantic contracts,
and implementation matrix under ``tsldata/primitives``. Prefer direct hardware
instructions, then composition from qualified TSL primitives, then the generic
fallback. Add missing prerequisite primitives before duplicating their behavior
inside another implementation.

See `Adding a primitive <https://github.com/JPietrzykTUD/tslgen-v2/blob/main/docs/add-primitive.md>`_.

Add an extension
----------------

Declare the extension, target-family capabilities, register and mask policies,
profile participation, and the first verified primitive slice. Backend-specific
syntax remains in the backend rather than leaking into shared source facts.

See `Adding an extension <https://github.com/JPietrzykTUD/tslgen-v2/blob/main/docs/add-extension.md>`_.

Add a TSIL region
-----------------

A new keyword requires one shared lexical/authoring descriptor, shell
validation where necessary, one lowering handler registration, and focused
scanner/lowering tests. Add a new structural scanner shape only when the region
cannot use an existing call or block form.

See the `TSIL keyword reference <https://github.com/JPietrzykTUD/tslgen-v2/blob/main/docs/tsil-keywords.md>`_
and `Adding a TSIL keyword region <https://github.com/JPietrzykTUD/tslgen-v2/blob/main/docs/add-keyword.md>`_.

Validate a change
-----------------

Start with the owning focused tests, then run the compiler checks appropriate
to the slice:

.. code-block:: console

   python -m compileall -q tslc/src/tslc
   PYTHONPATH=tslc/src python -m pytest -q tslc/tests
   (cd tslc && python -m mypy)
   git diff --check

Generated layout, backend code, or executable value-test changes also require
the opt-in generated build/value gates.
