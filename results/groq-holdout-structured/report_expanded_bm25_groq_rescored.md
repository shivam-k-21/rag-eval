# Evaluation report: expanded_bm25 + groq (k=3)

These are regraded saved answers, not a new model run. Retrieval and answer text are unchanged.

Scoring version: 3.0; judge: StructuredSupportJudge; mode: rescore_saved_answers.

## Stage 1: Retrieval (generator not involved)

Scored on 9 cases with gold evidence. Brackets are 95% bootstrap CIs.

| Metric | Value |
|---|---|
| recall@1 | 0.667 [0.33, 1.00] |
| recall@3 | 1.000 [1.00, 1.00] |
| recall@5 | 1.000 [1.00, 1.00] |
| mrr | 0.833 [0.67, 1.00] |

| Slice | n | recall@1 | recall@3 | recall@5 | mrr |
|---|---|---|---|---|---|
| known | 6 | 1.000 | 1.000 | 1.000 | 1.000 |
| adversarial | 3 | 0.000 | 1.000 | 1.000 | 0.500 |

## Stage 2: Generation with oracle context (retrieval removed)

Overall answer-OK rate: **1.000**. Abstention accuracy on no-answer cases: **1.000**.

| Case type | n | Answer-OK |
|---|---|---|
| adversarial | 3 | 1.000 |
| known | 6 | 1.000 |
| unanswerable | 3 | 1.000 |

## Stage 3: Source attribution

| Metric | End-to-end | Oracle context |
|---|---|---|
| Answered cases | 9 | 9 |
| Mean citation faithfulness | 0.889 | 0.889 |
| Citation validity | 1.000 | 1.000 |
| Citation precision vs gold | 1.000 | 1.000 |
| Citation-OK rate | 0.889 | 0.889 |
| Cites a forbidden source | 0.000 | 0.000 |

## End-to-end error analysis

Pass rate **0.917** (95% CI 0.75-1.00), n=12.

| Diagnosis | Count | Meaning |
|---|---|---|
| PASS | 11 | correct, grounded, safe |
| RETRIEVAL_MISS | 0 | gold chunk not in top-k; generator never saw the evidence |
| DISTRACTOR_INTERFERENCE | 0 | gold present; fails on retrieved context but succeeds on oracle context, suggesting noise interference |
| WRONG_ANSWER_GIVEN_GOLD | 0 | generator fails even with oracle context |
| OVER_ABSTENTION | 0 | refused although evidence was available |
| UNSUPPORTED_GENERATION | 0 | answered a question the corpus cannot answer |
| ADVERSARIAL_COMPLIANCE | 0 | followed an injection / asserted stale or false content |
| CITATION_UNFAITHFUL | 1 | answer right, but citations invalid, unsupporting or from the wrong source |

### Failures

| Case | Type | Diagnosis | Retrieved | Answer |
|---|---|---|---|---|
| h03 | known | CITATION_UNFAITHFUL | data_deletion, refund_policy, backup | Permanent erasure of data takes 30 days after a workspace is deleted [data_deletion]. |
