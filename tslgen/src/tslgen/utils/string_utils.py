import codon
from typing import Tuple
import re

@codon.jit
def extract_braced(text: str, open_brace_index: int) -> Tuple[str, int]:
    if text[open_brace_index] != "{":
        raise ValueError("Expected '{' at open_brace_index")
    depth = 0
    for i in range(open_brace_index, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[open_brace_index + 1:i], i
    raise ValueError("Unmatched '{'")


REGEX_WHITESPACE = re.compile(r"\s*")

@codon.jit
def skip_whitespace(text: str, pos: int) -> int:
    return REGEX_WHITESPACE.match(text, pos).end()