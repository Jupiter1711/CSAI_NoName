from dataclasses import dataclass


@dataclass
class SearchResult:
    path: list[str] | None
    expanded: int
    cost: float = 0.0

    @property
    def found(self) -> bool:
        return self.path is not None

    @property
    def length(self) -> int:
        return len(self.path) if self.path is not None else 0
