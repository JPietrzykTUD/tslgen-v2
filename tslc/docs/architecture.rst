Architecture
============

``tslc`` is a source-driven compiler with one traceable pipeline:

.. code-block:: text

   sources and assets
     -> parse
     -> typed catalog
     -> select implementations
     -> scan TSIL regions
     -> lower specializations
     -> close dependencies and finalize names
     -> validate and plan backend output
     -> render
     -> write and optionally verify

Stage ownership
---------------

``sources`` and ``compiler_assets``
   Load authored files and packaged static assets. Later stages do not perform
   incidental filesystem reads.

``syntax`` and ``catalog``
   Parse the outer TSL language, then promote it into validated, immutable
   domain objects such as primitives, extensions, semantic contracts, and
   implementation safety.

``select`` and ``ir``
   Choose one implementation candidate for each concrete slot and scan its body
   into raw target text plus recognized recursive TSIL regions. TSIL is not a
   C++, Rust, or general target-language AST.

``lower``
   Resolve typed region semantics into ``LoweredSpecialization`` values and
   record dependencies, requirements, diagnostics, and safety effects.

``backend``, ``value_tests``, and ``benchmark``
   Translate already-lowered facts and construct complete output, test, and
   benchmark plans. Backend code does not reopen TSL source data.

``render`` and ``output``
   Format validated plans, write deterministic artifacts, and explicitly invoke
   configured compilers or runners.

Design boundaries
-----------------

* Typed immutable objects replace dictionaries after parsing and configuration
  boundaries.
* Backends format decided semantics; templates do not select or repair them.
* Raw target-language fragments remain opaque to compiler-owned projections.
* Unsupported combinations produce structured diagnostics or explicit skips.
* New primitives, extensions, backends, and TSIL regions should be additive
  vertical slices.

The complete, current architecture narrative lives in
`tslc/DESCRIPTION.md <https://github.com/JPietrzykTUD/tslgen-v2/blob/main/tslc/DESCRIPTION.md>`_.
The stable design constraints live in the
`repository charter <https://github.com/JPietrzykTUD/tslgen-v2/blob/main/CHARTER.md>`_
and
`compiler charter <https://github.com/JPietrzykTUD/tslgen-v2/blob/main/tslc/CHARTER.md>`_.
