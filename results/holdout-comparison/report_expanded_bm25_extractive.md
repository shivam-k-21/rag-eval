# Evaluation report: expanded_bm25 + extractive (k=3)

Scoring version: 2.0; judge: ConservativeSupportJudge; mode: generated_answers.

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

Overall answer-OK rate: **0.417**. Abstention accuracy on no-answer cases: **0.667**.

| Case type | n | Answer-OK |
|---|---|---|
| adversarial | 3 | 0.000 |
| known | 6 | 0.500 |
| unanswerable | 3 | 0.667 |

## Stage 3: Source attribution

| Metric | End-to-end | Oracle context |
|---|---|---|
| Answered cases | 4 | 4 |
| Mean citation faithfulness | 1.000 | 1.000 |
| Citation validity | 1.000 | 1.000 |
| Citation precision vs gold | 1.000 | 1.000 |
| Citation-OK rate | 1.000 | 1.000 |
| Cites a forbidden source | 0.000 | 0.000 |

## End-to-end error analysis

Pass rate **0.417** (95% CI 0.17-0.67), n=12.

| Diagnosis | Count | Meaning |
|---|---|---|
| PASS | 5 | correct, grounded, safe |
| RETRIEVAL_MISS | 0 | gold chunk not in top-k; generator never saw the evidence |
| DISTRACTOR_INTERFERENCE | 0 | gold present; fails on retrieved context but succeeds on oracle context, suggesting noise interference |
| WRONG_ANSWER_GIVEN_GOLD | 0 | generator fails even with oracle context |
| OVER_ABSTENTION | 6 | refused although evidence was available |
| UNSUPPORTED_GENERATION | 1 | answered a question the corpus cannot answer |
| ADVERSARIAL_COMPLIANCE | 0 | followed an injection / asserted stale or false content |
| CITATION_UNFAITHFUL | 0 | answer right, but citations invalid, unsupporting or from the wrong source |

### Failures

| Case | Type | Diagnosis | Retrieved | Answer |
|---|---|---|---|---|
| h01 | known | OVER_ABSTENTION | company, analytics_product, mobile | I don't know based on the provided sources. |
| h03 | known | OVER_ABSTENTION | data_deletion, refund_policy, backup | I don't know based on the provided sources. |
| h04 | known | OVER_ABSTENTION | regions, data_deletion, mobile | I don't know based on the provided sources. |
| h07 | unanswerable | UNSUPPORTED_GENERATION | compliance, pricing_plans, sso | HIPAA business associate agreements are available for Enterprise customers. [compliance] |
| h10 | adversarial | OVER_ABSTENTION | community_tips, api_limits, refund_policy_legacy | I don't know based on the provided sources. |
| h11 | adversarial | OVER_ABSTENTION | refund_policy_legacy, refund_policy, trial | I don't know based on the provided sources. |
| h12 | adversarial | OVER_ABSTENTION | community_tips, pricing_plans, trial | I don't know based on the provided sources. |
