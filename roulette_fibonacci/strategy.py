"""Fibonacci staking for even-money roulette bets (rojo/negro, par/impar, 1-18/19-36).

Progression on a loss: advance one step through the Fibonacci sequence.
Progression on a win: retreat two steps (a win only needs to cover the last
two losses, since fib(n) = fib(n-1) + fib(n-2)).
The sequence is capped at `max_steps` terms so a losing streak never grows
the bet past the last term (e.g. with max_steps=6 the bet stops rising at
the 6th consecutive loss and stays flat at that size).
"""

from dataclasses import dataclass, field


def build_sequence(max_steps: int) -> list[int]:
    if max_steps < 1:
        raise ValueError("max_steps must be >= 1")
    seq = [1, 1]
    while len(seq) < max_steps:
        seq.append(seq[-1] + seq[-2])
    return seq[:max_steps]


@dataclass
class FibonacciStrategy:
    unit: float = 1.0
    max_steps: int = 6
    sequence: list[int] = field(default=None)
    index: int = field(default=0, init=False)

    def __post_init__(self):
        if self.sequence is None:
            self.sequence = build_sequence(self.max_steps)
        self.max_index = len(self.sequence) - 1

    def current_bet(self) -> float:
        return self.sequence[self.index] * self.unit

    def register_result(self, won: bool) -> None:
        if won:
            self.index = max(0, self.index - 2)
        else:
            self.index = min(self.max_index, self.index + 1)

    def reset(self) -> None:
        self.index = 0

    @property
    def at_start(self) -> bool:
        return self.index == 0

    @property
    def capped(self) -> bool:
        return self.index == self.max_index
