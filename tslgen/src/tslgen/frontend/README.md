# TSL-Generator Frontend

This directory contains the source code for the TSL-Generator frontend, which is responsible for parsing TSL files, performing semantic analysis and generating intermediate representations for further processing by the middleend and backend components.

## Steps

### 1. Parsing

TSL files follow a custom [LARK](https://github.com/lark-parser/lark) ([RTD](https://lark-parser.readthedocs.io/en/stable/)) grammar defined in the `grammar` directory. 
The parser (`parser.py`) uses LARK to convert TSL source code into a python data class representation. 
Internally, lark parses the TSL source code into a parse tree. Than this parse tree is transformed into a more convenient data class representation.
We do this deliberately because the TSL grammar is basically an extension of the yaml grammar, and the parse tree is very similar to the data class representation.

### 2. Semantic Analysis

After parsing, the frontend (`semantic_analyzer.py`) performs semantic analysis to ensure that the TSL code is semantically correct.
This includes checking for undefined variables, type mismatches, and other semantic errors.

### 3. Primitive Emitter

After validating the TSL code, the frontend performs primitive emission.
For every TSL primitive every specific implementation (extension $\times$ type) is emitted as a separate primitive.
This is done to simplify the dependency analysis and code generation process, as it allows us to treat each primitive implementation as a separate entity with its own dependencies and code generation requirements.
The emitted primitives are stored in a list of [Primitive](../ir/primitive_ir.py).