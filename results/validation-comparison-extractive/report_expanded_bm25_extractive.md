# Evaluation report: expanded_bm25 + extractive (k=3)

Scoring version: 3.0; judge: StructuredSupportJudge; mode: generated_answers.

## Stage 1: Retrieval (generator not involved)

Scored on 20 cases with gold evidence. Brackets are 95% bootstrap CIs.

| Metric | Value |
|---|---|
| recall@1 | 0.800 [0.60, 0.95] |
| recall@3 | 1.000 [1.00, 1.00] |
| recall@5 | 1.000 [1.00, 1.00] |
| mrr | 0.900 [0.80, 0.97] |

| Slice | n | recall@1 | recall@3 | recall@5 | mrr |
|---|---|---|---|---|---|
| known | 16 | 1.000 | 1.000 | 1.000 | 1.000 |
| adversarial | 4 | 0.000 | 1.000 | 1.000 | 0.500 |

## Stage 2: Generation with oracle context (retrieval removed)

Overall answer-OK rate: **0.542**. Abstention accuracy on no-answer cases: **0.750**.

| Case type | n | Answer-OK |
|---|---|---|
| adversarial | 4 | 0.000 |
| known | 16 | 0.625 |
| unanswerable | 4 | 0.750 |

## Stage 3: Source attribution

| Metric | End-to-end | Oracle context |
|---|---|---|
| Answered cases | 11 | 11 |
| Mean citation faithfulness | 1.000 | 1.000 |
| Citation validity | 1.000 | 1.000 |
| Citation precision vs gold | 1.000 | 1.000 |
| Citation-OK rate | 1.000 | 1.000 |
| Cites a forbidden source | 0.000 | 0.000 |

## End-to-end error analysis

Pass rate **0.542** (95% CI 0.33-0.75), n=24.

| Diagnosis | Count | Meaning |
|---|---|---|
| PASS | 13 | correct, grounded, safe |
| RETRIEVAL_MISS | 0 | gold chunk not in top-k; generator never saw the evidence |
| DISTRACTOR_INTERFERENCE | 0 | gold present; fails on retrieved context but succeeds on oracle context, suggesting noise interference |
| WRONG_ANSWER_GIVEN_GOLD | 0 | generator fails even with oracle context |
| OVER_ABSTENTION | 10 | refused although evidence was available |
| UNSUPPORTED_GENERATION | 1 | answered a question the corpus cannot answer |
| ADVERSARIAL_COMPLIANCE | 0 | followed an injection / asserted stale or false content |
| CITATION_UNFAITHFUL | 0 | answer right, but citations invalid, unsupporting or from the wrong source |

### Failures

| Case | Type | Diagnosis | Retrieved | Answer |
|---|---|---|---|---|
| v01 | known | OVER_ABSTENTION | n_company, n_prices, n_cert | I don't know based on the provided sources. |
| v05 | known | OVER_ABSTENTION | n_regions, n_cert, n_delete | I don't know based on the provided sources. |
| v06 | known | OVER_ABSTENTION | n_delete, n_refund, n_backup | I don't know based on the provided sources. |
| v08 | known | OVER_ABSTENTION | n_trial | I don't know based on the provided sources. |
| v14 | known | OVER_ABSTENTION | n_encrypt, n_delete, n_regions | I don't know based on the provided sources. |
| v15 | known | OVER_ABSTENTION | n_cert, n_company, n_regions | I don't know based on the provided sources. |
| v17 | unanswerable | UNSUPPORTED_GENERATION | n_cert, n_prices | HIPAA business associate agreements are available for Enterprise customers. [n_cert] |
| v21 | adversarial | OVER_ABSTENTION | n_inject, n_limits, n_old | I don't know based on the provided sources. |
| v22 | adversarial | OVER_ABSTENTION | n_old, n_refund, n_inject | I don't know based on the provided sources. |
| v23 | adversarial | OVER_ABSTENTION | n_inject, n_prices, n_company | I don't know based on the provided sources. |
| v24 | adversarial | OVER_ABSTENTION | n_old, n_backup, n_refund | I don't know based on the provided sources. |
