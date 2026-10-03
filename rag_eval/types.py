from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Doc:
    id: str
    title: str
    text: str

    def __post_init__(self):
        for name in ("id", "title", "text"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Doc.{name} must be a nonempty string")


@dataclass(frozen=True)
class Case:
    id: str
    type: str                      # known | unanswerable | adversarial
    question: str
    gold_ids: tuple[str, ...] = ()
    answers: tuple[str, ...] = ()  # acceptable answer substrings (any match)
    forbidden_phrases: tuple[str, ...] = ()
    forbidden_ids: tuple[str, ...] = ()  # hard negatives: stale / injected / distractor chunks
    must_abstain: bool = False
    tags: tuple[str, ...] = ()

    def __post_init__(self):
        if self.type not in {"known", "unanswerable", "adversarial"}:
            raise ValueError(f"Unknown case type: {self.type}")
        for name in ("id", "question"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Case.{name} must be a nonempty string")
        for name in ("gold_ids", "answers", "forbidden_phrases", "forbidden_ids", "tags"):
            values = getattr(self, name)
            if not isinstance(values, (list, tuple)) or any(not isinstance(v, str) or not v.strip() for v in values):
                raise ValueError(f"Case.{name} must be a sequence of nonempty strings")
            object.__setattr__(self, name, tuple(values))
        if not isinstance(self.must_abstain, bool):
            raise ValueError("Case.must_abstain must be a boolean")
        # An unanswerable case must always be abstained on, however the Case was constructed.
        if self.type == "unanswerable" and not self.must_abstain:
            object.__setattr__(self, "must_abstain", True)


@dataclass
class Answer:
    text: str
    citations: list[str] = field(default_factory=list)
    abstained: bool = False


def load_docs(path: str | Path) -> list[Doc]:
    return _load_records(path, Doc)


def load_cases(path: str | Path) -> list[Case]:
    return _load_records(path, Case)


def _load_records(path, record_type):
    records = []
    seen = set()
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = record_type(**json.loads(line))
            if record.id in seen:
                raise ValueError(f"Duplicate id: {record.id}")
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{path}:{number}: {exc}") from exc
        seen.add(record.id)
        records.append(record)
    if not records:
        raise ValueError(f"{path}: dataset is empty")
    return records


def validate_dataset(cases: list[Case], docs: list[Doc]) -> None:
    if not docs or not cases:
        raise ValueError("Corpus and cases must both be nonempty")
    for name, records in (("document", docs), ("case", cases)):
        if len({r.id for r in records}) != len(records):
            raise ValueError(f"Duplicate {name} ids")
    ids = {d.id for d in docs}
    for case in cases:
        missing = set((*case.gold_ids, *case.forbidden_ids)) - ids
        if missing:
            raise ValueError(f"Case {case.id}: unknown document ids: {', '.join(sorted(missing))}")
        if set(case.gold_ids) & set(case.forbidden_ids):
            raise ValueError(f"Case {case.id}: gold and forbidden ids overlap")
