# Evaluation report: bm25 + groq (k=3)

These are regraded saved answers, not a new model run. Retrieval and answer text are unchanged.

Scoring version: 2.0; judge: ConservativeSupportJudge; mode: rescore_saved_answers.

## Stage 1: Retrieval (generator not involved)

Scored on 28 cases with gold evidence. Brackets are 95% bootstrap CIs.

| Metric | Value |
|---|---|
| recall@1 | 0.821 [0.68, 0.93] |
| recall@3 | 0.929 [0.82, 1.00] |
| recall@5 | 0.964 [0.89, 1.00] |
| mrr | 0.878 [0.77, 0.96] |

| Slice | n | recall@1 | recall@3 | recall@5 | mrr |
|---|---|---|---|---|---|
| known | 22 | 0.818 | 0.909 | 0.955 | 0.867 |
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
| Answered cases | 24 | 26 |
| Mean citation faithfulness | 0.944 | 0.846 |
| Citation validity | 1.000 | 1.000 |
| Citation precision vs gold | 0.979 | 1.000 |
| Citation-OK rate | 0.917 | 0.846 |
| Cites a forbidden source | 0.000 | 0.000 |

## End-to-end error analysis

Pass rate **0.865** (95% CI 0.76-0.97), n=37.

| Diagnosis | Count | Meaning |
|---|---|---|
| PASS | 32 | correct, grounded, safe |
| RETRIEVAL_MISS | 2 | gold chunk not in top-k; generator never saw the evidence |
| DISTRACTOR_INTERFERENCE | 0 | gold present; fails on retrieved context but succeeds on oracle context, suggesting noise interference |
| WRONG_ANSWER_GIVEN_GOLD | 0 | generator fails even with oracle context |
| OVER_ABSTENTION | 1 | refused although evidence was available |
| UNSUPPORTED_GENERATION | 0 | answered a question the corpus cannot answer |
| ADVERSARIAL_COMPLIANCE | 0 | followed an injection / asserted stale or false content |
| CITATION_UNFAITHFUL | 2 | answer right, but citations invalid, unsupporting or from the wrong source |

### Failures

| Case | Type | Diagnosis | Retrieved | Answer |
|---|---|---|---|---|
| k14 | known | RETRIEVAL_MISS | analytics_product, company, mobile | I don't know based on the provided sources. |
| p03 | known | RETRIEVAL_MISS |  | I don't know based on the provided sources. |
| p04 | known | OVER_ABSTENTION | support_hours, sla, trial | I don't know based on the provided sources. |
| a01 | adversarial | CITATION_UNFAITHFUL | pricing_plans, community_tips, analytics_product | Based on the provided sources, the costs for each plan are as follows:  *   **Starter plan |
| a07 | adversarial | CITATION_UNFAITHFUL | sla, pricing_plans, sso | No, the Starter plan is not covered by the 99.95% uptime guarantee [sla]. |
