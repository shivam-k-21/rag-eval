"""Atomic per-answer checkpoints; credentials never enter cache identity or files."""
import hashlib
import inspect
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from .types import Answer


class AnswerCheckpoint:
    def __init__(self, directory, resume=True):
        self.directory = Path(directory)
        self.resume = resume

    def generate(self, generator, case, context, stage):
        sources = []
        for cls in type(generator).__mro__:
            if cls is object:
                continue
            try:
                sources.append(inspect.getsource(cls))
            except (OSError, TypeError):
                sources.append(cls.__module__ + "." + cls.__qualname__)
        implementation = "\n".join(sources)
        settings = {name: getattr(generator, name) for name in
                    ("name", "model", "max_tokens", "min_coverage", "reasoning_effort", "SYSTEM")
                    if hasattr(generator, name)}
        identity = {"schema": 1, "implementation": hashlib.sha256(implementation.encode()).hexdigest(),
                    "settings": settings, "case_id": case.id, "question": case.question,
                    "stage": stage, "context": [asdict(doc) for doc in context]}
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        path = self.directory / f"{key}.json"
        if self.resume and path.exists():
            try:
                record = json.loads(path.read_text())
                value = record["answer"]
                if record["key"] != key or not isinstance(value["text"], str) or not isinstance(value["abstained"], bool):
                    raise ValueError("Invalid checkpoint record")
                if not isinstance(value["citations"], list) or any(not isinstance(v, str) for v in value["citations"]):
                    raise ValueError("Invalid checkpoint citations")
                return Answer(**value), True
            except (ValueError, TypeError, KeyError) as exc:
                raise RuntimeError(f"Invalid checkpoint {path}; remove that record or use --no-resume.") from exc
        answer = generator.generate(case.question, context)
        self.directory.mkdir(parents=True, exist_ok=True)
        record = {"key": key, "answer": asdict(answer)}
        # Each completed answer survives later API failures; replacement is atomic.
        fd, temporary = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(record, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return answer, False
