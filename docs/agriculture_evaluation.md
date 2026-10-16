# AgDA Agriculture Evaluation Guide

Expert review briefing and feedback worksheet | 16 October 2026 UTC

## Purpose and intended use

AgDA is a working agricultural question-answering prototype that helps people
explore evidence about Nigerian agriculture in ordinary language. It brings
selected survey statistics, saved market-price observations and saved weather
forecasts into one interface while keeping their sources and meanings separate.

This review asks an agriculture specialist to assess whether the questions,
measures and explanations are useful, correctly interpreted and responsibly
bounded. The aim is to identify improvements before broader evaluation with
farmers, extension professionals, researchers or other intended users.

### Aims and objectives

- Make supported agricultural evidence easier to explore without writing database queries.
- Explain each answer's measure, geographical scope, source and limitations.
- Support descriptive comparisons and follow-up questions without losing the original context.
- Distinguish survey findings, historical market observations and model forecasts.
- Recognize ambiguity and unsupported requests, and use feedback to improve the system.

These are design objectives. Improved farm decisions, yields, incomes or adoption
have not been established by the project's recorded technical tests.

### What has been built

The web interface connects to an analytical service with a versioned survey
release, 18 registered core measures, separately attributed market and weather
snapshots, conversational follow-ups and feedback controls. It also has internal
usage monitoring and persistence support. The survey release is `wave5_v1`, with
metric definitions version `1.0.0`.

The current answering path uses explicit interpretation rules and predefined
calculations. It has no integrated large language model. It is therefore bounded
by the questions, entities, measures and data coverage that have been implemented;
it is not an open-ended agronomy adviser.

### How an answer is produced

1. A user asks a question, and the system identifies the intended measure and scope.
2. A supported question runs against the packaged survey release or an accepted external snapshot.
3. The response presents results, source information and relevant cautions. Ambiguous or unsupported requests may receive clarification or a request to rephrase.
4. A supported core follow-up can reuse the last analytical interpretation. Starting a new conversation clears that context.

Questions do not fetch new provider data on demand. A newly retrieved snapshot
may still contain old market observations or forecast hours that no longer apply.

**Access:** [Recorded production demo](https://web-production-ba3f9.up.railway.app)
and [project repository](https://github.com/LordDonald/AgDA/tree/docs/phase29-handoff).
The demo address is recorded in the [launch record](production_launch.md);
availability must be confirmed at the review session. If it cannot be used, the
project owner can arrange the [local version](local_development.md).

## Evidence and interpretation limits

### Three distinct kinds of evidence

| Evidence | What it can describe | Essential interpretation |
| --- | --- | --- |
| Nigerian Wave 5 survey release | Crop prevalence, observed yields, commercialization, food insecurity, information access and community context | Describes the analytical sample and eligible records for each measure. It is not a current census or a forecast. |
| FEWS market snapshots | Saved Nigerian white-maize retail observations in NGN/kg and compatible market rankings | Check the market, commodity and observation date. Retrieval date does not mean today's price. |
| Open-Meteo snapshots | Saved hourly temperature, relative humidity and precipitation forecasts | Check the saved location, forecast-valid hours and missing data. Forecasts are model outputs, not measured weather. |

The survey release contains 4,715 analytical households, not 4,715 confirmed
farmers. A particular result may use a much smaller subset. Market and forecast
coverage is limited to the accepted snapshots; the interface does not silently
expand to an unrepresented place or time. External data is not automatically
joined to survey results.

### Measures that need particular care

| Measure | Meaning and boundary |
| --- | --- |
| Crop grower share | Weighted share of crop-growing households growing a crop, with household-crop pairs deduplicated. It is not land-area share or share of all households. |
| Observed yield | Unweighted median kg/ha among eligible completed-harvest records. It does not measure attainable yield, land suitability or the outcome a new farmer should expect. |
| Commercialization and selling | Commercialization is an unweighted median household-crop sales share; seller participation is weighted. Neither measure establishes profitability or total sales volume. |
| Food insecurity | A weighted mean of a descriptive 0-8 experience count. Seasonal change is post-harvest minus post-planting; it is not a calibrated severity scale or proof of a harvest effect. |
| Community climate likelihood | Reported expectations in sampled community-event records. These perceptions are not measured flood probabilities or meteorological predictions. |

Weighting varies by measure. Missing values, eligibility rules and minimum record
thresholds also affect results. Labels such as "Limited", "Adequate" and "Strong"
reflect record-count rules; they are not confidence intervals, significance
tests or proof of national representativeness. A ranking can omit groups with
too few eligible records.

The review should examine whether cross-crop yield comparisons make agronomic
sense, whether the stated denominator fits the question, and whether uncertainty
is communicated clearly. Descriptive differences do not establish causation.
AgDA does not provide individual planting prescriptions or complete profit
estimates.

Definitions and provenance are traceable through the
[release manifest](../data/releases/wave5_v1/release_manifest.json),
[household/table metadata](../data/releases/wave5_v1/metadata/processed_data_manifest.csv),
[metric catalog](../data/releases/wave5_v1/metrics/analytical_metric_catalog.parquet),
[answer policies](../data/releases/wave5_v1/metrics/analytical_answer_policy.parquet)
and [calculation implementation](../packages/analytics/executor.py). The release
build date is not the survey fieldwork date. Confirm the original survey's
sampling design, fieldwork dates and variable documentation before research use
or population-level claims.

## Guided review of the core application

Allow about 30-45 minutes for an initial review; independent numerical checks may
need a separate session. Record the date, environment and release shown in the
answer. Use synthetic, non-sensitive questions: questions and feedback may be
stored for analysis. There is no need to access the internal dashboard.

Start a new conversation for each row below except the explicitly paired
follow-up. The expected behaviors come from the project's
[curated question bank](../tests/qa/user_question_bank.py). They are review targets,
not claims that these examples were newly executed for this guide. Inspect the
actual answer rather than assuming it matches the target.

| Question to try | What to assess |
| --- | --- |
| What crops do people farm most in Kaduna? | Crop grower share within the analytical sample; correct place and denominator. |
| Which states have the highest yields for rice? | Observed median completed-harvest yield, kg/ha and eligible records; no suitability recommendation. |
| How much maize do farmers sell? | Commercialization percentage rather than tonnes, revenue or profit. Is that interpretation clear to a reader? |
| Is food security better after harvest? | Descriptive seasonal change in the experience count, with the direction and limits explained. |
| How risky is flooding in the North West? | Community-reported expectations, clearly separated from physical flood risk or a forecast. |
| Which states have the highest grower share for rice? Then: What about Kaduna? | The second turn retains rice and grower share, changes the location, and gives a coherent scoped answer. |
| Which state looks strongest for rice? | Clarification of what "strongest" means, rather than an invented combined ranking. |
| Does extension improve yield? | Reframing of the causal claim; an association must not be presented as an effect. |
| What is the most profitable crop? | An explicit unsupported response because complete profitability is outside the implemented scope. |
| Should I farm maize in Katsina? | A boundary on personal planting advice, with a suitable reframe. |

After the paired follow-up, use **New conversation** and verify that the next
question is not interpreted using the prior rice context. Review the readability
of the answer, evidence and any chart on the intended phone or computer.

Add two or three questions in your own words, including one genuine information
need from your field. Record the intended meaning before submitting. Distinguish
an unsupported but useful future capability from an incorrect answer to a
supported question. A well-explained refusal can be the correct result.

For at least one numerical answer, ask the project owner for an independent
calculation using the same release, exclusions, denominator and weighting.
Compare both the number and its interpretation. Repeating the same application
query is not an independent numerical check; mark accuracy **not assessed** if
no suitable reference calculation is available.

## External data and existing validation

### Optional market and weather review

External snapshots must be available for these checks. Record the saved location,
observation or forecast time, retrieval time, units and snapshot version where
displayed. The project owner can supply the exact snapshot identifier for
reproduction. Do not assume the reviewer's own location is selected.
If data is unavailable or outside coverage, record that separately from a wrong
calculation.

| Question to try | What to assess |
| --- | --- |
| Which market has the highest maize price? | Ranking only of compatible saved white-maize retail observations; market, period and NGN/kg must remain clear. |
| What is the forecast temperature? | The saved location and forecast-valid hours are clear; this must not be described as an observation or an unrestricted current forecast. |
| How much rain is forecast? | Units, valid period and missing-hour coverage are explicit. A partial sum is not a complete forecast total; missing values are not proof of no rain. |
| Compare maize yields and market price. | Reframing rather than an unsupported combination of survey and external-source evidence. |

Natural-language external questions use bounded saved coverage. More precise
market and time selectors are available through the separate technical query
interface; they are not all promises of conversational support. The
[external-query contract](phase28_external_capabilities.md) describes those
selectors, missing data and source/time semantics.

### What has been demonstrated

The [Phase 29 closure record](phase29_closure.md) reports 50/50 backend regression
scripts, 23/23 curated question cases, five scripted manual QA journeys and
passing frontend/CI checks. Four staging browser journeys covered submission,
follow-up, dashboard use and zoom/reset. A synthetic conversation and feedback
sequence survived an API redeployment. External checks compared selected results
with their saved snapshots.

These are engineering checks. The 23 question cases are not 23 participants.
They do not establish independent agricultural accuracy, forecast skill, user
comprehension, farmer benefit or a representative usability study. Dated hosted
checks also do not establish continuous or present availability.

The [preservation record](hosted_data_preservation.md) documents six sets that
passed artifact checks, together with Redis coverage limitations. It does not
establish a completed restoration exercise. Preservation is operational evidence,
not validation of the agricultural conclusions.

### What this expert review should inform

The most useful outcomes are corrections to misleading interpretations,
priorities for missing but valuable agricultural questions, clearer explanations
and a decision about readiness for a small supervised user study. Further work
should independently verify selected calculations and survey provenance, test
understanding with intended users, and assess language, device and accessibility
needs. Claims about improved decisions, yields or incomes would require separate
outcome studies. These are proposed next steps, not completed achievements.

## Feedback worksheet

### Record one row per attempted question

For each attempt, record the question and preceding turns; intended meaning;
actual answer or screenshot; source, version and time information; expected
versus actual outcome; and the reason for any concern. Include the comparison
method for any independently checked number. Avoid names, private farm records
or other sensitive information.

Use these outcome labels: **supported as scoped**, **needs revision**,
**unsupported as expected**, **incorrect or misleading**, or **could not assess**.
Keep unavailable service/data and unperformed checks visible in the final tally.

### Suggested review scale

Use **0 = material problem**, **1 = partly adequate**, **2 = adequate**, or
**N/A = not assessed**. This is a proposed discussion aid, not a validated research
instrument. Do not treat unassessed items as passes or average away a seriously
misleading answer.

| Dimension | Review question | Rating |
| --- | --- | --- |
| Agricultural relevance | Is the information useful for the stated agricultural need? | ____ |
| Interpretation | Are crop, place, time, measure and intended comparison preserved? | ____ |
| Numerical and methodological accuracy | Do independently checked calculations, units, denominators and weighting agree? | ____ |
| Evidence and limits | Can the reader distinguish sources, dates, uncertainty and permitted inference? | ____ |
| Communication | Can an intended reader explain the answer and its limits in their own words? | ____ |
| Boundaries | Are ambiguous, causal, advisory and unavailable requests handled appropriately? | ____ |
| Interaction | Are follow-ups, reset, reading and feedback understandable on the chosen device? | ____ |

### Overall response to return to the project owner

- **Reviewer role or anonymous ID, review date, environment and known revision:**
- **Questions attempted; answered, appropriately unsupported, problematic and unassessed counts:**
- **Most useful capability and why:**
- **Most important incorrect or potentially misleading answer, with its question and evidence:**
- **Three priority improvements, distinguishing essential corrections from new capabilities:**
- **Recommendation:** ready for a small supervised user study / revise before further evaluation / more evidence needed.

Return the completed notes and any annotated screenshots directly to the project
owner. In-app feedback can supplement the review, but the detailed rationale is
especially valuable. This guide requests expert appraisal; it does not imply
endorsement or certification by the reviewer.

For additional detail, see the [repository overview](../README.md),
[architecture](architecture.md), [documentation index](README.md) and
[local setup guide](local_development.md).
