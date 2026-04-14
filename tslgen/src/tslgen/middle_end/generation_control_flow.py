import codon
import re
from typing import ClassVar, Pattern

from tslgen.core.passes import MiddleEndPass
from tslgen.ir.primitive_ir import Primitive
from tslgen.utils.string_utils import extract_braced, skip_whitespace

from tslgen.utils.type_utils import TriBool

class StringBoolEvaluator:
    ALLOWED: ClassVar[Pattern[str]] = re.compile(
        r'^(?:True|False|&&|\|\||\(|\)|\s+)+$',
        re.DOTALL
    )

    @codon.jit
    def check_allowed(self, expr: str) -> bool:
        return self.ALLOWED.fullmatch(expr) is not None

    def __call__(self, expr: str) -> TriBool:
        if not self.check_allowed(expr):
            return TriBool.UNKNOWN
        
        result = eval(
            expr.replace("&&", " and ").replace("||", " or "),
            {"__builtins__": {}},
            {},
        )
        return TriBool.TRUE if result else TriBool.FALSE


class GenerationControlFlowRewrite(MiddleEndPass):
    REGEX_IF: ClassVar[Pattern[str]] = re.compile(
        r'if<compile>\((?P<condition>.*?)\)\s*\{',
        re.DOTALL,
    )
    REGEX_ELSE_IF: ClassVar[Pattern[str]] = re.compile(
        r'else\s+if<compile>\((?P<condition>.*?)\)\s*\{',
        re.DOTALL,
    )
    REGEX_ELSE: ClassVar[Pattern[str]] = re.compile(
        r'else\s*\{',
        re.DOTALL,
    )
    STRING_BOOL_EVALUATOR: StringBoolEvaluator = StringBoolEvaluator()

    def lower(self, source: Primitive) -> Primitive:
        if source.stages_resolved.get(self.__class__.__name__, False):
            return source
        text = source.implementation

        fully_resolved = True

        while match_if := self.REGEX_IF.search(text):
            chain_start = match_if.start()

            decidable: bool = False

            selected_text: str | None = None

            if_condition = match_if.group("condition")
            if_open_brace_index = match_if.end() - 1
            if_text, if_close_brace_index = extract_braced(text, if_open_brace_index)

            check_if_result = self.STRING_BOOL_EVALUATOR(if_condition)
            if check_if_result == TriBool.TRUE:
                selected_text = if_text
                decidable = True
            elif check_if_result == TriBool.FALSE:
                decidable = True
            elif check_if_result == TriBool.UNKNOWN:
                pass
            pos = skip_whitespace(text, if_close_brace_index + 1)
            chain_end = if_close_brace_index

            while match_else_if := self.REGEX_ELSE_IF.match(text, pos):
                else_if_condition = match_else_if.group("condition")
                else_if_open_brace_index = match_else_if.end() - 1
                else_if_text, else_if_close_brace_index = extract_braced(text, else_if_open_brace_index)


                if selected_text is None:
                    else_if_result = self.STRING_BOOL_EVALUATOR(else_if_condition)
                    if else_if_result == TriBool.TRUE:
                        selected_text = else_if_text
                        decidable = True
                    elif else_if_result == TriBool.FALSE:
                        decidable = True
                    elif else_if_result == TriBool.UNKNOWN:
                        pass
                
                chain_end = else_if_close_brace_index
                pos = skip_whitespace(text, chain_end + 1)
            
            match_else = self.REGEX_ELSE.match(text, pos)
            if match_else is not None:
                else_open_brace_index = match_else.end() - 1
                else_text, else_close_brace_index = extract_braced(text, else_open_brace_index)

                if selected_text is None and decidable:
                    selected_text = else_text
                
                chain_end = else_close_brace_index
            
            replacement_text = "" if selected_text is None else selected_text
            text = text[:chain_start] + replacement_text + text[chain_end + 1:]

            if not decidable:
                fully_resolved = False
        
        source.implementation = text
        
        source.stages_resolved[self.__class__.__name__] = fully_resolved
        return source