# Card-Content Charter Spec (Draft v5 — final pre-implementation)

**Status:** design frozen, ready to implement.
**Goal:** eliminate cross-topic content overlap *prescriptively* — by specifying what each card owns — instead of detecting duplication after the fact. Companion to `course_blueprints.py` (which cards, in what order) and `narration/contracts.py` (how a card is framed). This adds the missing layer: **what content each card owns, and what it must defer to a sibling.**

**v5 changelog (from review 4):** split `PROCEDURE` → `PROCEDURE_OVERVIEW` (a background's high-level "name the method/approach") vs `PROCEDURE` (the full steps, owned by `method_process`), so a `background` card never competes with the real procedure card for one slot. Explicit intra-topic tie-break ("first matching card by card-plan order"). A2 updated; new test A18 (background vs method_process). (`STRUCTURE` split considered but deferred — `scope_note` covers it.)
**v4 changelog (from review 3):** (1) A1 reworded — only slots with a planned carrier must resolve once; the taxonomy is not a per-path checklist. (2) "never drops content" scoped to content a planned card *declares*. (3) `SlotOwner.friendly_label` for readable exclude pointers. (4) `CardCharter.family` (stable rollout key, so card-type aliases like `purpose_context`/`background` map to one family). (5) new test A17 (summary non-owning). (6) note: use `fallback_expresses` sparingly.
**v3 changelog (from review 2):** (1) **card-aware ownership** — a slot owner is valid only if the topic actually has a *planned card* able to express it (a topic can exist but have its slot-bearing card pruned); `resolve_ownership` now takes the card plans. (2) **Explicit fallback precedence** — a card that `expresses` a slot beats one that only `fallback_expresses` it, so a `background` never becomes the glossary when a later `definition` card exists. (3) **A1 reworded** — equal-priority role-owners are legal; the real invariant is "each owned slot resolves to exactly one (topic, card) per path." (4) New `scope_note` (card-level negative boundary, distinct from slot-level `exclude`). (5) **Summary/review cards are non-owning** (§6.9 + MUST-NOT). (6) New tests A15 (card-aware fallback) + A16 (background ≠ glossary).
**v2 changelog:** `fallback_expresses`; `DEFINE_GLOBAL` vs `DEFINE_LOCAL`; `PRECONDITION`/`COMMON_ERROR`/`CHECK` slots; row-based rollout; `ResolvedCardCharter` prose directives + A11–A14.

Motivating defect (observed live, "completing the square", 2 topics `concept_intuition` + `math_formula_method`): both opened with an identical **"What is Completing the Square?"** card, both defined the same terms, both ended with the same practice (x²+8x+15).

---

## 1. The core question: how does the system know what a card should differ on?

A static "background@math_formula_method excludes motivation" rule is not enough, because whether motivation belongs elsewhere depends on **whether a `concept_intuition` topic — and a card in it that actually carries the intuition — exists in this path**. Differentiation is **two layers**:

1. **Content ownership (static, by topic-type ROLE).** Every atomic unit of content — a *slot* — has a primary owner topic type. `INTUIT` → `concept_intuition`; `PROCEDURE` → the method/walkthrough topics; `DEFINE_GLOBAL` → `terminology_components`. The *difference* between the same card type in two topics is the difference in the slots their roles own.
2. **Ownership resolution (dynamic, per path AND per card plan).** At generation time the resolver looks at the **actual sibling topics and their planned cards** and picks, for each slot, the single owning card — then every non-owner that would render the slot `excludes` it (with a pointer to the owner). If nobody can own a slot some card needs, a fallback carrier renders it, so content is relocated, never dropped.

So: **the charter encodes roles; the resolver grounds them against the real path and its real cards.**

---

## 2. Content slots (the atomic units that can overlap)

| Slot | Meaning | Notes |
|---|---|---|
| `ORIENT` | Path-level: what you'll be able to do, roadmap | |
| `MOTIVATE` | Why / when you'd reach for this | |
| `INTUIT` | The one-sentence mental model | |
| `DEFINE_GLOBAL` | Formal definitions of terms — the glossary | owned; single home per path |
| `DEFINE_LOCAL` | Minimal term meaning needed *inside* a card ("where b is the linear coefficient") | **UNIVERSAL** — never owned, never excluded |
| `STRUCTURE` | Anatomy: inputs, outputs, parts, notation | |
| `PRECONDITION` | When the method applies; assumptions, input constraints | distinct from `MOTIVATE` (why) — formal applicability |
| `PROCEDURE_OVERVIEW` | The method named at a high level ("the approach in one breath") | a `background`'s share — never the full steps |
| `PROCEDURE` | The full method / steps / trace | owned by `method_process` — distinct slot from the overview |
| `DERIVE` | *Why* the method works (justification) | |
| `INSTANCE` | A fully worked example | |
| `EDGE` | Legitimate degenerate / boundary cases | |
| `COMMON_ERROR` | A mistake **learners** commonly make + how to avoid | ≠ `EDGE` |
| `CHECK` | How to **verify** the result | e.g. expand the vertex form back to the original |
| `PRACTICE` | Learner attempts a problem | |
| `COMPARE` | Contrast with alternatives | |
| `APPLY` | Use on a real problem | |

Every **owned** slot (all but `DEFINE_LOCAL`) resolves to **exactly one card** per path (§5). `DEFINE_LOCAL` is the pressure-release valve so single-ownership never makes a card unreadable.

---

## 3. Typed schema

```python
Slot = Literal["ORIENT","MOTIVATE","INTUIT","DEFINE_GLOBAL","DEFINE_LOCAL","STRUCTURE",
               "PRECONDITION","PROCEDURE_OVERVIEW","PROCEDURE","DERIVE","INSTANCE","EDGE",
               "COMMON_ERROR","CHECK","PRACTICE","COMPARE","APPLY"]

UNIVERSAL_SLOTS: frozenset[Slot] = frozenset({"DEFINE_LOCAL"})   # never owned / never excluded

@dataclass(frozen=True)
class TopicRole:
    topic_type: str
    owns: tuple[Slot, ...]          # slots this topic type is the PRIMARY owner of
    priority: int                   # tie-break rank (higher wins a contested slot)

@dataclass(frozen=True)
class CardCharter:
    topic_type: str
    card_type: str
    family: str                     # stable rollout key (e.g. "background"); card-type ALIASES share one family
    job: str                        # one-line learner-facing intent (injected verbatim)
    expresses: tuple[Slot, ...] = ()          # PRIMARY slots this card renders — owner-resolved
    fallback_expresses: tuple[Slot, ...] = () # rendered ONLY when nothing higher-precedence owns them
    include: tuple[str, ...] = ()   # extra concrete elements (free text)
    exclude: tuple[str, ...] = ()   # STATIC slot-independent exclusions (always)
    scope_note: str = ""            # card-level negative boundary, learner-facing (≠ slot exclude)
    handoff: str = ""               # what a later card/topic covers, so this one doesn't preempt it

@dataclass(frozen=True)
class SlotDirective:                # slot -> the prose the resolver emits (never abstract slots)
    include: str                    # "Give the one-sentence mental model."
    exclude_template: str           # "Do NOT explain the intuition — the {owner} topic covers it."

@dataclass(frozen=True)
class SlotOwner:
    topic_order: int
    topic_type: str
    card_type: str                  # the SPECIFIC card that owns the slot
    tier: int                       # 1 role-owner · 2 expresses · 3 fallback  (debug/telemetry)
    friendly_label: str = ""        # readable owner name for exclude pointers ("the intuition topic")

@dataclass(frozen=True)
class ResolvedCardCharter:          # the resolver's OUTPUT — prompt builder just concatenates
    topic_type: str
    card_type: str
    job: str
    include_slots: tuple[Slot, ...]
    exclude_slots: tuple[Slot, ...]
    include_directives: tuple[str, ...]   # already human-readable
    exclude_directives: tuple[str, ...]
    scope_note: str
    handoff: str
```

Lookup: `charter_for(topic_type, card_type)` → `(topic_type, card_type)` cell → `card_type` default → `None`. **Sparse:** only author cells where the job varies by topic type or overlap is a real risk.

**`expresses` vs `fallback_expresses`:** `expresses` = the card's primary slots (owner-resolved; excluded if another card owns them). `fallback_expresses` = secondary slots the card renders **only when nothing that `expresses` them is present** — so a self-contained path stays complete. Precedence is enforced in §5. **Use `fallback_expresses` sparingly** — only for self-containment of early/context cards (e.g. a method `background`); dedicated teaching cards use plain `expresses`, so fallback never becomes a backdoor for opportunistic ownership.

---

## 4. Topic-type content ownership

`priority` breaks a contested slot among role-owners.

| topic_type | owns (slots) | priority |
|---|---|---|
| `study_path_introduction` | `ORIENT` | 10 |
| `concept_intuition` | `INTUIT`, `MOTIVATE` | 30 |
| `terminology_components` | `DEFINE_GLOBAL`, `STRUCTURE` | 40 |
| `math_formula_method` | `PROCEDURE_OVERVIEW`, `PROCEDURE`, `DERIVE`, `INSTANCE`, `EDGE`, `COMMON_ERROR`, `CHECK`, `PRECONDITION`, `PRACTICE` | 60 |
| `process_walkthrough` | `PROCEDURE_OVERVIEW`, `PROCEDURE`, `INSTANCE`, `EDGE`, `COMMON_ERROR`, `CHECK`, `PRECONDITION`, `PRACTICE` | 60 |
| `algorithm_walkthrough` | `PROCEDURE_OVERVIEW`, `PROCEDURE`, `INSTANCE`, `EDGE`, `PRECONDITION`, `CHECK` | 60 |
| `data_structure_operation` | `STRUCTURE`, `PROCEDURE_OVERVIEW`, `PROCEDURE`, `INSTANCE`, `PRECONDITION` | 55 |
| `coding_implementation` | `PROCEDURE_OVERVIEW`, `PROCEDURE`, `INSTANCE`, `COMMON_ERROR`, `CHECK`, `PRACTICE` | 65 |
| `proof_reasoning` | `DERIVE`, `PROCEDURE`, `CHECK` | 60 |
| `science_mechanism` | `INTUIT`, `PROCEDURE_OVERVIEW`, `PROCEDURE`, `INSTANCE`, `PRECONDITION` | 60 |
| `compare_distinguish` | `COMPARE` | 50 |
| `problem_solving_application` | `APPLY`, `PRACTICE`, `COMMON_ERROR`, `CHECK` | 70 |

Equal-priority owners (e.g. several topic types own `PROCEDURE`) are legal — they're normally mutually exclusive for one concept, and §5 still yields a single owner (card-awareness + earliest order).

---

## 5. Ownership resolution (runtime, per path — CARD-AWARE)

```python
def resolve_ownership(
    topics: list[TopicPlan],                     # ordered: topic_type + order_index
    card_plans_by_topic: dict[str, list[str]],   # topic -> its planned card_types (from the blueprint)
) -> dict[Slot, SlotOwner]:
```

For each **owned** slot, pick the single owning `(topic, card)` by **precedence tiers** — and a topic only qualifies if it has a **planned card whose charter can render the slot** (card-aware, so a pruned card can't hold phantom ownership):

1. **Role-owner:** topics whose *role* `owns` the slot **and** have a planned card that `expresses` (or, if none, `fallback_expresses`) it → winner = highest `priority`, ties earliest `order_index`; owning card = **the first matching card in that topic's card-plan order**. (Intra-topic ties are rare because slots are split where they'd collide — e.g. a `background` expresses `PROCEDURE_OVERVIEW` while `method_process` expresses `PROCEDURE`, so they never contend for one slot.)
2. **Any `expresses` card:** if tier 1 is empty, topics with a planned card that `expresses` the slot → earliest order.
3. **Any `fallback_expresses` card:** if tier 2 is empty, topics with a planned card that `fallback_expresses` the slot → earliest order.
4. **Unowned:** the slot is rendered nowhere.

`DEFINE_LOCAL` is never resolved (universal). **Precedence guarantee:** a card that `expresses` a slot (tiers 1–2) always beats one that only `fallback_expresses` it (tier 3) — so a method `background` (fallback DEFINE_GLOBAL) never owns the glossary when a later `definition` card `expresses` it.

Then `resolve_card(charter, ownership, this_topic, this_card) -> ResolvedCardCharter`:
- For `slot in expresses ∪ fallback_expresses`, let `owner = ownership.get(slot)`:
  - `owner == (this_topic, this_card)` → **include** (+ `SLOT_DIRECTIVES[slot].include`). (A card's *fired* fallback slot — one nobody else owns — resolves to itself and is included here.)
  - owner is **another** card → **exclude** (+ `exclude_template.format(owner=<friendly name>)`), whether the slot is in `expresses` **or** `fallback_expresses`. The negative directive is the point: a method `background` whose `INTUIT` is owned by a concept sibling must be *told* "do not re-explain what X is" (A4), not merely left silent.
  - `owner is None` (no card `expresses` it **and** no card `fallback_expresses` it) → the slot is **unresolved** and rendered nowhere. (If any card expressed it, tiers 1–2 chose an owner; if only a fallback carrier existed, tier 3 chose it — so `None` here means genuinely no carrier, consistent with A1.)
- Always append the `DEFINE_LOCAL` allowance directive.
- Copy `job`, static `include`/`exclude`, `scope_note`, `handoff`.

Same charters + card plans, different sibling sets → different effective directives. **This is the mechanism** that makes one card type differ correctly across topics, and the card-awareness is what stops content vanishing when the "owning" topic's card was pruned.

---

## 6. Charters for the overlap-prone card types

### 6.1 `background` / `purpose_context`
| topic_type | job | expresses | fallback_expresses |
|---|---|---|---|
| `study_path_introduction` | Orient the path: what you'll do, why it matters | `ORIENT` | — |
| `concept_intuition` | The mental model + when you'd reach for this | `INTUIT`, `MOTIVATE` | — |
| `math_formula_method` / `process_walkthrough` | Name the method, its inputs/output, the goal | `PROCEDURE_OVERVIEW`, `STRUCTURE` | `INTUIT`, `MOTIVATE`, `DEFINE_GLOBAL` |
| `algorithm_walkthrough` | The problem it solves + high-level approach | `PROCEDURE_OVERVIEW` | `INTUIT`, `MOTIVATE` |
| `coding_implementation` | The problem the code solves + the approach | `PROCEDURE_OVERVIEW` | `MOTIVATE` |

`scope_note` on method backgrounds: *"Name the method and goal only; do not teach the full procedure or a glossary."* The background expresses `PROCEDURE_OVERVIEW` (the approach in one breath), never `PROCEDURE` — `method_process` (§6.3) owns the full steps, so the two cards never contend (A18). Per §5 precedence, the `DEFINE_GLOBAL` fallback fires **only if** neither a `terminology_components` topic nor a later `definition` card in this topic `expresses` it (A16).

### 6.2 `definition` / `components_terms`
| topic_type | job | expresses |
|---|---|---|
| `terminology_components` | Define every term the path uses | `DEFINE_GLOBAL`, `STRUCTURE` |
| any other with a definition card | Own `DEFINE_GLOBAL` only if the resolved owner; else name only what THIS card needs | `DEFINE_GLOBAL`, +always `DEFINE_LOCAL` |

With a terminology sibling, others `exclude DEFINE_GLOBAL` (+ pointer) but **keep `DEFINE_LOCAL`**. → kills the duplicate glossary without under-explaining.

### 6.3 `method_process` / `formula` / `formula_breakdown`
| topic_type | job | expresses | static exclude |
|---|---|---|---|
| `math_formula_method` | The procedure + the formula that drives it, with its preconditions | `PROCEDURE`, `DERIVE`, `PRECONDITION` | motivation; full glossary |
| `process_walkthrough` | The ordered steps | `PROCEDURE`, `PRECONDITION` | motivation |
| `proof_reasoning` | The reasoning chain | `DERIVE`, `PROCEDURE`, `CHECK` | — |

### 6.4 `edge_case` vs `common_mistake` (two distinct slots)
| card_type | owner | expresses | note |
|---|---|---|---|
| `edge_case` | `PROCEDURE`-owner | `EDGE` | full set of boundary cases, treated correctly |
| `common_mistake` / misconception | `PROCEDURE`- or `APPLY`-owner | `COMMON_ERROR` | learner errors, not boundaries |
| (in `concept_intuition`) | — | may *name* one boundary as intuition | no full treatment |

`EDGE` single-ownership **fixes the observed x²+4 divergence**. `COMMON_ERROR` is a separate slot so "forgetting to halve b before squaring" isn't conflated with the legitimate no-linear-term boundary.

### 6.5 `worked_example`
`PROCEDURE`-owner, `expresses INSTANCE`. If >1 topic carries worked examples, the resolver **tags instances** so a later topic can't repeat an earlier one's numbers.

### 6.6 `quick_practice` / `practice`
`problem_solving_application` → `APPLY`,`PRACTICE`; `PROCEDURE`-owner → `PRACTICE`. Rules: (a) **distinct** problems across topics (tagged like §6.5); (b) **scope-matched** to what the worked examples demonstrated (closes the a≠1 gap).

### 6.7 `check` / verify
`PROCEDURE`-owner, `expresses CHECK`. Own "how to confirm the answer" (expand `(x+h)²+k` back to the original). Own card or the worked example's closing move — the slot ensures one owner.

### 6.8 `roadmap`
`study_path_introduction` only; `expresses ORIENT`.

### 6.9 `summary` / `review` / `takeaway` — **NON-OWNING**
A summary/review/recap card owns **no** slot. It may **compress** prior owned content (a one-line reminder) but MUST NOT introduce or re-teach a new `DEFINE_*`, `INSTANCE`, `PROCEDURE`, `EDGE`, or `DERIVE`. It gets no `expresses`; its charter carries only a `job` + a `scope_note` ("compress what was taught; introduce nothing new"). This closes the review-card overlap hole without adding an ownership dimension.

---

## 7. `main_concept` / header charter (folded in)

Per card, `main_concept` = the card's **concrete claim** drawn from its owned slot, never an instructor objective ("Half the linear coefficient, square it, add and subtract," not "Follow the sequence of steps"). `learning_goal` (if kept) states the *capability* and must differ. A header matching an instructor-voice pattern (`Detail…`, `Understand…`, `Introduce…`, `Establish…`) is non-conformant (A9).

---

## 8. Prompt-injection surface

- Inject at the **card-plan layer** — `lean_lesson_prompt._format_card_plan` / `_format_combined_card_plan`. Append the `ResolvedCardCharter`'s `job` + `include_directives` + `exclude_directives` + `scope_note` + `handoff`, co-located with that card. **The builder concatenates prose only — it never sees slots.** Same pattern as the shipped `process_scaffold_directive`.
- The **resolver** runs once per topic with the full sibling list **and their planned card sets** (`topic.study_path.topics` + the blueprint card sequences, both already available where `build_scope_boundaries_from_siblings` runs).

---

## 9. Acceptance-test table

Deterministic (offline) unless marked live. A11–A16 assert on the **built prompt / `ResolvedCardCharter`**.

| # | Given | Assert |
|---|---|---|
| A1 | any concrete path + its card plans | each owned slot **that ≥1 active planned card `expresses`/`fallback_expresses`** resolves to **exactly one** `(topic, card)`; slots with no planned carrier stay **unresolved** (the taxonomy is not a per-path checklist); `DEFINE_LOCAL` never resolved. (Equal-priority role-owners allowed; single owner via card-awareness + earliest order.) |
| A2 | `charter_for(math_formula_method, background)` | expresses `PROCEDURE_OVERVIEW`,`STRUCTURE` (**not** `PROCEDURE`); `fallback_expresses` has `INTUIT`,`MOTIVATE`,`DEFINE_GLOBAL` |
| A3 | `charter_for(concept_intuition, background)` | expresses `INTUIT`,`MOTIVATE` |
| A4 | resolve [intro, concept_intuition(bg), math_formula_method(bg)] | `INTUIT` owner = concept bg; method bg `INTUIT` ∈ exclude_slots |
| A5 | resolve [intro, math_formula_method] (no concept) | method bg fallback fires → `INTUIT`,`MOTIVATE` ∈ include_slots; `DEFINE_GLOBAL` included **only if** no later definition card |
| A6 | two topics carry `definition`, no terminology sibling | `DEFINE_GLOBAL` owned by earliest; later excludes it but keeps `DEFINE_LOCAL` |
| A7 | two topics carry `edge_case` | `EDGE` owned by one; other excludes / has no edge card |
| A8 | built prompt, method topic | contains the method-background directive, not the intuition one |
| A9 | header conformance | `main_concept` = "Detail the foundational knowledge" is rejected |
| A11 | built method prompt, concept sibling present | contains exclude directive ~ "do not re-explain what X is — the intuition topic covers it" |
| A12 | built method prompt, NO concept sibling | contains a fallback **intuition** include directive |
| A13 | formula card, terminology sibling present | include has the `DEFINE_LOCAL` allowance; exclude has the `DEFINE_GLOBAL`→glossary pointer |
| A14 | second `practice` card in a path | directives contain "distinct from the earlier practice problem" |
| **A15** | concept topic present but its card plan has **no** card expressing `INTUIT` (pruned) | tier-3 fallback → method bg owns `INTUIT`; it IS in include (content not dropped) |
| **A16** | no terminology topic, method topic has a later `definition` card | method bg does **not** own `DEFINE_GLOBAL` (tier-2 definition card wins); the definition card owns it |
| **A17** | a `summary`/`review`/`takeaway` card | resolves **no** owned slots; prompt contains "compress what was taught; introduce nothing new" |
| **A18** | a method topic with both `background` + `method_process` | `background` owns `PROCEDURE_OVERVIEW` only; `method_process` owns `PROCEDURE`; no slot is double-owned; background prompt says not to teach the full procedure |
| A10 (live) | regenerate `completing_square_2topic` with charters on | "What is X?" once; terms defined once; practice problems distinct |

## 10. Fixtures

- **`completing_square_2topic`** — `concept_intuition` + `math_formula_method`, the exact overlap. Primary regression fixture.
- **`completing_square_no_concept`** — `intro` + `math_formula_method` only → exercises `fallback_expresses`.
- **`concept_topic_pruned`** — a concept topic whose intuition card was pruned → exercises A15 card-aware fallback.
- **`bst_coding`** — coding path (walkthrough + implementation) → confirms coding cards partition and nothing math leaks.

## 11. Implementation surface + MUST-NOT

**New:** `app/core/card_charters.py` (`Slot`, `TopicRole`, `CardCharter`, `SlotDirective`, `SlotOwner`, `ResolvedCardCharter`, `TOPIC_ROLES`, `CARD_CHARTERS`, `SLOT_DIRECTIVES`, `resolve_ownership(topics, card_plans_by_topic)`, `resolve_card(...)`, `charter_for(...)`, `active_charter_families()`). Injection in `lean_lesson_prompt`. Tests `test_card_charters.py`.

**MUST-NOT:**
- Not the source of truth for card **sequence** — `course_blueprints.py` stays that.
- Governs **scope/content ownership only** — **not correctness** (adapter-grounding does that).
- **No runtime validator** for overlap — prompt directives prevent it; only header conformance (A9) is a lightweight check.
- The resolver **never drops content a planned card declares** (via `expresses`/`fallback_expresses`) — if a needed slot has no valid primary owner, the highest-precedence fallback carrier renders it. (A slot no card carries simply doesn't appear — the taxonomy is not a checklist.) Ownership is **card-aware** so a pruned card holds no phantom ownership.
- **Summary/review cards own nothing** and introduce no new owned content (§6.9).
- The prompt builder **never interprets slots** — it concatenates the resolver's prose.

## 12. Rollout

- **Row-based flag:** `AZALEA_CARD_CHARTERS` = comma-separated active families (`background`, `definition`, `practice`, … or `all`); unset/empty = off. A charter applies only if its **`family`** is in the active set — matching on `family` (a stable name), not the raw `card_type`, so aliases like `purpose_context`/`background` or `quick_practice`/`practice` map to one switch. **Startup log line** reports the active set (so it can't silently no-op like the dark flags).
- **Build order** (each step independently tested):
  1. `Slot`/`TopicRole`/`CardCharter`/`SlotDirective`/`SlotOwner`/`ResolvedCardCharter` + `charter_for`.
  2. Row-flag parsing (`active_charter_families()`).
  3. `resolve_ownership` (card-aware) + `resolve_card`.
  4. Seed the `background` row only.
  5. Deterministic tests A1–A5, A8, A11, A12, A15, A16, A18.
  6. Inject resolved prose into `_format_card_plan`.
  7. Live-run `completing_square_2topic` (A10).
  8. Add `definition` (A6, A13); then `practice` uniqueness (A14); then `edge_case`/`common_mistake` (A7); then `check`; then summary non-owning (§6.9).
