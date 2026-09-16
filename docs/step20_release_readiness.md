# AgDA Step 20 Release Readiness Report

## Status

**Step 20: PASSED**

AgDA has completed full backend regression, automated user-question QA,
natural-language persona testing, and targeted remediation of issues discovered
during manual QA.

This gate validates application behavior against the current `wave5_v1`
analytical release and metric version `1.0.0`.

---

## 1. Automated Backend Regression

Result:

- 16 integration suites passed
- 0 failed

Coverage includes:

- release loading
- metric registry
- analytics execution
- question routing
- question pipeline
- answer service
- API behavior
- clarification follow-ups
- conversation context
- API conversation memory
- request observability
- health and environment configuration
- API request limits
- contextual reference inheritance
- extension/yield comparison
- methodological follow-ups

**Result: PASS**

---

## 2. Automated User Question QA

Result:

- 23 / 23 cases passed
- 0 failures

Personas tested:

- Farmer
- General user
- Government / policy user
- Investor / stakeholder
- Researcher

Supported behavior includes:

- analytical answers
- clarification
- safe reframing
- unsupported-question handling
- conversational follow-ups
- metric switching
- evidence reporting
- methodological caution
- data-version provenance

**Result: PASS**

---

## 3. Manual Persona QA

Five conversational user journeys were tested using natural-language wording
that differed from the original engineering regression prompts.

### Farmer

Validated:

- natural crop-prevalence language
- crop replacement follow-up
- pronoun-based commercialization follow-up
- prescriptive recommendation guardrail

**Result: PASS**

### Government / Policy

Validated:

- natural geographic crop ranking
- state-comparison references
- metric switching while retaining comparison structure
- narrowing state rankings to an individual state

**Result: PASS**

### Researcher

Validated:

- descriptive extension/yield comparison
- comparison follow-up language
- non-causal interpretation
- descriptive food-security change

The extension/yield comparison uses eligible completed-harvest records and
compares observed median yield by reported planting-season extension status.

Observed medians:

- Received planting extension: approximately 1,790.5 kg/ha
- No planting extension: approximately 1,588.5 kg/ha

This comparison is explicitly presented as unadjusted and descriptive.
It does not establish that extension caused the observed difference.

**Result: PASS**

### Investor / Stakeholder

Validated:

- commercialization-share ranking by geography
- geographic follow-up
- profitability guardrail

AgDA does not infer profitability from commercialization because complete
production-cost and margin data are unavailable.

**Result: PASS**

### Climate / General User

Validated:

- natural climate-perception language
- North West Flood filtering
- methodological follow-up
- climate-event ranking

AgDA explicitly distinguishes community expectations of climate risk from a
meteorological forecast.

**Result: PASS**

---

## 4. Natural-Language Remediation Completed

Manual QA identified and corrected the following general classes of issues:

### Natural ranking and grouping

Examples now supported include:

- "What are farmers mostly growing in Kaduna?"
- "Where is rice grown most commonly?"
- "Where are rice farmers selling the largest share of their harvest?"
- "Which climate threat is viewed as the biggest overall?"

### Conversational reference inheritance

AgDA now supports contextual structures such as:

- "What about rice?"
- "How much of it do farmers usually sell?"
- "Which of those states gets the best rice yields?"
- "Show seller participation instead."
- "Can you compare them without saying extension caused the difference?"

### Guardrail intent recognition

Expanded recognition includes:

- individual crop recommendations
- planting recommendations
- profitability inference
- causal interpretation

### Methodological follow-ups

AgDA can answer questions about the interpretation of a previous result without
pretending that another analytical query was executed.

Example:

- "Is that an actual weather forecast?"

The response is derived from the methodological limitations of the preceding
climate metric.

---

## 5. Safety and Methodological Controls

The following controls remain active:

- descriptive statistics are not presented as causal effects;
- community climate expectations are not represented as forecasts;
- commercialization is not represented as profitability;
- crop evidence is not converted into individualized farming recommendations;
- unsupported questions return explicit limitations instead of fabricated
  statistics;
- minimum evidence thresholds remain enforced;
- data and metric versions remain exposed in API responses;
- request IDs support diagnostic tracing without exposing internal exceptions.

---

## 6. Release Integrity

Current analytical release:

- Data version: `wave5_v1`
- Metric version: `1.0.0`
- Registered metrics: `18`
- Release state: `stable`

The extension/yield comparison reuses the registered
`median_completed_yield` metric through the existing
`production_extension_view`.

No additional metric was added to the immutable Wave 5 release.

---

## 7. Known Limitations

AgDA remains a deterministic evidence-backed analytical assistant rather than a
general agricultural recommendation engine.

Current limitations include:

- no causal-effect estimation;
- no individualized agronomic recommendations;
- no reliable profitability calculation without complete cost and margin data;
- climate-risk responses describe surveyed community expectations rather than
  meteorological forecasts;
- analytical comparisons may remain unadjusted for crop mix and other
  confounding factors unless explicitly modeled;
- answers are limited to metrics and analytical relationships supported by the
  validated release.

---

## 8. Deferred Pre-Launch UX Requirement

The current conversation page requires users to scroll back toward the question
composer after reading later responses.

Before production launch, the interface should be redesigned into a persistent
chat-style conversation layout:

- keep the composer visible at the bottom of the viewport;
- allow the conversation history to scroll independently;
- automatically scroll to the latest turn when an answer arrives;
- keep follow-up entry immediately available after every answer;
- retain the New Conversation control;
- support responsive mobile behavior and safe-area spacing;
- optionally provide a scroll-to-latest control when the user has manually
  scrolled upward.

This is a UX requirement and does not invalidate the analytical or backend QA
results in Step 20.

---

## 9. Step 20 Decision

All required analytical, routing, conversational, API, safety, and regression
checks for Step 20 have passed.

**Decision: GO**

AgDA may proceed to the production-environment preparation stage, subject to
the remaining deployment and pre-launch UX work.