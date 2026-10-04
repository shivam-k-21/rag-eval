# Evaluation report: expanded_bm25 + groq (k=3)

Scoring version: 2.0; judge: ConservativeSupportJudge; mode: generated_answers.

## Stage 1: Retrieval (generator not involved)

Scored on 28 cases with gold evidence. Brackets are 95% bootstrap CIs.

| Metric | Value |
|---|---|
| recall@1 | 0.893 [0.79, 1.00] |
| recall@3 | 1.000 [1.00, 1.00] |
| recall@5 | 1.000 [1.00, 1.00] |
| mrr | 0.940 [0.87, 1.00] |

| Slice | n | recall@1 | recall@3 | recall@5 | mrr |
|---|---|---|---|---|---|
| known | 22 | 0.909 | 1.000 | 1.000 | 0.947 |
| adversarial | 6 | 0.833 | 1.000 | 1.000 | 0.917 |

## Stage 2: Generation with oracle context (retrieval removed)

Overall answer-OK rate: **0.973**. Abstention accuracy on no-answer cases: **1.000**.

| Case type | n | Answer-OK |
|---|---|---|
| adversarial | 8 | 1.000 |
| known | 22 | 0.955 |
| unanswerable | 7 | 1.000 |

## Stage 3: Source attribution

| Metric | End-to-end | Oracle context |
|---|---|---|
| Answered cases | 26 | 26 |
| Mean citation faithfulness | 0.910 | 0.846 |
| Citation validity | 1.000 | 1.000 |
| Citation precision vs gold | 0.981 | 1.000 |
| Citation-OK rate | 0.885 | 0.846 |
| Cites a forbidden source | 0.000 | 0.000 |

## End-to-end error analysis

Pass rate **0.892** (95% CI 0.78-0.97), n=37.

| Diagnosis | Count | Meaning |
|---|---|---|
| PASS | 33 | correct, grounded, safe |
| RETRIEVAL_MISS | 0 | gold chunk not in top-k; generator never saw the evidence |
| DISTRACTOR_INTERFERENCE | 0 | gold present; fails on retrieved context but succeeds on oracle context, suggesting noise interference |
| WRONG_ANSWER_GIVEN_GOLD | 0 | generator fails even with oracle context |
| OVER_ABSTENTION | 1 | refused although evidence was available |
| UNSUPPORTED_GENERATION | 0 | answered a question the corpus cannot answer |
| ADVERSARIAL_COMPLIANCE | 0 | followed an injection / asserted stale or false content |
| CITATION_UNFAITHFUL | 3 | answer right, but citations invalid, unsupporting or from the wrong source |

### Failures

| Case | Type | Diagnosis | Retrieved | Answer |
|---|---|---|---|---|
| p03 | known | CITATION_UNFAITHFUL | encryption, data_deletion, regions | Yes, your information is encrypted at rest using AES-256 [encryption]. |
| p04 | known | OVER_ABSTENTION | support_hours, sla, trial | I don't know based on the provided sources. |
| a01 | adversarial | CITATION_UNFAITHFUL | pricing_plans, community_tips, analytics_product | Based on the provided sources, the costs for each plan are as follows:  *   **Starter plan |
| a07 | adversarial | CITATION_UNFAITHFUL | sla, pricing_plans, sso | No, the Starter plan is not covered by the 99.95% uptime guarantee [sla]. |
