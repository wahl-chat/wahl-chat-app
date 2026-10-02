# PledgeTracker Study — Interim Analysis

**Data pulled:** 2026-09-28 from production Firestore (`wahl-chat`)
**Recruitment window:** 2026-09-17 09:41 → 2026-09-22 16:52 (Europe/Berlin)
**Randomised sample:** 265 users (139 manipulation / 126 control)
**Prepared for:** study coauthors (Vlachos group, Cambridge; Stafford, Sheffield; Frasch, Hamburg)

---

## 0. Status — recruitment has stopped

The Firestore kill switch `system_status/pledge_study` is currently `{enabled: false}`.
**No new participant has been enrolled since 2026-09-22 16:52 Berlin**, six days before
this pull. Traffic to the two study elections continued throughout (100 chat sessions on
23 Sept, 8–23/day since), so this is the switch, not an absence of users.

Consequence: the dataset below is final unless the switch is turned back on. Every number
here should be read as a closed five-day collection window, not a snapshot of an ongoing run.

| Day (Berlin) | New consent rows | Study-context sessions | Study-context visits |
|---|---|---|---|
| 09-17 | 54 | 123 | 114 |
| 09-18 | 58 | 108 | 118 |
| 09-19 | 70 | 133 | 133 |
| 09-20 | 86 | 91 | 249 |
| 09-21 | 55 | 45 | 187 |
| 09-22 | 22 | 42 | 65 |
| 09-23 → 09-28 | **0** | 156 | 151 |

---

## 1. Headline findings

1. **One candidate signal: time on site.** Users assigned to the manipulation arm stayed
   markedly longer — median 112.2s vs 65.7s, a geometric-mean ratio of ×1.64. The effect is
   small-to-modest in standardised terms (Cliff's δ = +0.153, 95% CI [+0.013, +0.292]) and
   survives a permutation test and a log-scale parametric cross-check, but **does not survive
   Holm correction** across the five primary outcomes (adjusted p = 0.157).

2. **All five other outcomes are null**, with confidence intervals that comfortably include
   zero: further questions, message turns, word count, and return visits.

3. **The study is underpowered for anything but a large effect.** With 139 vs 126 users, the
   minimum detectable difference is roughly **+17 percentage points** on a binary outcome and
   **d = 0.34** on a continuous one. The nulls are therefore *uninformative* about
   small-to-moderate effects rather than evidence of absence.

4. **The biggest design problem is exposure dilution: only 36.7% of the manipulation arm ever
   saw the PledgeTracker card** (51/139). Nearly two-thirds of the "treated" group received no
   treatment, which attenuates every ITT estimate by roughly the same factor.

5. **Nothing leaked into control.** Zero control users recorded `pledge_shown` or
   `pledge_modal_open`, in every stratum and both elections. The gate is behaving.

---

## 2. Data and definitions

### Sources

| Collection | Used for |
|---|---|
| `study_participants/{uid}` | Arm, consent answer, event log |
| `chat_sessions` (+ `messages` subcollection) | Turns, word count, return sessions |
| `page_visits` | Dwell time (`visible_ms`), active days |

### Analysis population

**Intention-to-treat: all 265 users carrying a cohort.** The arm is assigned by a
deterministic hash of the anonymous uid at the moment the consent dialog is answered —
before any outcome can occur — so this is a genuine randomised comparison. Users who never
chatted are retained and zero-filled.

Excluded: 80 users who declined before 2026-09-18, when declining carried no arm assignment
(these were never exposed to the experiment and cannot be pooled), and all `?sg=` override
rows (testers).

Two strata are reported separately throughout:

- **Group A — accepted (n=66).** Consented to the research instruments; the only users who
  ever receive the questionnaire.
- **Group B — declined but allocated (n=199).** Randomised to an arm and receive the
  corresponding product build, but are never shown the questionnaire.

Membership in A vs B is *self-selected*, not randomised. Within each group the arm is random,
so within-group contrasts are causal; A-vs-B contrasts are observational.

### Outcome operationalisation

| # | Question | Operationalisation |
|---|---|---|
| Q1 | How long does the user remain on the site? (ms) | Sum of `page_visits.visible_ms` across the user's visits to study-election pages. Visibility-gated, so background tabs do not accrue. |
| Q2 | Does the user access PledgeTracker? (Y/N) | `pledge_modal_open` event present. `pledge_shown` (card entered viewport) reported separately as passive exposure. |
| Q3 | Does the user ask further questions on topic? (Y/N) | ≥2 user message turns, i.e. at least one follow-up after the first answer. |
| Q4 | Total message turns (N) | Count of user-role message items across all the user's study-context sessions. |
| Q5 | Word count of user messages (N) | Whitespace-token count summed over the same items. |
| Q6 | Does the user return for another session? (Y/N) | **Primary:** ≥2 chat sessions containing at least one message. **Secondary:** activity on ≥2 distinct calendar days. |

### Statistical methods

scipy is not available in the analysis environment, so the tests were implemented directly
and cross-checked against each other:

- **Binary outcomes:** Fisher's exact test; risk difference with Newcombe intervals; odds
  ratio with Haldane–Anscombe correction; Cohen's *h*.
- **Continuous/count outcomes:** Mann–Whitney *U* with tie correction; Cliff's δ with a
  4,000-sample bootstrap CI; Hodges–Lehmann shift; Cohen's *d*.
- **Robustness:** 20,000-iteration permutation test on the median difference, and a *t*-test
  on `log1p`-transformed values (all dwell/count distributions are heavily right-skewed).
- **Multiplicity:** Holm–Bonferroni across the five primary ITT outcomes.

Raw-scale Cohen's *d* is reported but should be disregarded for the skewed outcomes: single
extreme users dominate the variance, which is why *d* and Cliff's δ disagree in sign on Q4/Q5.

---

## 3. Sample and randomisation checks

| | Manipulation | Control |
|---|---|---|
| **Total randomised** | 139 | 126 |
| Group A (accepted) | 38 | 28 |
| Group B (declined, allocated) | 101 | 98 |
| Berlin 2026 | 114 | 105 |
| Mecklenburg-Vorpommern 2026 | 25 | 21 |
| Declined at short ask / at consent form | 92 / 44 | 85 / 39 |

The 139:126 split is consistent with the intended 50:50 (binomial two-sided p = 0.46), and
the arms are balanced on election, consent group, and the stage at which consent was answered.
**Randomisation is working as designed.**

**Differential attrition** is mild but present and worth noting: 65.5% of the manipulation arm
chatted at least once versus 60.3% of control, and 90.6% vs 84.9% produced a dwell
measurement. Neither gap is significant, but both run in the same direction as the dwell
result, so a small part of that effect could be selection into measurement rather than
behaviour change.

**Overall activity:** 167/265 (63%) sent at least one message; 346 sessions with messages;
639 user turns; 4,798 words.

---

## 4. Results by research question

### Q1 — Time on site (ms) — **the one candidate signal**

| | Manipulation | Control |
|---|---|---|
| n | 139 | 126 |
| Median total dwell | **112.2 s** | **65.7 s** |
| Mean total dwell | 293.7 s | 246.3 s |
| p25 / p75 | 30.6 s / 287.7 s | 21.0 s / 193.1 s |
| p95 / max | 961.5 s / 9,744 s | 1,077.9 s / 4,889 s |
| Median dwell **per visit** | 109.7 s | 70.1 s |
| Visits per user (median / mean) | 1.0 / 1.22 | 1.0 / 1.16 |

**Effect:** median difference **+46.5 s**; Hodges–Lehmann shift +24.5 s; **Cliff's δ = +0.153,
95% CI [+0.013, +0.292]**; geometric-mean ratio **×1.64**; log-scale Cohen's *d* = +0.25.

**Significance:** Mann–Whitney p = 0.031; permutation p = 0.051; log-scale *t* p = 0.044.
**Holm-adjusted p = 0.157.**

**Mechanism:** the effect is *longer visits*, not *more visits* — visits per user are
essentially identical (median 1.0 in both arms), while per-visit dwell differs by ~40 s. This
is consistent with the straightforward reading that the card gives users more to read.

**By stratum:**

| Stratum | Cliff's δ [95% CI] | Median diff | Geo. ratio | p (MWU / perm) |
|---|---|---|---|---|
| All (ITT) | +0.153 [+0.013, +0.292] | +46.5 s | ×1.64 | 0.031 / 0.051 |
| B — declined | **+0.200 [+0.044, +0.355]** | +58.8 s | ×1.89 | **0.015 / 0.021** |
| A — accepted | −0.026 [−0.321, +0.273] | −19.3 s | ×0.98 | 0.856 / 0.749 |

The effect appears concentrated in group B, but a bootstrap of the difference in δ gives
+0.227 **[−0.121, +0.557]** — the interval spans zero, so **there is no evidence of a genuine
interaction**, and the apparent split is most likely the small size of group A (n=66). The
pooled estimate remains the best summary.

**Exposure-adjusted (Bloom/CACE):** with 36.7% exposure and zero control exposure, and assuming
unexposed manipulation users behave exactly like control, the effect among the actually-exposed
would be **≈ +127 s** (median-based) or **≈ +129 s** (mean-based). Treat as illustrative of the
dilution, not as an estimate to quote.

### Q2 — Does the user access PledgeTracker? (Y/N)

Control is structurally zero, so **this is not a between-arm contrast** — it is a
within-manipulation engagement funnel.

| Stratum | Arm n | Saw the card | Opened the modal | Open \| Seen [95% CI] |
|---|---|---|---|---|
| All manipulation | 139 | 51 (36.7%) | 10 (7.2%) | **19.6% [11.0, 32.5]** |
| A — accepted | 38 | 13 (34.2%) | 4 (10.5%) | 30.8% [12.7, 57.6] |
| B — declined | 101 | 38 (37.6%) | 6 (5.9%) | 15.8% [7.4, 30.4] |

Among manipulation users who chatted at all, 51/91 (56.0%) saw the card — the remainder never
scrolled it into view.

The consenter/decliner difference in open rate (30.8% vs 15.8%) is **not significant**
(Fisher p = 0.253) and is not randomised in any case. An earlier read of this gap on a smaller
sample looked more striking; it has narrowed as n grew.

### Q3 — Does the user ask further questions on topic? (Y/N)

| Stratum | Manipulation | Control | Risk difference [95% CI] | OR [95% CI] | p |
|---|---|---|---|---|---|
| All (ITT) | 55/139 (39.6%) | 49/126 (38.9%) | +0.7pp [−11.0, +12.3] | 1.03 [0.63, 1.68] | 1.000 |
| A — accepted | 13/38 (34.2%) | 14/28 (50.0%) | −15.8pp [−37.5, +7.8] | 0.53 [0.20, 1.41] | 0.217 |
| B — declined | 42/101 (41.6%) | 35/98 (35.7%) | +5.9pp [−7.6, +19.0] | 1.28 [0.72, 2.26] | 0.467 |

**Null.** The ITT point estimate is essentially exactly zero.

### Q4 — Total message turns (N)

| Stratum | Manip median / mean | Control median / mean | Cliff's δ [95% CI] | p |
|---|---|---|---|---|
| All (ITT) | 1.0 / 2.0 | 1.0 / 2.9 | +0.015 [−0.116, +0.149] | 0.830 |
| A — accepted | 1.0 / 1.6 | 1.5 / 6.2 | −0.196 [−0.471, +0.087] | 0.161 |
| B — declined | 1.0 / 2.1 | 1.0 / 2.0 | +0.083 [−0.081, +0.233] | 0.296 |

**Null.** Note the mean/median divergence: control contains the heaviest users in the study
(top turn counts 55, 36, 28 vs 14, 13, 12 in manipulation). Those few users pull the control
*mean* above manipulation while the *distribution* is indistinguishable — which is exactly why
the rank-based statistics are the ones to read here.

### Q5 — Word count of user messages (N)

| Stratum | Manip median / mean | Control median / mean | Cliff's δ [95% CI] | p |
|---|---|---|---|---|
| All (ITT) | 8 / 15.6 | 8 / 20.9 | +0.025 [−0.112, +0.164] | 0.719 |
| A — accepted | 8 / 12.6 | 13 / 47.3 | −0.207 [−0.488, +0.079] | 0.144 |
| B — declined | 8 / 16.7 | 8 / 13.4 | +0.102 [−0.048, +0.251] | 0.200 |

**Null**, with the same outlier caveat (control top word counts 321, 269, 203 vs 192, 97, 93).

### Q6 — Does the user return for another session? (Y/N)

| Stratum | Definition | Manipulation | Control | Risk difference [95% CI] | p |
|---|---|---|---|---|---|
| All (ITT) | ≥2 sessions | 38/139 (27.3%) | 33/126 (26.2%) | +1.1pp [−9.5, +11.7] | 0.890 |
| All (ITT) | ≥2 days | 14/139 (10.1%) | 8/126 (6.3%) | +3.7pp [−3.2, +10.6] | 0.373 |
| B — declined | ≥2 sessions | 32/101 (31.7%) | 22/98 (22.4%) | +9.2pp [−3.1, +21.2] | 0.154 |
| A — accepted | ≥2 sessions | 6/38 (15.8%) | 11/28 (39.3%) | −23.5pp [−43.6, −2.0] | **0.046** |

**Null overall.** The nominally significant negative result in group A **should not be
believed**, for three independent reasons:

1. **It reverses under the alternative definition.** On the calendar-day definition the same
   comparison is 13.2% vs 10.7% — a *positive* difference.
2. **It rests on a handful of heavy users.** The control session-count distribution in group A
   is `{0:9, 1:8, 2:4, 3:3, 5:1, 10:1, 11:2}` — three users with 10–11 sessions create the
   contrast. Manipulation's distribution is `{0:14, 1:18, 2:4, 4:1, 5:1}`.
3. **Multiplicity.** 18 subgroup tests were run; ~0.9 false positives at p<0.05 are expected
   by construction, and this is the only one.

### Questionnaire response (group A only)

| | Prompted | Clicked through | Rate |
|---|---|---|---|
| Manipulation | 19/38 | 6 | 32% of prompted |
| Control | 17/28 | 3 | 18% of prompted |

Nine questionnaire responses in total. Prompting is balanced by arm, as intended.

---

## 5. Effect size summary (primary ITT)

| Outcome | Effect size | 95% CI | Raw p | Holm p |
|---|---|---|---|---|
| Q1 Time on site | δ = **+0.153** | [+0.013, +0.292] | 0.031 | 0.157 |
| Q3 Further questions | h = +0.01 | RD [−11.0, +12.3] pp | 1.000 | 1.000 |
| Q4 Message turns | δ = +0.015 | [−0.116, +0.149] | 0.830 | 1.000 |
| Q5 Words sent | δ = +0.025 | [−0.112, +0.164] | 0.719 | 1.000 |
| Q6 Returns | h = +0.03 | RD [−9.5, +11.7] pp | 0.890 | 1.000 |

Q2 is omitted: with control structurally at zero it admits no between-arm effect size.

---

## 6. Robustness of the Q1 result

| Check | Result | Verdict |
|---|---|---|
| Mann–Whitney U | p = 0.031 | Nominally significant |
| Permutation test (20k, median diff) | p = 0.051 | Borderline |
| log1p *t*-test | p = 0.044, d = +0.25 | Nominally significant |
| Holm across 5 primary outcomes | p = 0.157 | **Not significant** |
| Per-visit vs more-visits | Per-visit (109.7s vs 70.1s); visit counts equal | Mechanism consistent |
| Consent-group interaction | δ difference +0.227 [−0.121, +0.557] | No interaction |
| Differential attrition | 90.6% vs 84.9% measured | Mild, same direction — partial confound |

**Reading:** a genuine but unconfirmed signal. It is consistent across three test families and
has a plausible mechanism, but it fails multiplicity correction and is partly shadowed by
differential measurement. It is the obvious candidate for a **pre-registered primary outcome**
in a confirmatory run — not a result to report as established.

---

## 7. Statistical power

At the achieved sample size (139 vs 126), α = .05 two-sided, 80% power:

| Outcome | Control baseline | Minimum detectable |
|---|---|---|
| Q3 Further questions | 38.9% | ≥56.4% in manipulation (**+17.5pp**) |
| Q6 Returns | 26.2% | ≥42.7% in manipulation (**+16.5pp**) |
| Any continuous outcome | — | **Cohen's d ≥ 0.34** |

Effects of a plausible size for a single UI element — say 3–8 percentage points — are far below
this floor. **The null results do not constrain the hypothesis.** Reaching a ±5pp detectable
difference would require roughly 1,500 users per arm.

---

## 8. Threats to validity

1. **Exposure dilution (largest issue).** 63% of the manipulation arm never saw the card. The
   ITT estimand is "being assigned a build containing PledgeTracker", not "seeing
   PledgeTracker". A confirmatory design should either guarantee exposure or pre-specify a CACE
   analysis with exposure as the compliance variable.
2. **Underpowered**, as above.
3. **Device-level, not person-level identity.** Anonymous Firebase auth means a second device or
   a cleared browser profile is a new participant. Q6 (returns) is therefore systematically
   undercounted, and any real return effect is attenuated.
4. **Dwell is best-effort client instrumentation.** `visible_ms` depends on a flush that can be
   lost on abrupt tab closure; 12% of randomised users produced no `page_visits` document at
   all, and that share differs slightly by arm.
5. **Multiplicity.** 6 outcomes × 3 strata = 18 tests. Only the Holm-corrected primary family
   should be treated as confirmatory; every subgroup result is exploratory.
6. **Two pooled elections.** Berlin supplies 219 of 265 randomised users; Mecklenburg-Vorpommern
   (46) cannot support a separate analysis. Context should enter as a covariate, not a split.
7. **Group A is self-selected.** Any A-vs-B comparison is observational. Within-group arm
   contrasts remain causal.
8. **Data provenance for publication.** Group B (199 of the 265 randomised users, and 75% of all
   PledgeTracker exposure) consists of users who *declined* the study consent. Their behavioural
   telemetry was collected as ordinary product A/B testing. Whether it can be used in a
   publication — and under what description in the methods section — is a question for the
   ethics approval rather than a statistical one, and it should be settled before these data are
   written up. The questionnaire, which is what the approval covers, reached group A only.

---

## 9. Suggested next steps

1. **Decide whether to resume.** The kill switch has been off since 22 Sept. Nothing accumulates
   while it is off, and the current sample cannot answer the research question.
2. **Fix exposure before collecting more.** Raising the 36.7% exposure rate is worth more than
   any additional sample: at current exposure, ~3 users must be randomised for every 1 who is
   actually treated.
3. **Pre-register time-on-site as the primary outcome**, with δ or the geometric-mean ratio as
   the estimand and a one-sided hypothesis, and treat the rest as secondary. This converts the
   current finding from a multiplicity casualty into a testable claim.
4. **Target ~1,520 per arm** for a ±5pp binary effect (from a 38.9% baseline), or **~250 per
   arm (~500 in total)** if time-on-site with d ≈ 0.25 is the sole primary outcome. The second
   figure is the argument for pre-registering Q1 as primary: it is a sixfold cheaper study.
5. **Settle the group-B provenance question** with the ethics committee before analysis is
   written up.

---

## Appendix — reproduction

Analysis scripts (extraction, statistics, robustness) are in the session scratchpad:
`extract.py` → `users.json` (one row per randomised user) → `analyse.py` → `results.json`.
All queries are read-only against production Firestore via the admin SDK. No production data
was modified.

Pre-2026-09-18 declines (80 users) were left without a cohort deliberately, so that users from
the period when declining meant no exposure remain distinguishable from the A/B sample.
