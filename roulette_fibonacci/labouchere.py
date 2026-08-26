"""Labouchere (cancellation) staking: the classic way to express "I want to
win exactly +N units this session, recovering losses along the way".

This is the system the user described: aim for +1 unit of profit per session,
accumulate those units, and accept that occasionally a session goes badly and
needs several later wins to be recovered.

Mechanics:
  - Start with a line of numbers summing to the session target (e.g. [1]).
  - Stake = first + last element of the line (or the single element if len==1).
  - Win  -> cross off both ends. Line empty => session target reached.
  - Lose -> append the stake to the end of the line.

The line grows only on losses, and each win removes two entries, so the system
"self-liquidates" after a mixed run. It is capped in practice by the table
limit and by the bankroll, which is where it breaks.
"""

from dataclasses import dataclass, field


@dataclass
class Labouchere:
    target: int = 1
    unit: float = 1.0
    line: list[float] = field(default=None)

    def __post_init__(self):
        if self.line is None:
            # A line of `target` ones sums to the target.
            self.line = [1.0] * self.target

    def current_bet(self) -> float:
        if not self.line:
            return 0.0
        if len(self.line) == 1:
            return self.line[0] * self.unit
        return (self.line[0] + self.line[-1]) * self.unit

    def register_result(self, won: bool) -> None:
        if not self.line:
            return
        if won:
            if len(self.line) == 1:
                self.line.pop()
            else:
                self.line.pop(0)
                self.line.pop()
        else:
            self.line.append(self.current_bet() / self.unit)

    @property
    def complete(self) -> bool:
        return not self.line

    @property
    def outstanding(self) -> float:
        """How much profit the remaining line still promises to deliver."""
        return sum(self.line) * self.unit
