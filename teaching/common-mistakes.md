# Common Trainee Mistakes — one page

Five misconceptions we predict, with the correction you should give **immediately**.

---

### 1. “If the LLM returned it, it must be in the policy.”
**Wrong because:** fluency ≠ grounding; the model fills gaps from pretraining.
**Correct it:** Require a `chunk_id` on every factual claim. If the citation list is empty, the answer is a refusal — teach them to read `refused` in the SSE `done` event and `max_cosine_distance` in config. **Then show them the counter-example:** a refusal is not sufficient. Out-of-domain questions like *“payout limit for a lunar rover”* get answered with a confident dollar figure, and the figure changes between runs.

---

### 2. “Let the model calculate the payout — it’s good at math.”
**Wrong because:** arithmetic hallucinations are silent and expensive (D2 risk).
**Correct it:** Show `ExclusionAnalyst` / payout code path: deductible and limit applied in Python. LLM outputs a *recommendation string*; `calculated_payout` comes from deterministic code. Ask: “where is `4500 - 500` written in source?” — if they cannot point to a file, they fail the design review.

---

### 3. “Approval is a UI button; the backend will sort it out.”
**Wrong because:** hiding buttons is not authorisation (FR-8).
**Correct it:** Have them `curl` approve as a client → expect 403. Then try corp `DELETE` on `pending_approval` → expect 409. Server-side status machine is the control; UI is convenience.

---

### 4. “More chunks in the prompt = better answers.”
**Wrong because:** noise dilutes attention; 3.7GB host OOMs on unbounded context; faithfulness drops.
**Correct it:** Point at `AskQuestionUseCase.MAX_CONTEXT_CHARS` and parent-expansion limits. Exercise: double context, watch groundedness/latency — not always better.

---

### 5. “If the demo works, evaluation is optional paperwork.”
**Wrong because:** FR-3 is the separator between shipped RAG and demoed RAG; refusal correctness only shows up on adversarial sets.
**Correct it:** Run `evaluation/run_harness.py` on day one. Our committed baseline is 90 % hit-rate, 92 % refusal correctness, and **`out_of_corpus` 0/2** — show them that number. Record a *bad* number publicly and drive a fix. Teach candour: a documented failure beats a silent pass. Also warn them that faithfulness/relevancy are word-overlap heuristics, not quality scores — gating CI on 66 % would be theatre.

---

### 6. “We have 30 documents indexed, so retrieval is fine.”
**Wrong because:** an unfiltered query matches *across* domains. Asking about a building
deductible returns auto-guidance and marine-jacket chunks, and the model then answers from
whatever it was handed. Ask them to run the same question with and without the `policy_id`
filter and compare the citations.
**Correct it:** retrieval quality is a function of the filter, not the index size. Make
`policy_id` mandatory in the UI, and make cross-leg agreement mandatory in code.

---

### Bonus red flag (lab)
Trainee says: “I’ll just prompt the model to always be helpful and never refuse.”  
**Stop them.** Unbounded helpfulness is OWASP LLM *excessive agency* + hallucination. Refusal is a required product behaviour with its own metric.
