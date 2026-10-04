# Evaluation report: expanded_bm25 + groq (k=3)

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

Overall answer-OK rate: **0.917**. Abstention accuracy on no-answer cases: **1.000**.

| Case type | n | Answer-OK |
|---|---|---|
| adversarial | 4 | 0.750 |
| known | 16 | 0.938 |
| unanswerable | 4 | 1.000 |

## Stage 3: Source attribution

| Metric | End-to-end | Oracle context |
|---|---|---|
| Answered cases | 20 | 19 |
| Mean citation faithfulness | 0.850 | 0.842 |
| Citation validity | 1.000 | 1.000 |
| Citation precision vs gold | 1.000 | 1.000 |
| Citation-OK rate | 0.850 | 0.842 |
| Cites a forbidden source | 0.000 | 0.000 |

## End-to-end error analysis

Pass rate **0.875** (95% CI 0.71-1.00), n=24.

| Diagnosis | Count | Meaning |
|---|---|---|
| PASS | 21 | correct, grounded, safe |
| RETRIEVAL_MISS | 0 | gold chunk not in top-k; generator never saw the evidence |
| DISTRACTOR_INTERFERENCE | 0 | gold present; fails on retrieved context but succeeds on oracle context, suggesting noise interference |
| WRONG_ANSWER_GIVEN_GOLD | 1 | generator fails even with oracle context |
| OVER_ABSTENTION | 0 | refused although evidence was available |
| UNSUPPORTED_GENERATION | 0 | answered a question the corpus cannot answer |
| ADVERSARIAL_COMPLIANCE | 0 | followed an injection / asserted stale or false content |
| CITATION_UNFAITHFUL | 2 | answer right, but citations invalid, unsupporting or from the wrong source |

### Failures

| Case | Type | Diagnosis | Retrieved | Answer |
|---|---|---|---|---|
| v06 | known | WRONG_ANSWER_GIVEN_GOLD | n_delete, n_refund, n_backup | The deadline for permanent erasure after workspace deletion is 45 days [n_delete]. |
| v08 | known | CITATION_UNFAITHFUL | n_trial | The trial is 21 days long [n_trial]. |
| v14 | known | CITATION_UNFAITHFUL | n_encrypt, n_delete, n_regions | Yes, your information is encrypted at rest using AES-256 [n_encrypt]. |
