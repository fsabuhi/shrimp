from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Scheme:
    prefix_map: dict[str, str] = field(default_factory=dict)
    separator: str = "_"
    counter_format: str = "{:03d}"
    case: str = "upper"  # "upper" | "lower"
    aliaser: Callable[[str, int], str] | None = None

    def __post_init__(self) -> None:
        if self.case not in ("upper", "lower"):
            raise ValueError(f"case must be 'upper' or 'lower', got {self.case!r}")
        prefixes = list(self.prefix_map.values())
        if len(prefixes) != len(set(prefixes)):
            raise ValueError("Scheme prefix_map has duplicate prefix values")

    def make_short_id(self, category: str, n: int) -> str:
        if self.aliaser is not None:
            return self.aliaser(category, n)
        prefix = self.prefix_map.get(category, category[:3])
        if self.case == "upper":
            prefix = prefix.upper()
        else:
            prefix = prefix.lower()
        counter = self.counter_format.format(n)
        return f"{prefix}{self.separator}{counter}"
