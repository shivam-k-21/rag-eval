# Evaluation report: bm25 + groq (k=3)

## Stage 1: Retrieval (generator not involved)

Scored on 3 cases with gold evidence. Brackets are 95% bootstrap CIs.

| Metric | Value |
|---|---|
| recall@1 | 1.000 [1.00, 1.00] |
| recall@3 | 1.000 [1.00, 1.00] |
| recall@5 | 1.000 [1.00, 1.00] |
| mrr | 1.000 [1.00, 1.00] |

| Slice | n | recall@1 | recall@3 | recall@5 | mrr |
|---|---|---|---|---|---|
| known | 3 | 1.000 | 1.000 | 1.000 | 1.000 |

## Stage 2: Generation with oracle context (retrieval removed)

Overall answer-OK rate: **1.000**. Abstention accuracy on no-answer cases: **n/a**.

| Case type | n | Answer-OK |
|---|---|---|
| known | 3 | 1.000 |

## Stage 3: Source attribution

| Metric | End-to-end | Oracle context |
|---|---|---|
| Answered cases | 3 | 3 |
| Mean citation faithfulness | 0.667 | 0.667 |
| Citation validity | 1.000 | 1.000 |
| Citation precision vs gold | 1.000 | 1.000 |
| Citation-OK rate | 0.667 | 0.667 |
| Cites a forbidden source | 0.000 | 0.000 |

## End-to-end error analysis

Pass rate **0.667** (95% CI 0.00-1.00), n=3.

| Diagnosis | Count | Meaning |
|---|---|---|
| PASS | 2 | correct, grounded, safe |
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
| k03 | known | CITATION_UNFAITHFUL | refund_policy, refund_policy_legacy, api_limits | You have 30 days from the date of purchase to request a full refund [refund_policy]. |
