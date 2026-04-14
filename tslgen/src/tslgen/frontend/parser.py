from dataclasses import dataclass

@dataclass(frozen=True)
class Span:
    start_pos: int
    end_pos: int
    line: int
    column: int
    end_line: int
    end_column: int