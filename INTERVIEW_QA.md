# 50 interview questions and answers: RAG reliability evaluation

These answers describe the implemented project. Proposed improvements are marked
as future work. Use the explanations as speaking notes and adapt the wording to
your own contribution. A three-case API smoke test is not a full benchmark.

## Project purpose and architecture

### 1. How would you explain this project in one minute?

**Answer:** This is a Python framework for evaluating retrieval-augmented generation systems. It separates retrieval quality, answer generation, and source attribution so an incorrect answer can be traced to a likely cause. It compares end-to-end answers with answers produced using annotated oracle evidence, then generates per-case diagnoses and aggregate reports. It supports reproducible lexical baselines and live Anthropic, Gemini, and Groq generators.

### 2. What problem does the project solve?

**Answer:** A single accuracy score cannot explain whether the system retrieved the wrong document, misread good evidence, failed to abstain, or cited an unsuitable source. This framework measures those behaviors separately. The resulting diagnosis helps decide whether to improve retrieval, generation, evidence trust, or citation handling rather than changing every component at once.

### 3. What is RAG, and how does this project evaluate it?

**Answer:** RAG retrieves external evidence for a question and supplies that evidence to a generator. In this project, BM25 or TF-IDF retrieves passages, a generator answers using the selected context, and scoring checks the answer and citations. The project evaluates a RAG workflow; it does not train a model, crawl websites, or build a document-ingestion service.

### 4. What are the main evaluation stages?

**Answer:** Retrieval measures whether gold evidence appears in ranked results. Oracle generation evaluates answering with annotated evidence available. Attribution measures citation validity, lexical support, overlap with gold sources, and forbidden-source use. Diagnosis combines these outcomes into a single failure label per case. Retrieval metrics are calculated without invoking the generator.

### 5. Describe the execution flow from the CLI to the report.

**Answer:** The CLI parses arguments, loads and validates JSONL data, and initializes the selected retriever and generator. `run_eval` obtains rankings, constructs retrieved and oracle contexts, generates both sets of answers, scores them, and assigns diagnoses. Reporting writes JSON and Markdown, while the CLI prints a compact comparison table. Input fingerprints and run settings accompany the results.

### 6. Why did you separate retrievers, generators, and support judges?

**Answer:** They answer different questions and change independently. A retriever returns ranked document IDs, a generator returns an `Answer`, and a support judge decides whether evidence supports a claim. Small protocol contracts make it possible to replace a lexical retriever with a semantic retriever or the lexical judge with an entailment model without rewriting the evaluation pipeline.

### 7. Why use Python with minimal dependencies?

**Answer:** Python makes the evaluation logic easy to inspect and test, while the standard library covers data loading, statistics, HTTP requests, and reporting. The local baselines and Gemini/Groq adapters need no additional runtime libraries; Anthropic uses its optional SDK. This reduces setup friction, although implementing HTTP handling ourselves also creates responsibility for transport and response validation.

### 8. Which files would you show an interviewer first?

**Answer:** I would start with `evaluate.py` because it expresses the staged evaluation and diagnosis logic. Then I would show `types.py` for the data contracts, `retrieval.py` for the baselines, and `attribution.py` for the scoring assumptions. `cli.py`, provider adapters, and `report.py` demonstrate how those components form a usable application. `ARCHITECTURE.md` explains the complete structure.

### 9. Why use dataclasses and protocols?

**Answer:** Dataclasses make documents, cases, answers, and scores explicit and readable. Immutable documents and cases help keep annotations stable during a run. Protocols describe the behavior expected from replaceable components without requiring a shared inheritance hierarchy. Type hints improve understanding, but runtime validation is still necessary because annotations alone do not enforce input correctness.

### 10. Is this a production RAG system?

**Answer:** It is an evaluation framework and a small reference RAG workflow, with a separate local report visualizer. It does not include an authentication service, persistent vector index, or large-scale ingestion pipeline. Its component contracts are reusable, but synthetic data, substring correctness checks, and bounded support rules are insufficient for claiming production reliability. A production evaluation would need representative data and independently validated judges.

## Data and retrieval

### 11. What does the dataset contain?

**Answer:** The development corpus has 18 fictional passages and 37 cases; 12 separate post-audit cases were added later. The original 37 comprise 22 known-answer, 7 unanswerable, and 8 adversarial questions. Cases cover paraphrases, prompt injection, stale policies, distractor products, false premises, and negation. Fictional facts reduce the opportunity for a model to answer from memorized real-world knowledge, although that does not guarantee complete absence of prior-knowledge effects.

### 12. What are the document, case, and answer schemas?

**Answer:** A `Doc` contains an ID, title, and text. A `Case` contains a question, type, gold source IDs, acceptable answer aliases, forbidden phrases and sources, an abstention requirement, and tags. An `Answer` contains text, citation IDs, and an explicit abstention flag. These contracts keep ground-truth annotations separate from generated output.

### 13. Why store the data in JSONL?

**Answer:** JSONL keeps each document or case on an independent line, making records easy to append and inspect. The loader can report the specific line responsible for an invalid record. It handles blank lines and rejects malformed or empty datasets. The current loader still loads everything into memory, so JSONL does not make this implementation a streaming system.

### 14. What input validation is implemented?

**Answer:** The project rejects empty required strings, unsupported case types, invalid annotation sequences, duplicate IDs, missing referenced documents, and overlap between gold and forbidden source IDs. CLI validation checks context size, coverage threshold, case limits, intervals, and retry limits. Unanswerable cases automatically require abstention. Validation prevents broken annotations from silently corrupting reported scores.

### 15. How are documents chunked?

**Answer:** Each document's text field is already one retrieval passage. There is no automatic chunking pipeline in the current implementation. For larger documents, I would add preprocessing that creates stable chunk IDs and preserves parent-document and version metadata. Chunk size and overlap would then become explicit experimental parameters because they affect both retrieval and answer grounding.

### 16. How does BM25 work in this implementation?

**Answer:** BM25 rewards query terms that occur in a document, gives rarer terms greater weight, and applies term-frequency saturation and document-length normalization. The defaults are `k1=1.5` and `b=0.75`. The implementation precomputes term counts, document frequencies, inverse document frequencies, and lengths. Search scans documents and sums scores for the unique content tokens in the question.

### 17. What is the difference between BM25 and TF-IDF here?

**Answer:** BM25 explicitly models term-frequency saturation and adjusts for document length. TF-IDF constructs vectors using logarithmic term frequency and smoothed inverse document frequency, then calculates cosine similarity after normalization. Both are lexical baselines and depend on token overlap. Neither understands synonyms or semantic equivalence in the way an embedding model might.

### 18. What text preprocessing is used, and what can go wrong?

**Answer:** Text is lowercased, tokenized, filtered through stopwords and lightly stemmed for retrieval. The conservative support judge separately preserves polarity and checks numbers, units and subjects, compensating for some information lost by the original tokenization. These are bounded rules rather than semantic understanding; valid paraphrases and complex contradictions still need semantic or human review.

### 19. How do you keep retrieval deterministic?

**Answer:** The retrievers use fixed token-processing and scoring logic. Equal scores are ordered by document ID, and zero-score documents are omitted. This avoids arbitrary tie ordering and prevents unrelated passages from being returned simply to fill K positions. The deterministic retrieval and extractive generator make local regression comparisons straightforward.

### 20. What does increasing K change?

**Answer:** K determines how many retrieved chunks reach the generator. Increasing it may supply missing evidence but also introduces more distractors, more input tokens, and potentially greater latency or quota consumption. Retrieval is performed deeply enough to cover both the generation K and every requested metric cutoff. I would choose K on development data using quality and resource measurements, not assume larger is always better.

## Metrics and experimental design

### 21. How is Recall@K calculated?

**Answer:** Recall@K is the number of unique gold document IDs in the first K results divided by the total number of unique gold IDs. If a case has two gold documents and only one is retrieved, recall is 0.5. Cases without gold evidence are excluded from aggregate retrieval scoring. This is evidence coverage, not answer accuracy.

### 22. What is MRR, and why use it alongside recall?

**Answer:** Reciprocal rank is `1/r` where r is the rank of the first gold document, or zero if none is found. MRR averages that quantity across scored cases. It rewards placing relevant evidence early, while recall measures how much gold evidence is retrieved. A multi-source question can have excellent MRR but incomplete recall because only its first relevant source ranked well.

### 23. Is a retrieval hit equivalent to complete evidence retrieval?

**Answer:** No. The current hit flag means at least one gold ID appears in the generator's top-K context. A question requiring multiple documents could register a hit while missing another necessary source. Recall captures part of that gap, but the diagnosis uses the simpler hit condition. A future multi-hop evaluation should explicitly track whether all required evidence reached the generator.

### 24. What is oracle context?

**Answer:** For cases with gold evidence, oracle context combines annotated forbidden or hard-negative passages with the gold passages, deduplicating IDs and placing negatives first. This makes the gold evidence available independently of its retrieval rank while still testing distractor resistance. For cases without gold, oracle context reuses the retrieved top-K passages. It is an annotated intervention, not universally clean context.

### 25. Why generate answers using both retrieved and oracle contexts?

**Answer:** The comparison helps locate the failure. If retrieved-context answering fails but oracle answering succeeds, improving the evidence presented to the model may help. If the model also fails when gold evidence is available, generation or evidence interpretation deserves attention. Because oracle context can contain hard negatives and has different size or ordering, this comparison suggests a cause rather than proving one.

### 26. How is answer correctness evaluated?

**Answer:** Answers and aliases are lowercased and whitespace-normalized, then checked for an acceptable substring. Forbidden phrases cause failure even if a correct alias is present, except narrowly recognized standalone refusals to reveal the system prompt. Abstention-required cases must explicitly abstain. Cases without answer aliases otherwise rely on forbidden-phrase checks, so their acceptance rule can be permissive. This is a simple deterministic evaluator, not a semantic truth judge.

### 27. What are the limitations of substring correctness checks?

**Answer:** A paraphrase may be correct but miss every reference alias, while a wrong sentence can contain a correct alias. For example, saying “the price is not $40” still contains `$40` unless another rule catches the contradiction. I would improve this with structured expected facts, entailment checks, and human-reviewed grading. The current score should be interpreted within its matching rules.

### 28. How does the extractive generator decide to abstain?

**Answer:** It measures the fraction of the question's unique content tokens covered by each context sentence and selects the best-covered sentence. If there is no matching sentence or coverage is below `min_coverage`, it abstains. The default is 0.6. This is a lexical decision rule, not a calibrated probability of answer correctness.

### 29. What does the threshold sweep demonstrate?

**Answer:** The sweep runs coverage thresholds from 0.4 through 0.8 and compares pass rate, abstention behavior, and diagnosis counts. On the shipped dataset, higher thresholds reduce unsupported generation but increase over-abstention. At 0.8 the baseline has zero unsupported-generation diagnoses and 14 over-abstentions. I would tune a threshold on separate development data and then assess it on held-out cases.

### 30. How is abstention accuracy reported?

**Answer:** In the oracle-generation summary, it is the share of `must_abstain` cases whose generated answer has the abstention flag set. Those cases include unanswerable questions and any adversarial cases explicitly requiring abstention. The separate `answer_ok` check also considers forbidden phrases, so abstention accuracy is not identical to complete safe-answer acceptance. No applicable cases produces an undefined metric.

### 31. Why include confidence intervals?

**Answer:** A score estimated from a small case set has substantial sampling uncertainty. The project uses 2,000 seeded bootstrap resamples and reports percentile intervals for retrieval metrics and end-to-end pass rate. These intervals describe variability under resampling of the observed cases; they do not account for dataset bias, judge errors, or every source of model variability.

### 32. Does a three-case 100% result prove the model is reliable?

**Answer:** No. The smoke cases are only the first three known-answer questions, not a representative sample of unanswerable or adversarial behavior. With every observed value equal to one, a percentile bootstrap can even produce a degenerate interval at one. That is a limitation of resampling such a tiny sample, not proof that the true success rate is 100%.

### 33. What verified baseline results can you discuss?

**Answer:** With BM25, the extractive generator, and K=3, the saved baseline reports Recall@3 of about 0.929, MRR of about 0.878, oracle answer-OK of about 0.622, and end-to-end pass rate of about 0.649. BM25 and TF-IDF tie on the aggregate metrics in this small corpus. These results illustrate the evaluation approach; they do not establish that the retrievers perform equally on larger datasets.

### 34. What did the live Groq smoke test show?

**Answer:** The saved Groq smoke report used `qwen/qwen3.8-27b`, not GPT-OSS, and evaluated three known-answer cases. Retrieval metrics and oracle answer-OK were 1.0, but end-to-end pass rate was 0.667 because one answer failed citation support scoring. The saved full report uses Qwen too: 27/37 originally, or 32/37 when rescoring the same answers under version 2.0. Those are grading comparisons, not a model improvement; no completed GPT-OSS full report was verified here.

## Attribution, safety, and diagnosis

### 35. What is citation faithfulness in this project?

**Answer:** Scoring version 2.0 measures the fraction of substantive claims supported by the source IDs attached to that claim. The default conservative judge requires 80% lexical support within a source sentence plus number, unit, polarity and subject guards. Narrow standalone system-prompt refusals are exempted, but uncited factual claims are not. Optional Groq judging supplies semantic support decisions with extra API use.

### 36. How do validity, precision, and faithfulness differ?

**Answer:** Validity checks that citation IDs exist in both the corpus and the supplied context. Precision measures the fraction of unique cited IDs that belong to the case's gold evidence, when gold is available. Faithfulness measures lexical support for the answer. A citation can exist and identify a gold source while the associated answer still fails support scoring.

### 37. What makes the combined citation check pass?

**Answer:** Citations must be present and valid, faithfulness must be at least 0.999, no forbidden source may be cited, and the citations must overlap gold sources when gold is defined. Duplicate IDs are counted once. The check does not require citation precision to equal one or every gold document to be cited. It is therefore stronger than validity alone but not complete source-level correctness.

### 38. Why are attribution metrics undefined for abstentions?

**Answer:** An abstained answer makes no substantive answer claim to support, so forcing a zero or one would distort the average. Attribution fields are `None` for abstentions, and attribution summaries focus on answered cases. Undefined numeric aggregates become JSON `null`. Abstention correctness is evaluated separately, preventing a system from improving its citation score simply by refusing everything.

### 39. Can a faithful answer still be unsafe or wrong?

**Answer:** Yes. An answer can accurately repeat an injected or superseded source that should not be trusted. Lexical support can also accept contradictions because shared words do not establish entailment. That is why the project checks forbidden sources and forbidden phrases separately. Faithfulness measures a relationship to evidence under a judge, not whether that evidence is authoritative or true.

### 40. How are prompt injection and stale sources tested?

**Answer:** Adversarial cases include passages or questions with malicious instructions and evidence that should not be trusted. Gold and forbidden IDs identify appropriate and inappropriate sources, while forbidden phrases mark unacceptable content. Hosted prompts instruct the model to treat sources as untrusted data. The evaluator tests whether the output violates the annotations; the prompt instruction alone is not a security guarantee.

### 41. What are the eight diagnosis labels?

**Answer:** `PASS` means the answer and applicable citation checks pass. The failure labels are `RETRIEVAL_MISS`, `DISTRACTOR_INTERFERENCE`, `WRONG_ANSWER_GIVEN_GOLD`, `OVER_ABSTENTION`, `UNSUPPORTED_GENERATION`, `ADVERSARIAL_COMPLIANCE`, and `CITATION_UNFAITHFUL`. They respectively describe missing retrieved gold, failure despite oracle success, failure even with oracle evidence, unnecessary refusal, answering when abstention was required, forbidden output, and unacceptable citations for an otherwise acceptable answer.

### 42. Why does diagnosis precedence matter?

**Answer:** A case may have several problems, but the implementation assigns one label. After checking for a pass, it prioritizes forbidden output, then failed abstention requirements, then attribution failure for an acceptable answer, followed by missing gold, over-abstention, and the oracle comparison. For example, forbidden content takes priority over a retrieval miss. The taxonomy is a useful summary, not an exhaustive list of every simultaneous defect.

### 43. What does `DISTRACTOR_INTERFERENCE` prove?

**Answer:** It does not prove that a particular distractor caused failure. It means gold was retrieved, the end-to-end answer failed without abstaining, and oracle answer acceptance succeeded. Oracle context can contain negatives, and the comparison changes source ordering and composition. To strengthen causal claims, I would add controlled clean-gold, gold-plus-one-distractor, and randomized-order experiments.

### 44. How would you investigate the Qwen citation failure?

**Answer:** The original report shows k03 had the correct 30-day fact and a valid gold citation but zero lexical support. The evidence confirms the paraphrase, so version 2.0 removes a narrow conversational wrapper and passes it. The original report remains unchanged. Wrong durations, wrong units and negated refund claims have regression tests so that fixing the false rejection does not remove these checks.

## API integration, engineering, and future work

### 45. How are hosted providers integrated without changing the evaluator?

**Answer:** Anthropic, Gemini, and Groq adapters all implement `generate(question, context) -> Answer`. They construct source-only prompts, call their provider, extract final text and citation IDs, and recognize the exact `INSUFFICIENT_EVIDENCE` marker as abstention. Gemini and Groq use standard-library HTTP; Anthropic uses its SDK. The CLI registry selects the adapter, while `run_eval` remains provider independent.

### 46. What is special about the Groq adapter?

**Answer:** It calls Groq's chat-completion endpoint using `GROQ_API_KEY` as a bearer credential, with temperature zero and a 2,048-token completion budget. GPT-OSS 20B and 120B receive low reasoning effort and exclude reasoning from responses. Scoring reads final `message.content`, not the separate reasoning field. The adapter requires normal completion and rejects empty, truncated, or blocked output rather than scoring it as a valid answer.

### 47. How did you handle HTTP 503 and HTTP 429?

**Answer:** Temporary server errors such as 503 use bounded exponential backoff, with three retries by default and request spacing respected. For Groq, a 429 is retried only when it supplies a numeric `Retry-After` of at most 60 seconds. Gemini reports structured quota details when available but does not automatically retry quota errors. Longer spacing helps short-term throughput; it cannot replenish exhausted daily quotas. The model never changes silently during retries.

### 48. How do you control request volume and protect API keys?

**Answer:** A single-retriever 37-case run plans 74 generation requests before retries and cache hits. Pacing and case limits control volume; keys are kept in environment variables and headers. Hosted runs now checkpoint each completed answer atomically and resume on the same command. Cache identity includes model, prompt, implementation, question, stage and actual context. Optional semantic judging makes additional requests, also with cached verdicts.

### 49. How did you test the project and make runs auditable?

**Answer:** The latest verified suite has 144 passing tests, including interrupted-run resume, cache invalidation, corrupt records, claim-level citation binding, numerical and polarity guards, mocked entailment verdicts, structured support probes, and visualizer evidence fingerprints. Reports record scoring version, data fingerprints and model settings; replay reports identify their original artifact. Reusing cached answers is useful for grading comparisons, but independent hosted trials require fresh outputs or --no-resume.

### 50. What would you improve next, and how would you evaluate the improvement?

**Answer:** The project now has conservative and structured scoring, an optional Groq entailment judge, resume checkpoints, per-case progress, vocabulary expansion, and a separate report visualizer. Fresh validation uses a different fictional corpus, 24 questions, and labeled support/refusal probes. The controlled offline comparison improved retrieval but left end-to-end accuracy unchanged. Next are independent real-world data, human-validated judging, dense or hybrid retrieval, and latency/token tracking. I would keep configurations fixed and distinguish regrading gains from model gains.

## Local references

- [Architecture](ARCHITECTURE.md)
- [Project README and baseline discussion](README.md)
- [Groq setup](GROQ_SETUP.md)
- [Gemini setup](GEMINI_SETUP.md)
- [Saved BM25 baseline](results/report_bm25_extractive.md)
- [Saved Qwen Groq smoke report](results/groq-smoke/report_bm25_groq.md)

Results and test counts above reflect the verified state at preparation time.
Check the saved configuration before quoting a model's score, and do not treat
one model's smoke report as another model's full evaluation.
