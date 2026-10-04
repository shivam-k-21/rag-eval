# Validation-v1

This set uses Nimbus Storage, a new fictional 12-document corpus. It shares no
document IDs with Helios. Its 24 questions comprise 16 known-answer, four
unanswerable, and four adversarial cases. Quantities, locations, and wording
were specified before implementing the structured support judge.

`support_cases.jsonl` contains 28 labeled source-support probes, including
wrong subjects, borrowed numbers, units, negation, ambiguous references,
list membership, and deadline-versus-duration distinctions.
`refusal_cases.jsonl` contains eight safe-refusal and disclosure probes.
These are independent of generated answers and use assistant-authored labels.
They are a small synthetic validation set, not independent expert annotation
or representative production data. The related predicates are deliberately
within the proposed grader's intended scope.

Run `python scripts/validate_judge.py` to inspect both judges' decisions and
`python scripts/run_comparison.py` for a controlled offline RAG comparison.
Both commands write source fingerprints. Keep these files frozen; if later
results are used for tuning, use another set for subsequent validation.

The original 12 Helios holdout cases are now audited development evidence for
scoring version 3.0. Replaying them is a regression check, not fresh validation.
