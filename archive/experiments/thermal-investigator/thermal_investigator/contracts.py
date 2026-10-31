from __future__ import annotations

from dataclasses import asdict, dataclass
import math

DT = 2.0
DURATION = 120.0
RESET_SECONDS = 300.0
MAX_POWER_PERCENT = 65.0
MAX_TEMPERATURE_C = 60.0


@dataclass(frozen=True)
class Segment:
    seconds: float
    q1_percent: float
    q2_percent: float


@dataclass(frozen=True)
class Schedule:
    id: str
    segments: tuple[Segment, ...]

    def validate(self) -> None:
        if not isinstance(self.id, str) or not self.id or not self.segments:
            raise ValueError("A nonempty schedule ID and segments are required")
        total = 0.0
        for segment in self.segments:
            if not all(math.isfinite(v) for v in asdict(segment).values()):
                raise ValueError("Schedule values must be finite")
            if segment.seconds <= 0 or not math.isclose(segment.seconds / DT, round(segment.seconds / DT)):
                raise ValueError("Each duration must be positive and divisible by sample interval")
            if any(q < 0 or q > MAX_POWER_PERCENT for q in (segment.q1_percent, segment.q2_percent)):
                raise ValueError("Power command outside the declared envelope")
            total += segment.seconds
        if not math.isclose(total, DURATION):
            raise ValueError("Every experiment must have the same 120-second duration")

    def commands(self) -> list[list[float]]:
        self.validate()
        return [[s.q1_percent / 100.0, s.q2_percent / 100.0]
                for s in self.segments for _ in range(round(s.seconds / DT))]

    def to_dict(self) -> dict:
        return {"id": self.id, "segments": [asdict(s) for s in self.segments]}

    @classmethod
    def from_dict(cls, value: dict) -> Schedule:
        if set(value) != {"id", "segments"}:
            raise ValueError("Unexpected schedule fields")
        result = cls(value["id"], tuple(Segment(**s) for s in value["segments"]))
        result.validate()
        return result


def schedule(name: str, pairs: list[tuple[float, float]]) -> Schedule:
    result = Schedule(name, tuple(Segment(DURATION / len(pairs), a, b) for a, b in pairs))
    result.validate()
    return result


def experiment_library() -> list[Schedule]:
    return [
        schedule("left-pulse", [(60, 0), (60, 0), (0, 0), (0, 0)]),
        schedule("right-pulse", [(0, 60), (0, 60), (0, 0), (0, 0)]),
        schedule("alternate", [(60, 0), (0, 60), (60, 0), (0, 60)]),
        schedule("opposed-levels", [(60, 15), (15, 60), (60, 15), (15, 60)]),
        schedule("left-stair", [(15, 0), (30, 0), (45, 0), (60, 0)]),
        schedule("right-stair", [(0, 15), (0, 30), (0, 45), (0, 60)]),
        schedule("both-release", [(60, 60), (60, 60), (0, 0), (0, 0)]),
        schedule("staggered", [(60, 0), (60, 60), (0, 60), (0, 0)]),
    ]


def initial_schedule() -> Schedule:
    return schedule("initial-common", [(30, 30), (30, 30), (0, 0), (0, 0)])
