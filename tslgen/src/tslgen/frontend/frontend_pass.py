from typing import Protocol

class FrontendPass(Protocol):
    def lower(self, source)