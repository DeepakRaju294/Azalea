from __future__ import annotations

from typing import TypedDict

# STAGE_RULES defines what belongs inside a selected card. It does not
# decide which cards are generated. Card selection is controlled by
# course_blueprints.py and TopicScopeContract. If a stage rule asks for
# prerequisite/context content, it must still obey TopicScopeContract:
# do not expand prerequisites beyond their assigned treatment.


class CardStageRule(TypedDict):
    content: list[str]
    visual: str
    microcheck: str
    notes: list[str]


STAGE_RULES: dict[str, dict[str, CardStageRule]] = {

    # ─── Concept + Intuition ─────────────────────────────────────────────────
    "concept_intuition": {
        "context_first_impression": {
            "content": [
                "what the concept is used for",
                "why it matters or where it fits in the bigger picture",
                "what to picture or expect before details arrive",
            ],
            "visual": "full structure or process overview as a first-impression diagram",
            "microcheck": "",
            "notes": [],
        },
        "definition": {
            "content": [
                "accurate, precise definition",
                "necessary conditions or constraints",
                "only the precision needed for correctness — no overloading",
            ],
            "visual": "labeled definition diagram if the concept has a natural spatial form",
            "microcheck": "check a key condition or critical detail from the definition",
            "notes": [],
        },
        "components_parts": {
            "content": [
                "each important part of the concept",
                "role of each part",
                "structural edge cases or variants that are part of the concept",
            ],
            "visual": "component diagram — each major part labeled with role",
            "microcheck": "check the role of one part or the difference between two parts",
            "notes": ["may span multiple cards when components are numerous"],
        },
        "how_it_works": {
            "content": [
                "every meaningful step in the mechanism or process",
                "normal-case behavior at each step",
                "edge-case behavior where behavior changes",
            ],
            "visual": "full process visual or one visual per step when state/progression matters",
            "microcheck": "check after each main idea or step",
            "notes": ["may span multiple cards"],
        },
        "comprehensive_example": {
            "content": [
                "for each step: current state, action taken, reason for the action, result, reason the result follows",
                "normal cases and important edge cases",
                "adaptive feedback when the learner answers incorrectly",
            ],
            "visual": "visual per step or full visual with progression highlights",
            "microcheck": "ask what happens next or why a step happens before revealing the answer",
            "notes": [
                "each important step usually gets its own card",
                "use multiple examples only if a single one would be too cluttered",
            ],
        },
        "practice": {
            "content": [
                "apply the concept to a scenario",
                "include normal cases and important edge cases",
                "adaptive feedback that clarifies misconceptions",
            ],
            "visual": "if a visual aids the scenario",
            "microcheck": "",
            "notes": [],
        },
    },

    # ─── Algorithm Walkthrough ────────────────────────────────────────────────
    "algorithm_walkthrough": {
        "context_first_impression": {
            "content": [
                "what the algorithm does and what kind of problem it solves",
                "high-level idea — what it does differently from brute force",
                "when and why this algorithm is chosen",
            ],
            "visual": "high-level diagram of the algorithm's approach (graph/array/tree as appropriate)",
            "microcheck": "",
            "notes": [],
        },
        "algorithm_rule_main_idea": {
            "content": [
                "the core decision rule the algorithm makes at each step",
                "why this rule is correct — the invariant it maintains",
                "what it avoids doing and why",
            ],
            "visual": "",
            "microcheck": "check the core decision rule or invariant",
            "notes": [],
        },
        "state_components": {
            "content": [
                "every piece of state the algorithm maintains: frontier/queue/stack/table/visited/results",
                "initial state at start",
                "stopping condition and what it means",
            ],
            "visual": "labeled state diagram showing all components at step 0",
            "microcheck": "check which state component does what",
            "notes": [],
        },
        "how_it_works": {
            "content": [
                "every meaningful step in one pass of the algorithm",
                "what state changes at each step and why",
                "how the stopping condition is checked",
            ],
            "visual": "full process visual — highlight state changes per step",
            "microcheck": "check what changes after a step or which state component is updated",
            "notes": ["may span multiple cards for complex algorithms"],
        },
        "comprehensive_walkthrough_example": {
            "content": [
                "for each step: current state of all components, decision made, reason for decision, new state",
                "show a tricky step — where the algorithm makes a non-obvious choice",
                "cover normal progress and at least one edge transition",
            ],
            "visual": "same base visual per step with progression highlights — node/edge highlights for graphs, array pointer positions for arrays",
            "microcheck": "ask what the algorithm does next or why it chose this option before revealing it",
            "notes": [
                "each meaningful state update gets its own card",
                "reuse the same base visual across steps",
            ],
        },
        "final_result_output": {
            "content": [
                "what the algorithm produces when it terminates",
                "how to read the output: path, order, table, value",
                "verify the result is correct against the stopping condition",
            ],
            "visual": "final state visual with output highlighted",
            "microcheck": "check what the final output is or how to read it",
            "notes": [],
        },
        "algorithm_analysis": {
            "content": [
                "time complexity with the input variable named explicitly",
                "space complexity",
                "what input structure or size drives the worst case",
            ],
            "visual": "",
            "microcheck": "check complexity or what drives the worst case",
            "notes": ["include only when complexity is part of the learning goal"],
        },
        "practice": {
            "content": [
                "trace a tricky example, predict next state, or produce the final output/order/path/table",
                "include at least one non-obvious step or edge transition",
                "adaptive feedback that corrects missed state changes",
            ],
            "visual": "if the algorithm operates on a structure (graph/array/tree), include it",
            "microcheck": "",
            "notes": [],
        },
    },

    # ─── Coding Implementation ────────────────────────────────────────────────
    "coding_implementation": {
        "function_goal_first_impression": {
            "content": [
                "what the function or class does in one sentence",
                "what kind of problem this solves",
                "what the learner will implement by the end",
            ],
            "visual": "",
            "microcheck": "",
            "notes": [],
        },
        "inputs_outputs_expected_behavior": {
            "content": [
                "each input: name, type, meaning, constraints",
                "the expected output: type, meaning",
                "what correct behavior looks like on a normal example",
            ],
            "visual": "",
            "microcheck": "check what the function returns for a simple input",
            "notes": [],
        },
        "key_idea_from_previous_topic": {
            "content": [
                "the single concept or algorithm idea that drives the implementation",
                "how it maps to the code structure",
                "why this idea leads to the correct solution",
            ],
            "visual": "",
            "microcheck": "check what the key idea contributes to the implementation",
            "notes": ["skip this card if there is no prerequisite walkthrough"],
        },
        "variables_state_needed": {
            "content": [
                "each variable/structure: name, type, initial value, what it tracks",
                "why each is needed — what the code breaks without it",
                "state invariants to maintain across iterations",
            ],
            "visual": "variable table with name, type, initial value, and role",
            "microcheck": "check what a variable tracks or its initial value",
            "notes": [],
        },
        "edge_cases_base_cases": {
            "content": [
                "each edge case or base case: what triggers it, what the correct return is",
                "why the main logic fails without this guard",
                "ordering — which case is checked first and why",
            ],
            "visual": "",
            "microcheck": "check what happens for an edge input",
            "notes": [],
        },
        "code_build_up": {
            "content": [
                "build the code in meaningful chunks — one chunk per main idea",
                "connect each chunk to a variable, state update, or algorithm step",
                "explain what each important line accomplishes",
            ],
            "visual": "code block for each chunk; annotate lines that change state",
            "microcheck": "check which line comes next or what a specific line does",
            "notes": ["do not dump all code at once — build incrementally"],
        },
        "full_code": {
            "content": [
                "complete, correct implementation",
                "comments only where non-obvious",
            ],
            "visual": "full syntax-highlighted code block",
            "microcheck": "",
            "notes": [],
        },
        "code_walkthrough_dry_run": {
            "content": [
                "trace through the code with a concrete example",
                "show variable values at each key step",
                "show how the code handles at least one edge case",
            ],
            "visual": "dry-run table: step, line executed, variable state",
            "microcheck": "check what a variable holds after a specific step",
            "notes": [],
        },
        "complexity": {
            "content": [
                "time complexity with input variable named",
                "space complexity",
                "what dominates the runtime and why",
            ],
            "visual": "",
            "microcheck": "check time or space complexity",
            "notes": [],
        },
        "practice": {
            "content": [
                "write code, fill a missing line, fix a bug, dry run, or modify for a variation",
                "include at least one edge case in the test input",
                "adaptive feedback explaining why incorrect answers fail",
            ],
            "visual": "",
            "microcheck": "",
            "notes": [],
        },
    },

    # ─── Data Structure Operation ─────────────────────────────────────────────
    "data_structure_operation": {
        "structure_refresh_first_impression": {
            "content": [
                "the data structure being operated on — its form and invariant",
                "what makes it valid — the property the operation must preserve",
                "which operation this lesson covers and why it matters",
            ],
            "visual": "structure diagram showing a valid example at rest",
            "microcheck": "",
            "notes": [],
        },
        "operation_goal": {
            "content": [
                "what the operation achieves",
                "what must remain true after the operation completes",
                "what inputs the operation takes",
            ],
            "visual": "",
            "microcheck": "check what must remain valid after the operation",
            "notes": [],
        },
        "cases_scenarios": {
            "content": [
                "every case the operation must handle: normal case, edge case, structural case",
                "what distinguishes each case — how to recognize which applies",
            ],
            "visual": "small diagram per case showing starting structure",
            "microcheck": "check which case applies given an example structure",
            "notes": [],
        },
        "how_operation_works": {
            "content": [
                "every step for each case: pointer/edge/value changes in order",
                "what changes and what must stay the same at each step",
                "invariant check after the structural change",
            ],
            "visual": "before/during/after diagram — highlight changed pointers, edges, or nodes",
            "microcheck": "check what pointer or edge changes at a specific step",
            "notes": ["may span multiple cards when cases differ significantly"],
        },
        "comprehensive_operation_example": {
            "content": [
                "for each step: current structure, action taken, reason, new structure",
                "cover the normal case and at least one structural edge case",
                "show the invariant is preserved at the end",
            ],
            "visual": "per-step before/after diagram with changed elements highlighted",
            "microcheck": "ask what the structure looks like after a step or why a pointer must change",
            "notes": ["each meaningful pointer/edge change gets its own card"],
        },
        "validity_invariant_check": {
            "content": [
                "verify the result satisfies the structure's invariant",
                "what would make the result invalid — common post-operation mistakes",
                "how to detect an invalid result",
            ],
            "visual": "valid vs invalid result diagram side by side",
            "microcheck": "check whether a given result is valid or what is wrong with it",
            "notes": [],
        },
        "benefits_limitations_complexity": {
            "content": [
                "time complexity of the operation with input named",
                "why the operation costs this much — what drives it",
                "any limitations or constraints on when the operation applies",
            ],
            "visual": "",
            "microcheck": "check the time complexity or a limiting constraint",
            "notes": [],
        },
        "practice": {
            "content": [
                "perform the operation on a given structure, choose the final state, or identify an invalid result",
                "include at least one structural edge case",
                "adaptive feedback explaining which step was missed or why the invariant broke",
            ],
            "visual": "provide the starting structure as a visual",
            "microcheck": "",
            "notes": [],
        },
    },

    # ─── Math Formula / Method ────────────────────────────────────────────────
    "math_formula_method": {
        "context_first_impression": {
            "content": [
                "what problem the formula or method solves",
                "when this method is used and what kind of question it answers",
                "what the learner will be able to compute or derive",
            ],
            "visual": "spatial/graphical context diagram only if the concept is geometric or has a visual shape",
            "microcheck": "",
            "notes": [],
        },
        "formula_method_meaning": {
            "content": [
                "the formula or method stated precisely in LaTeX",
                "what the formula computes — an intuitive sentence for each part",
                "why the formula is structured this way",
            ],
            "visual": "",
            "microcheck": "check what the formula computes or what a key part means",
            "notes": ["never use an image for the formula — use LaTeX"],
        },
        "symbols_inputs_conditions": {
            "content": [
                "every symbol defined: name, unit or type, meaning",
                "domain restrictions and assumptions",
                "what inputs are required and which are optional",
            ],
            "visual": "symbol table in styled UI — not a visual_plan item",
            "microcheck": "check what a symbol means or what domain restriction applies",
            "notes": [],
        },
        "step_by_step_method": {
            "content": [
                "every step in the procedure in order",
                "what is computed or transformed at each step and why",
                "when to stop or what signals a complete answer",
            ],
            "visual": "",
            "microcheck": "check the next valid step in the procedure",
            "notes": ["show all algebraic steps in LaTeX"],
        },
        "comprehensive_worked_example": {
            "content": [
                "identify given values and map to symbols",
                "apply each step of the method with full calculations in LaTeX",
                "interpret the result — what does the number mean",
            ],
            "visual": "spatial or graphical visual only if needed for geometry, probability tree, or number line",
            "microcheck": "ask for the next step or the result of an intermediate calculation before revealing it",
            "notes": [],
        },
        "edge_cases_conditions": {
            "content": [
                "each edge case: what input triggers it, what changes in the method",
                "domain restrictions — what inputs make the formula undefined or inapplicable",
                "how to detect the edge case before applying the formula",
            ],
            "visual": "",
            "microcheck": "check whether a given input triggers an edge case",
            "notes": [],
        },
        "benefits_limitations_complexity": {
            "content": [
                "when this formula/method is preferred over alternatives",
                "what it cannot handle — its domain or applicability limits",
                "computational cost if relevant to the learning goal",
            ],
            "visual": "",
            "microcheck": "check a limiting condition or when an alternative is needed",
            "notes": [],
        },
        "practice": {
            "content": [
                "set up the formula, fill in inputs, solve, or interpret the result",
                "include at least one edge case or domain-restriction input",
                "adaptive feedback explaining which step was wrong and why",
            ],
            "visual": "spatial/geometric visual only if the problem requires it",
            "microcheck": "",
            "notes": [],
        },
    },

    # ─── Proof / Reasoning ────────────────────────────────────────────────────
    "proof_reasoning": {
        "proof_goal_first_impression": {
            "content": [
                "what must be proven — the exact statement",
                "what kind of claim this is: existence, universality, equivalence, etc.",
                "why this claim is non-trivial — what makes it need proof",
            ],
            "visual": "",
            "microcheck": "",
            "notes": [],
        },
        "given_information": {
            "content": [
                "every assumption, premise, or given — stated precisely",
                "what can be used freely and what must be proven",
                "what is NOT given that the learner might assume",
            ],
            "visual": "",
            "microcheck": "check what is given vs what must be proven",
            "notes": [],
        },
        "definitions_allowed_facts": {
            "content": [
                "definitions required for the proof",
                "theorems or facts that may be cited without proof",
                "rules about what manipulations are allowed",
            ],
            "visual": "",
            "microcheck": "check which fact or definition applies at a step",
            "notes": [],
        },
        "proof_strategy": {
            "content": [
                "the proof strategy chosen: direct, contradiction, contrapositive, induction, construction, etc.",
                "why this strategy fits — what structure of the claim matches the strategy",
                "what the strategy will assume and what it must derive",
            ],
            "visual": "",
            "microcheck": "check why this strategy was chosen or what it assumes",
            "notes": [],
        },
        "proof_skeleton": {
            "content": [
                "the structural outline of the proof: assume X, derive Y, conclude Z",
                "all cases or inductive steps named",
                "what each section must accomplish",
            ],
            "visual": "",
            "microcheck": "check what must be shown in a specific section",
            "notes": ["render the skeleton as styled UI, not an image"],
        },
        "step_by_step_proof": {
            "content": [
                "each proof step: statement, justification (definition/theorem/algebra), and what it gives us",
                "show all symbolic manipulation in LaTeX",
                "make explicit when and why each allowed fact is used",
            ],
            "visual": "",
            "microcheck": "check the next valid step or the justification for a step",
            "notes": ["may span multiple cards for long proofs"],
        },
        "validity_why_steps_work": {
            "content": [
                "why the proof as written is valid — what makes each step legitimate",
                "what would make a similar argument invalid",
                "how the conclusion follows from the last step",
            ],
            "visual": "",
            "microcheck": "check whether a modified step is valid or what breaks it",
            "notes": [],
        },
        "invalid_reasoning_common_trap": {
            "content": [
                "a specific invalid argument that looks valid at first",
                "exactly where and why it fails",
                "how to detect this error in a proof",
            ],
            "visual": "",
            "microcheck": "identify the flaw in the invalid argument",
            "notes": ["circular reasoning, assuming the conclusion, invalid case splits are common examples"],
        },
        "practice": {
            "content": [
                "choose a proof strategy, fill a missing step, identify an invalid assumption, or complete a proof skeleton",
                "include at least one trap option in multiple-choice questions",
                "adaptive feedback explaining why an answer is invalid and what the correct step is",
            ],
            "visual": "",
            "microcheck": "",
            "notes": [],
        },
    },

    # ─── Compare / Distinguish ────────────────────────────────────────────────
    "compare_distinguish": {
        "comparison_first_impression": {
            "content": [
                "why these two ideas are commonly confused or compared",
                "what the comparison will reveal — the key distinguishing dimension",
                "when knowing the difference matters in practice",
            ],
            "visual": "side-by-side overview if the two ideas have a natural visual form",
            "microcheck": "",
            "notes": [],
        },
        "idea_a_separately": {
            "content": [
                "what Idea A is — definition, behavior, or purpose",
                "when Idea A is used",
                "its key properties relevant to the comparison",
            ],
            "visual": "diagram of Idea A if spatial or behavioral",
            "microcheck": "check a defining property of Idea A",
            "notes": ["use parallel structure to Idea B's card"],
        },
        "idea_b_separately": {
            "content": [
                "what Idea B is — definition, behavior, or purpose",
                "when Idea B is used",
                "its key properties relevant to the comparison",
            ],
            "visual": "diagram of Idea B if spatial or behavioral — same format as Idea A",
            "microcheck": "check a defining property of Idea B",
            "notes": ["use parallel structure to Idea A's card"],
        },
        "shared_features": {
            "content": [
                "what both ideas have in common — exactly, not approximately",
                "why the shared features cause confusion",
                "what the shared features tell us about the family both belong to",
            ],
            "visual": "",
            "microcheck": "check a shared feature or why it causes confusion",
            "notes": [],
        },
        "key_differences": {
            "content": [
                "each key difference with parallel wording for both sides",
                "why each difference exists — what causes it",
                "what NOT to focus on — the false differences learners overfocus on",
            ],
            "visual": "side-by-side behavior diagram if outputs or processes differ spatially",
            "microcheck": "check the most important difference or a common false distinction",
            "notes": [],
        },
        "same_example_applied_to_both": {
            "content": [
                "one example applied to both ideas with identical inputs",
                "show the output or behavior of each side",
                "explain where the result diverges and why",
            ],
            "visual": "side-by-side trace or result for both ideas on the same input",
            "microcheck": "ask what each idea produces on this input before revealing",
            "notes": ["always use the same example for both sides"],
        },
        "when_to_use_each": {
            "content": [
                "conditions under which Idea A is the right choice",
                "conditions under which Idea B is the right choice",
                "boundary cases where either could work",
            ],
            "visual": "",
            "microcheck": "check which idea applies in a given scenario",
            "notes": [],
        },
        "common_mixups_misconceptions": {
            "content": [
                "the most common incorrect belief about how they differ",
                "what makes the incorrect belief compelling",
                "the correct framing that resolves the mix-up",
            ],
            "visual": "",
            "microcheck": "identify which belief is the misconception",
            "notes": [],
        },
        "practice": {
            "content": [
                "classify a scenario, compare outputs, detect a mix-up, or decide which fits a goal",
                "include at least one boundary case",
                "adaptive feedback explaining the key distinction",
            ],
            "visual": "",
            "microcheck": "",
            "notes": [],
        },
    },

    # ─── Problem-Solving Pattern ──────────────────────────────────────────────
    "problem_solving_pattern": {
        "pattern_first_impression": {
            "content": [
                "what kind of problem this pattern solves",
                "why brute force fails and what makes this pattern efficient",
                "a quick mental image of how the pattern works",
            ],
            "visual": "quick sketch of the pattern's core movement or structure",
            "microcheck": "",
            "notes": [],
        },
        "when_pattern_applies": {
            "content": [
                "problem characteristics that indicate this pattern",
                "problem characteristics that look similar but require a different pattern",
                "why knowing when it applies matters as much as knowing how it works",
            ],
            "visual": "",
            "microcheck": "check whether the pattern applies to a given problem description",
            "notes": [],
        },
        "pattern_signals": {
            "content": [
                "each recognition signal — exact phrasing or structure that appears in problems needing this pattern",
                "how to distinguish this pattern's signals from overlapping patterns",
            ],
            "visual": "",
            "microcheck": "check which signal appears in a problem statement",
            "notes": ["render as a styled recognition checklist"],
        },
        "core_template": {
            "content": [
                "the reusable template or pseudo-code for the pattern",
                "what each line or section of the template does",
                "which parts change between problems and which stay fixed",
            ],
            "visual": "pointer/window movement, DP dependency arrows, or recursion tree as appropriate",
            "microcheck": "check what a part of the template does or what changes between problems",
            "notes": [],
        },
        "state_or_invariant": {
            "content": [
                "the state the pattern maintains at each step",
                "the invariant that must hold throughout — what makes the pattern correct",
                "what breaks if the invariant is violated",
            ],
            "visual": "",
            "microcheck": "check the invariant or what happens when a state update is skipped",
            "notes": [],
        },
        "comprehensive_pattern_example": {
            "content": [
                "apply the pattern step by step: current state, decision, update, reason",
                "cover the normal case and at least one tricky transition",
                "show why the pattern is faster than brute force on this example",
            ],
            "visual": "same visual per step with pointer/window/state highlighted",
            "microcheck": "ask for the next state update or decision before revealing it",
            "notes": [
                "each meaningful state update gets its own card",
                "reuse the same base visual",
            ],
        },
        "variations_and_edge_cases": {
            "content": [
                "each variation: how the problem changes and how the template adapts",
                "edge cases where the pattern still applies but state handling differs",
                "a case where the pattern does NOT apply and why",
            ],
            "visual": "",
            "microcheck": "check how the template changes for a variation",
            "notes": [],
        },
        "similar_patterns_to_avoid": {
            "content": [
                "patterns that look similar but solve different problems",
                "how to tell them apart in a problem statement",
                "what goes wrong if you apply the wrong pattern",
            ],
            "visual": "",
            "microcheck": "classify which pattern applies to a given problem",
            "notes": [],
        },
        "practice": {
            "content": [
                "recognize the pattern, choose the strategy, trace state, fill an update, solve a variation, or debug a misuse",
                "include at least one non-obvious signal or variation",
                "adaptive feedback explaining the recognition cue and the correct state update",
            ],
            "visual": "",
            "microcheck": "",
            "notes": [],
        },
    },

    # ─── Review / Refresh ─────────────────────────────────────────────────────
    "review_refresh": {
        "quick_diagnostic_first_check": {
            "content": [
                "one question that probes the most error-prone or forgotten aspect",
                "reveal the correct answer with a compact explanation",
                "indicate which cards follow based on the answer",
            ],
            "visual": "",
            "microcheck": "",
            "notes": ["skip reteaching if the learner answers correctly"],
        },
        "compressed_recall_card": {
            "content": [
                "the highest-yield rule, formula, or principle in compressed form",
                "one sentence per key idea — no introductions or definitions",
            ],
            "visual": "compact visual or LaTeX reminder only for the part being refreshed",
            "microcheck": "",
            "notes": [],
        },
        "key_rule_procedure_refresh": {
            "content": [
                "the exact rule or procedure the learner most likely forgot",
                "which edge case or condition typically breaks recall",
            ],
            "visual": "",
            "microcheck": "check the rule, edge condition, or next step",
            "notes": [],
        },
        "high_yield_example": {
            "content": [
                "one sharp example that covers the most common application",
                "skip setup — go directly to the non-obvious step",
            ],
            "visual": "compact visual only if needed for the refreshed concept",
            "microcheck": "check the result or the non-obvious step",
            "notes": [],
        },
        "targeted_repair_if_needed": {
            "content": [
                "reteach only the specific part the diagnostic revealed as weak",
                "keep it minimal — one or two focused points",
            ],
            "visual": "",
            "microcheck": "recheck the weak point after repair",
            "notes": ["only include this card if the diagnostic showed weakness"],
        },
        "practice_weak_area_check": {
            "content": [
                "one edge case, trap, trace, formula, proof, or implementation mini-check",
                "focused on the area most likely to still be weak",
            ],
            "visual": "",
            "microcheck": "",
            "notes": [],
        },
        "return_to_flow_bridge": {
            "content": [
                "one sentence connecting this concept back to the topic it unblocks",
                "confirm the learner is ready to continue",
            ],
            "visual": "",
            "microcheck": "",
            "notes": [],
        },
    },

    # ─── Science Concept / Mechanism ─────────────────────────────────────────
    "science_mechanism": {
        "context_first_impression": {
            "content": [
                "what the mechanism or process does and why it matters",
                "where it fits in the larger system",
                "the real-world outcome it produces",
            ],
            "visual": "overview diagram of the mechanism in its system context",
            "microcheck": "",
            "notes": [],
        },
        "definition_core_mechanism": {
            "content": [
                "precise definition of the mechanism",
                "what triggers it to start",
                "what state or output it produces when complete",
            ],
            "visual": "labeled mechanism diagram if the concept is spatial or structural",
            "microcheck": "check what triggers the mechanism or what it produces",
            "notes": [],
        },
        "components_parts": {
            "content": [
                "each component: name, role in the mechanism, what happens without it",
                "how components interact",
                "which components are rate-limiting or critical",
            ],
            "visual": "component diagram with roles labeled",
            "microcheck": "check the role of a component or what breaks without it",
            "notes": [],
        },
        "cause_effect_chain_process_steps": {
            "content": [
                "each step in the cause-effect chain: what triggers it, what happens, what it triggers next",
                "normal-case progression through all steps",
                "where the chain can be interrupted and what happens",
            ],
            "visual": "process flow or cause-effect chain diagram — highlight each step",
            "microcheck": "check what happens next or what triggers a specific step",
            "notes": ["may span multiple cards for long chains"],
        },
        "comprehensive_mechanism_example": {
            "content": [
                "trace the mechanism through a concrete example step by step",
                "show input conditions, each transformation, and the final outcome",
                "include a perturbation: what changes if one variable shifts",
            ],
            "visual": "per-step visual with highlighted state changes",
            "microcheck": "ask what happens next or how the output changes with a different input",
            "notes": [],
        },
        "variable_change_perturbation": {
            "content": [
                "what happens when each key input or variable changes: more, less, or absent",
                "direction of each change: amplify, dampen, disrupt",
                "which variables have the largest effect and why",
            ],
            "visual": "before/after or side-by-side comparison visual",
            "microcheck": "check what changes when a specific variable shifts",
            "notes": [],
        },
        "graph_data_model_interpretation": {
            "content": [
                "what each axis, unit, or line represents",
                "what pattern in the data means and why it appears",
                "how to read an anomaly or exception in the graph",
            ],
            "visual": "graph or data visualization — must have at least 2 data points",
            "microcheck": "check what a feature of the graph means or what an anomaly indicates",
            "notes": ["only include when the source or topic includes trends/data"],
        },
        "benefits_limitations_scope": {
            "content": [
                "conditions under which the mechanism functions normally",
                "conditions under which it fails, breaks down, or does not apply",
                "scope — organism, system, domain, or scale where the mechanism is relevant",
            ],
            "visual": "",
            "microcheck": "check a condition that limits the mechanism",
            "notes": [],
        },
        "practice": {
            "content": [
                "predict a perturbation, identify a blocked step, trace the mechanism, or interpret a graph/data",
                "include at least one non-obvious chain step",
                "adaptive feedback explaining the cause-effect logic",
            ],
            "visual": "provide diagram or graph if the question requires reading structure",
            "microcheck": "",
            "notes": [],
        },
    },

    # ─── System / Architecture ────────────────────────────────────────────────
    "system_architecture": {
        "system_first_impression": {
            "content": [
                "what the system does from end to end",
                "why it exists — what problem it solves",
                "the high-level shape: layers, services, or components",
            ],
            "visual": "high-level architecture map with major components labeled",
            "microcheck": "",
            "notes": [],
        },
        "system_goal_responsibility": {
            "content": [
                "the system's primary responsibility",
                "what it must guarantee — correctness, performance, availability",
                "what is explicitly outside its scope",
            ],
            "visual": "",
            "microcheck": "check what the system is responsible for or what it excludes",
            "notes": [],
        },
        "major_components": {
            "content": [
                "each major component: name, single responsibility, what it takes in and sends out",
                "which component owns each type of decision or data",
            ],
            "visual": "component map with responsibilities labeled",
            "microcheck": "check which component handles a responsibility",
            "notes": [],
        },
        "connections_interfaces": {
            "content": [
                "each connection: what it carries, in which direction, with what protocol or contract",
                "what each interface guarantees — its contract",
                "what happens when an interface fails or behaves unexpectedly",
            ],
            "visual": "architecture map with labeled connections and data flows",
            "microcheck": "check what a connection carries or what a contract guarantees",
            "notes": [],
        },
        "end_to_end_flow": {
            "content": [
                "trace one representative request/data/event through every component",
                "what each component does at each step and what it sends on",
                "where the response/result is assembled",
            ],
            "visual": "sequence or data-flow diagram using the same architecture map",
            "microcheck": "check where the flow goes next after a specific component",
            "notes": [],
        },
        "component_deep_dive": {
            "content": [
                "internal design of one critical or complex component",
                "why it is structured this way — what design choice it reflects",
                "how it interacts with adjacent components in detail",
            ],
            "visual": "zoomed-in component diagram with internal structure",
            "microcheck": "check an internal decision or why the component is structured this way",
            "notes": [],
        },
        "failure_points_bottlenecks": {
            "content": [
                "each failure point: what fails, how it manifests, which downstream components are affected",
                "bottlenecks: where throughput or latency is most constrained",
                "how the system degrades or recovers from each failure",
            ],
            "visual": "architecture map with failure points and affected paths highlighted",
            "microcheck": "check which component is affected by a failure or where the bottleneck is",
            "notes": [],
        },
        "design_choices_tradeoffs": {
            "content": [
                "each major design choice: what was chosen, what was rejected, why",
                "the tradeoff accepted — what is gained and what is sacrificed",
                "when the design choice would change",
            ],
            "visual": "",
            "microcheck": "check what the design choice optimizes for or what changes the decision",
            "notes": [],
        },
        "comprehensive_system_example": {
            "content": [
                "trace a realistic, non-trivial request or event end to end",
                "show each component's action, decision, or transformation",
                "include at least one failure or edge transition",
            ],
            "visual": "sequence diagram or animated architecture map per major step",
            "microcheck": "ask what a component does next or what handles a failure",
            "notes": [],
        },
        "practice": {
            "content": [
                "trace request/data/control flow, identify who owns a responsibility, diagnose a failure, or choose an architecture fix",
                "include a non-obvious flow or an edge failure",
                "adaptive feedback explaining the responsibility or failure path",
            ],
            "visual": "provide architecture diagram if the question requires reading structure",
            "microcheck": "",
            "notes": [],
        },
    },

    # ─── Debugging / Error Diagnosis ──────────────────────────────────────────
    "debugging_diagnosis": {
        "symptom_first_impression": {
            "content": [
                "the symptom — exactly what the learner observes or experiences",
                "why this symptom is confusing or misleading",
                "what system area it likely belongs to",
            ],
            "visual": "error message, log excerpt, or broken-state diagram as appropriate",
            "microcheck": "",
            "notes": [],
        },
        "expected_vs_actual_behavior": {
            "content": [
                "what the correct behavior should be",
                "what the observed behavior is",
                "what the gap tells us about where the fault might be",
            ],
            "visual": "expected-vs-actual side-by-side diagram or code output comparison",
            "microcheck": "check what the expected behavior is or what the gap indicates",
            "notes": [],
        },
        "error_context_system_area": {
            "content": [
                "which layer, component, or subsystem the error most likely originates in",
                "what surrounding context narrows the search space: environment, input, timing",
                "what information is still missing",
            ],
            "visual": "system map with the suspected area highlighted",
            "microcheck": "check which system area the evidence points to",
            "notes": [],
        },
        "possible_causes": {
            "content": [
                "each plausible cause ranked by evidence or likelihood",
                "for each cause: what evidence supports it, what evidence would rule it out",
                "what assumptions were made that could be wrong",
            ],
            "visual": "cause tree or ranked cause list as styled UI",
            "microcheck": "check which cause the current evidence most supports",
            "notes": [],
        },
        "diagnostic_checks": {
            "content": [
                "each diagnostic check: what it tests, what a positive result means, what a negative result rules out",
                "how to run the check — command, log query, code change, observation",
                "order the checks from fastest/cheapest to slowest",
            ],
            "visual": "",
            "microcheck": "check what a diagnostic result tells us or which check to run next",
            "notes": [],
        },
        "comprehensive_debugging_walkthrough": {
            "content": [
                "trace the full debugging session: symptom → hypotheses → checks → narrowed cause → fix",
                "show each check result and how it changes the hypothesis",
                "cover at least one misleading result that sends the debugger in the wrong direction briefly",
            ],
            "visual": "broken-to-fixed flow or cause-tree with eliminated branches highlighted",
            "microcheck": "ask which hypothesis a result eliminates or what check comes next",
            "notes": [],
        },
        "fix": {
            "content": [
                "the fix — exactly what to change and why it addresses the root cause",
                "why the symptom disappears with this fix",
                "what NOT to fix — common adjacent changes that are unnecessary",
            ],
            "visual": "before/after code diff or configuration diff",
            "microcheck": "check why this fix addresses the root cause",
            "notes": [],
        },
        "verification": {
            "content": [
                "how to confirm the fix worked — specific test or observation",
                "how to confirm nothing regressed — what else to check",
                "what a successful verification looks like",
            ],
            "visual": "",
            "microcheck": "check what a successful verification looks like",
            "notes": [],
        },
        "prevention": {
            "content": [
                "what practice, check, or constraint prevents this error class from recurring",
                "how to detect this earlier in the development cycle",
            ],
            "visual": "",
            "microcheck": "",
            "notes": [],
        },
        "practice": {
            "content": [
                "map symptom to cause, choose the next diagnostic check, interpret evidence, choose a fix, or verify a repair",
                "include a misleading clue or a second plausible cause",
                "adaptive feedback explaining the evidence chain",
            ],
            "visual": "provide the error message, log, or broken state diagram as context",
            "microcheck": "",
            "notes": [],
        },
    },

    # ─── Tool / Workflow ──────────────────────────────────────────────────────
    "tool_workflow": {
        "workflow_first_impression": {
            "content": [
                "what the tool or workflow accomplishes and why it is used",
                "the end-to-end shape of the workflow in one paragraph",
                "what the learner will be able to do after completing this lesson",
            ],
            "visual": "workflow map or pipeline diagram at a high level",
            "microcheck": "",
            "notes": [],
        },
        "setup_requirements": {
            "content": [
                "every prerequisite: software, permissions, environment, credentials",
                "how to verify each requirement is met before starting",
                "what to do if a requirement is missing",
            ],
            "visual": "",
            "microcheck": "check a prerequisite or how to verify it",
            "notes": [],
        },
        "files_commands_ui_parts": {
            "content": [
                "each file, command, or UI element: name, purpose, when it is used",
                "what each command or element does — not just the syntax",
                "which parts are required vs optional",
            ],
            "visual": "file tree or command reference as styled UI",
            "microcheck": "check what a file or command does",
            "notes": [],
        },
        "step_by_step_workflow": {
            "content": [
                "each step: current state, action, expected result, how to verify success",
                "explain why each step is in this order",
                "note which steps are destructive or irreversible",
            ],
            "visual": "terminal output block or workflow step diagram per step",
            "microcheck": "check the next action or expected output at a step",
            "notes": ["may span multiple cards for complex workflows"],
        },
        "verification_steps": {
            "content": [
                "how to confirm the workflow completed successfully",
                "what a successful output or state looks like",
                "what partial success looks like and what to do about it",
            ],
            "visual": "expected terminal output or success-state screenshot",
            "microcheck": "check what success looks like for a step",
            "notes": [],
        },
        "common_breakpoints_troubleshooting": {
            "content": [
                "each common failure: what it looks like, what causes it, how to fix it",
                "how to recognize the safe-default recovery path",
            ],
            "visual": "",
            "microcheck": "check the cause of a specific error or next fix step",
            "notes": [],
        },
        "comprehensive_workflow_example": {
            "content": [
                "run the complete workflow on a realistic example from setup to verification",
                "show exact commands, outputs, and state changes",
                "include at least one error and its recovery",
            ],
            "visual": "terminal output block or file-tree progression per step",
            "microcheck": "ask what comes next or what a specific output means",
            "notes": [],
        },
        "best_practices_safety_notes": {
            "content": [
                "each best practice: what it is, why it matters, what goes wrong without it",
                "safety notes for destructive or irreversible steps",
            ],
            "visual": "",
            "microcheck": "",
            "notes": [],
        },
        "practice": {
            "content": [
                "choose the next action, order steps, interpret output, fix a setup error, or verify a result",
                "include at least one breakpoint or recovery scenario",
                "adaptive feedback explaining the correct action and why",
            ],
            "visual": "provide terminal output or state as context",
            "microcheck": "",
            "notes": [],
        },
    },

    # ─── Design / Decision ────────────────────────────────────────────────────
    "design_decision": {
        "decision_context_first_impression": {
            "content": [
                "the decision being made and why it is non-trivial",
                "the options that exist at a high level",
                "what constraints or context will drive the choice",
            ],
            "visual": "decision overview diagram or option cards",
            "microcheck": "",
            "notes": [],
        },
        "options_overview": {
            "content": [
                "each option: name, what it does, what problem it was designed to solve",
                "use parallel structure for all options",
            ],
            "visual": "",
            "microcheck": "check what an option is designed to solve",
            "notes": [],
        },
        "decision_criteria": {
            "content": [
                "each criterion that matters for this decision: what it measures, why it matters",
                "how to evaluate each criterion in a given scenario",
                "which criteria are typically most important and why",
            ],
            "visual": "criteria table as styled UI",
            "microcheck": "check which criterion applies in a given scenario",
            "notes": [],
        },
        "tradeoff_breakdown": {
            "content": [
                "for each option: what it gains, what it sacrifices, what it assumes",
                "which tradeoffs are acceptable under which constraints",
                "tradeoffs that are commonly misunderstood or underweighted",
            ],
            "visual": "tradeoff matrix as styled UI",
            "microcheck": "check what a specific option sacrifices or what assumption it makes",
            "notes": [],
        },
        "scenario_based_decision_walkthrough": {
            "content": [
                "a realistic scenario with explicit constraints",
                "apply each criterion to the scenario and eliminate options",
                "arrive at the choice and explain what drove the elimination",
            ],
            "visual": "decision tree or elimination diagram if the walkthrough branches",
            "microcheck": "ask which option survives a specific constraint before revealing",
            "notes": [],
        },
        "when_decision_changes": {
            "content": [
                "each change in constraint or context that flips the preferred option",
                "what new information would change the recommendation",
                "boundary cases where both options are acceptable",
            ],
            "visual": "",
            "microcheck": "check what constraint flip changes the decision",
            "notes": [],
        },
        "common_wrong_decision_misconception": {
            "content": [
                "the most common wrong choice and why it seems reasonable",
                "what it ignores or underweights",
                "the corrected framing",
            ],
            "visual": "",
            "microcheck": "identify the flaw in the wrong reasoning",
            "notes": [],
        },
        "benefits_limitations_final_choice": {
            "content": [
                "what the recommended option delivers when the scenario fits it",
                "what its limits are — when to reconsider",
            ],
            "visual": "",
            "microcheck": "check a limit or when to reconsider",
            "notes": [],
        },
        "practice": {
            "content": [
                "choose the best option under constraints, identify the deciding criterion, or detect flawed reasoning",
                "include at least one boundary case or constraint flip",
                "adaptive feedback explaining the criterion chain",
            ],
            "visual": "",
            "microcheck": "",
            "notes": [],
        },
    },

    # ─── Case Study / Application ─────────────────────────────────────────────
    "case_study_application": {
        "real_scenario_first_impression": {
            "content": [
                "the real scenario — context, actors, and the problem to solve",
                "why this scenario is a good illustration of the concept",
                "what the learner will see the concept do in practice",
            ],
            "visual": "scenario map or system diagram showing the real-world context",
            "microcheck": "",
            "notes": [],
        },
        "concept_refresh_if_needed": {
            "content": [
                "compact recall of the concept — one sentence per key idea",
                "only include if the learner likely needs a reminder",
            ],
            "visual": "",
            "microcheck": "",
            "notes": ["skip if the concept was just taught in a prior card or topic"],
        },
        "concept_to_scenario_mapping": {
            "content": [
                "each abstract element of the concept mapped explicitly to its real-world counterpart",
                "why each mapping holds — what makes the analogy valid",
                "what does NOT map perfectly and why",
            ],
            "visual": "abstract-to-real mapping diagram — two columns, arrow between each pair",
            "microcheck": "check what a specific abstract element maps to in the scenario",
            "notes": [],
        },
        "scenario_components_roles": {
            "content": [
                "each real-world component: name, role, what it does in the scenario",
                "how components interact in this specific context",
            ],
            "visual": "scenario diagram with components labeled",
            "microcheck": "check the role of a component",
            "notes": [],
        },
        "step_by_step_application": {
            "content": [
                "each step the concept performs in the scenario: input, action, output, effect on the system",
                "what decision or transformation happens at each step",
                "why steps are ordered this way",
            ],
            "visual": "per-step scenario diagram showing state changes",
            "microcheck": "check what happens next or why a step produces a specific output",
            "notes": ["may span multiple cards for complex applications"],
        },
        "result_impact": {
            "content": [
                "what the system looks like after the concept is applied",
                "how the outcome differs from what would happen without it",
                "what the result enables next",
            ],
            "visual": "before/after diagram of the scenario state",
            "microcheck": "check how the result changes the system",
            "notes": [],
        },
        "variation_failure_case": {
            "content": [
                "a variation: how the scenario changes and how the concept's application adapts",
                "a failure case: what happens when the concept is misapplied or conditions are not met",
            ],
            "visual": "",
            "microcheck": "check what changes in the variation or why the failure occurs",
            "notes": [],
        },
        "benefits_limitations_in_this_scenario": {
            "content": [
                "what the concept does well in this specific scenario",
                "what it cannot handle — constraints specific to this context",
                "when a different approach would be better here",
            ],
            "visual": "",
            "microcheck": "check a limitation specific to this scenario",
            "notes": [],
        },
        "practice": {
            "content": [
                "identify the concept in a new scenario, map parts, trace the application, predict the outcome, or diagnose a wrong application",
                "include at least one scenario where the concept does not apply cleanly",
                "adaptive feedback explaining the mapping or the failure",
            ],
            "visual": "provide a scenario diagram or description as context",
            "microcheck": "",
            "notes": [],
        },
    },

    # ─── Historical / Development ─────────────────────────────────────────────
    "historical_development": {
        "starting_context_first_impression": {
            "content": [
                "the problem or need that started the development",
                "what existed before and why it was insufficient",
                "the era or context in which this development began",
            ],
            "visual": "timeline starting point or early-model diagram",
            "microcheck": "",
            "notes": [],
        },
        "initial_model_early_approach": {
            "content": [
                "what the first model, approach, or understanding looked like",
                "what it got right",
                "what it could not explain or handle",
            ],
            "visual": "early model diagram or representation",
            "microcheck": "check what the early model got right or where it failed",
            "notes": [],
        },
        "limitations_pressure_for_change": {
            "content": [
                "each specific limitation that made the old approach insufficient",
                "what evidence, event, or need created pressure for change",
                "why the limitation was not obvious at first",
            ],
            "visual": "",
            "microcheck": "check which limitation forced the next development",
            "notes": [],
        },
        "major_development_timeline": {
            "content": [
                "each major development in order: what changed, who or what drove it, what problem it solved",
                "emphasize problems and turning points — not dates unless required",
            ],
            "visual": "timeline diagram with developments and turning points marked",
            "microcheck": "check what drove a specific development",
            "notes": [],
        },
        "turning_point_cards": {
            "content": [
                "one turning point per card: what happened, what it changed fundamentally, why it mattered",
                "what would have happened without it",
            ],
            "visual": "old-to-new model comparison diagram",
            "microcheck": "check what the turning point changed or why it mattered",
            "notes": ["one card per major turning point"],
        },
        "cause_effect_development_chain": {
            "content": [
                "the chain of cause and effect across developments: limitation → development → new capability → new limitation",
                "what stayed stable across changes",
            ],
            "visual": "cause-effect chain diagram",
            "microcheck": "check what a development enabled or what new limitation it created",
            "notes": [],
        },
        "modern_version_current_understanding": {
            "content": [
                "what the current model, approach, or understanding is",
                "how it differs from the starting point",
                "what makes it better — and what it still cannot do",
            ],
            "visual": "modern model diagram",
            "microcheck": "check how the modern version differs or what it still cannot do",
            "notes": [],
        },
        "what_stayed_vs_changed": {
            "content": [
                "each element that stayed constant across all developments and why",
                "each element that changed fundamentally and what drove the change",
            ],
            "visual": "stayed-vs-changed comparison table as styled UI",
            "microcheck": "check which element stayed or changed and why",
            "notes": [],
        },
        "benefits_limitations_modern_version": {
            "content": [
                "what the modern version handles that earlier versions could not",
                "what it still does not handle — open problems or known limitations",
            ],
            "visual": "",
            "microcheck": "check a modern limitation or open problem",
            "notes": [],
        },
        "practice": {
            "content": [
                "order developments, match a limitation to its development, compare old vs new, or identify what changed",
                "include at least one turning point or cause-effect step",
                "adaptive feedback explaining the problem-development chain",
            ],
            "visual": "",
            "microcheck": "",
            "notes": [],
        },
    },

    # ─── Process / Lifecycle ──────────────────────────────────────────────────
    "process_lifecycle": {
        "process_first_impression": {
            "content": [
                "what the process or lifecycle does and why it is structured this way",
                "the high-level shape: how many stages, is it linear or cyclical",
                "what the final output or end state is",
            ],
            "visual": "lifecycle or process flow diagram — full view with all stages",
            "microcheck": "",
            "notes": [],
        },
        "stage_overview": {
            "content": [
                "each stage: name, what it accomplishes, what its output is",
                "the order and why it is in this order",
            ],
            "visual": "stage map with inputs and outputs labeled",
            "microcheck": "check the output of a stage or why stages are ordered this way",
            "notes": [],
        },
        "stage_by_stage_cards": {
            "content": [
                "for each stage: input received, action taken, output produced, what triggers the next stage",
                "what makes the stage complete",
                "what can go wrong at this stage",
            ],
            "visual": "zoomed-in stage diagram with input/action/output labeled",
            "microcheck": "check the output of the stage or what triggers the next",
            "notes": ["one card per stage or cluster of related stages"],
        },
        "transitions_handoffs": {
            "content": [
                "each handoff: what is passed, from where, to where, in what format",
                "what must be true for the handoff to succeed",
                "what breaks if the handoff fails",
            ],
            "visual": "handoff arrows on the process diagram with data labels",
            "microcheck": "check what is handed off or what breaks a handoff",
            "notes": [],
        },
        "feedback_loops_repeats": {
            "content": [
                "each feedback loop: what triggers it, where it loops back to, what changes in the repeated pass",
                "when the process exits the loop",
                "what prevents infinite looping",
            ],
            "visual": "process diagram with feedback arrows highlighted",
            "microcheck": "check what triggers a loop-back or what exits the loop",
            "notes": [],
        },
        "comprehensive_process_example": {
            "content": [
                "trace a realistic example through every stage",
                "show the input and output of each stage",
                "include at least one loop-back or failure at a stage",
            ],
            "visual": "per-step stage highlight on the full process diagram",
            "microcheck": "ask what the output of the next stage is before revealing",
            "notes": [],
        },
        "failure_points_bottlenecks": {
            "content": [
                "each failure point: which stage, what fails, what the downstream effect is",
                "bottlenecks: which stage limits throughput or causes the most delays",
                "how the process recovers or stalls",
            ],
            "visual": "process diagram with failure and bottleneck stages highlighted",
            "microcheck": "check which stage is the bottleneck or what a failure's effect is",
            "notes": [],
        },
        "benefits_limitations_scope": {
            "content": [
                "when this process or lifecycle is the right structure",
                "what it handles poorly — domains or inputs it is not suited for",
                "scope: what systems, domains, or scales it applies to",
            ],
            "visual": "",
            "microcheck": "check a scope limit or when to use a different structure",
            "notes": [],
        },
        "practice": {
            "content": [
                "identify the stage, order stages, predict the next stage, diagnose a broken process, or choose a loop-back point",
                "include at least one failure or loop-back scenario",
                "adaptive feedback explaining stage outputs and triggers",
            ],
            "visual": "provide the process diagram as context",
            "microcheck": "",
            "notes": [],
        },
    },

    # ─── Terminology / Vocabulary ─────────────────────────────────────────────
    "terminology_vocabulary": {
        "term_set_first_impression": {
            "content": [
                "why these terms are grouped together — their shared domain or role",
                "which terms block understanding of the larger topic",
                "the base example that will be used throughout to ground all terms",
            ],
            "visual": "base example diagram or structure that labels will be added to",
            "microcheck": "",
            "notes": [],
        },
        "term_map_grouping": {
            "content": [
                "how the terms relate to each other: hierarchy, parallel roles, or cause-effect",
                "why these groupings matter for understanding",
            ],
            "visual": "term relationship map or labeled grouping diagram",
            "microcheck": "check how two terms relate or which group a term belongs to",
            "notes": [],
        },
        "core_term_cluster_cards": {
            "content": [
                "each term in the cluster: definition, role in the system, example in the base example",
                "what makes this term distinct from its neighbors",
            ],
            "visual": "labeled diagram using the base example — highlight the term being introduced",
            "microcheck": "check what a term means or what role it plays",
            "notes": ["one card per cluster of 2-4 related terms"],
        },
        "same_example_with_labels": {
            "content": [
                "the base example with every introduced term labeled on it",
                "how all the terms fit together in one picture",
            ],
            "visual": "fully labeled base example diagram",
            "microcheck": "identify which label belongs where",
            "notes": [],
        },
        "similar_confusing_terms": {
            "content": [
                "each pair of confusing terms: what they share, what makes them different",
                "the context clue that tells them apart in practice",
            ],
            "visual": "",
            "microcheck": "check which term applies in a specific context",
            "notes": [],
        },
        "usage_in_context": {
            "content": [
                "each term used in a sentence or paragraph the way a practitioner would use it",
                "what changes if the wrong term is used",
            ],
            "visual": "",
            "microcheck": "choose the correct term for a given sentence or situation",
            "notes": [],
        },
        "practice": {
            "content": [
                "label a visual, match a term to an example, choose a term in a scenario, detect a misuse, or interpret a technical sentence",
                "include at least one confusing-term pair",
                "adaptive feedback explaining what the correct term refers to",
            ],
            "visual": "provide the base example diagram if the question requires label recognition",
            "microcheck": "",
            "notes": [],
        },
    },

    # ─── Exam / Interview Prep ────────────────────────────────────────────────
    "exam_interview_prep": {
        "assessment_first_impression": {
            "content": [
                "what the assessment format is: timed, structured, open-ended, or multiple choice",
                "what kinds of tasks it requires and what it tests",
                "what the learner's goal is for this session",
            ],
            "visual": "",
            "microcheck": "",
            "notes": [],
        },
        "scope_high_yield_topics": {
            "content": [
                "every topic likely to appear — ordered by frequency or weight",
                "which topics are highest yield and why",
                "topics to de-prioritize given time constraints",
            ],
            "visual": "skill map or topic weight list as styled UI",
            "microcheck": "check which topic is highest yield or most likely to appear",
            "notes": [],
        },
        "question_types": {
            "content": [
                "each question type: format, what it tests, what a strong answer looks like",
                "common variants and how to recognize them",
            ],
            "visual": "question type comparison table as styled UI",
            "microcheck": "identify the question type from a sample prompt",
            "notes": [],
        },
        "strategy_selection": {
            "content": [
                "first-move strategy for each question type: what to read, what to do first",
                "when to skip and return vs commit and solve",
                "how to allocate time across question types",
            ],
            "visual": "strategy checklist as styled UI",
            "microcheck": "check the first move for a specific question type",
            "notes": [],
        },
        "timed_or_realistic_example": {
            "content": [
                "a realistic problem in the assessment format",
                "work through it with the full strategy: first move, solution, verification",
                "note where time is typically lost on this type",
            ],
            "visual": "problem diagram or code skeleton if the question type requires it",
            "microcheck": "check the first move or the result of a step before revealing",
            "notes": [],
        },
        "common_traps": {
            "content": [
                "each trap: what it looks like, why it is tempting, what the correct response is",
                "how to detect the trap early in the problem",
            ],
            "visual": "trap comparison — wrong answer vs correct reasoning",
            "microcheck": "identify the trap in a problem before attempting it",
            "notes": [],
        },
        "weak_area_repair": {
            "content": [
                "reteach the specific weak area identified by prior checks",
                "keep it minimal: one key rule, one example, one recheck",
            ],
            "visual": "",
            "microcheck": "recheck the weak area with a new instance",
            "notes": ["only include when weak area is identified"],
        },
        "mixed_practice": {
            "content": [
                "a set of questions spanning the high-yield topics",
                "mix question types — include at least one trap",
                "adaptive feedback that routes to weak-area repair when needed",
            ],
            "visual": "problem diagram or code if question types require it",
            "microcheck": "",
            "notes": [],
        },
        "review_plan": {
            "content": [
                "summarize which areas are strong and which need further review",
                "recommend what to study next and in what order",
                "note which topics to revisit closest to the assessment",
            ],
            "visual": "",
            "microcheck": "",
            "notes": [],
        },
    },
}


# TopicType compatibility aliases. The current public topic taxonomy has 10
# topic types, while this stage-rule table still keeps the richer historical
# rule sets. These aliases let the new topic types reuse the closest existing
# card-content rules without changing every lesson-generation caller at once.
STAGE_RULES.setdefault("math_proof_reasoning", STAGE_RULES["math_formula_method"])
STAGE_RULES.setdefault("compare_decide", STAGE_RULES["compare_distinguish"])
STAGE_RULES.setdefault("system_workflow_debugging", STAGE_RULES["system_architecture"])
STAGE_RULES.setdefault("application_historical", STAGE_RULES["case_study_application"])


def _lean_rule(
    *content: str,
    visual: str = "",
    microcheck: str = "",
    notes: list[str] | None = None,
) -> CardStageRule:
    return {
        "content": list(content),
        "visual": visual,
        "microcheck": microcheck,
        "notes": notes or [],
    }


_UNIVERSAL_LEAN_RULES: dict[str, CardStageRule] = {
    "background": _lean_rule(
        "what this topic is — state the central idea directly in the first point",
        "the core mental model: the rule, principle, or mechanism that drives it and why it works",
        "why this topic matters only when it names a specific technical capability, constraint, result, or failure it prevents",
        "prerequisite context only as the immediate next step from where prior topics or assumed prerequisites ended",
        visual="plain-English visual_description when a visual helps convey the central idea at a glance",
        notes=[
            "This card combines orientation and core concept — start teaching immediately. Do not warm up with filler.",
            "Begin from the exact level where prior topics ended. If an earlier topic taught BSTs, assume BST structure is known and start from there. If no prior topics exist, begin from the assumed prerequisites.",
            "Do not re-explain content that assumed prerequisites or prior topics already cover.",
            "This card may span multiple slides when the central idea needs more explanation. Repeat blueprint_key 'background' for each continuation card.",
            "Continuation cards must pick up exactly where the previous background card left off — do not repeat content already covered.",
            "Explain in plain language without dumbing down: use correct terms but lead with intuition before the formal definition.",
            "Every point must have a specific teaching purpose — state an actual rule, behavior, result, condition, contrast, step, or consequence.",
            "A point may use terms from assumed prerequisites or prior topic scope without fully explaining them.",
            "If an assumed prerequisite term is not self-explanatory in context, briefly allude to it or give a tiny reminder instead of reteaching it.",
            "If a precise technical term is necessary and is neither assumed/prior scope nor already taught, explain it in plain language immediately or move it to components_terms.",
            "If a bullet needs two unexplained technical ideas, split it, simplify it, or move it later.",
            "If one point contains multiple ideas, split it into a main point plus indented subpoints in the points array.",
            "Represent subpoints as separate strings prefixed with two spaces and '- '.",
            "This structure applies across every topic type and card, not just algorithms.",
            "Use the main point as the frame, question, incomplete clause, or primary idea being answered.",
            "Put ordered actions, reasons, consequences, caveats, examples, and elaborations as subpoints.",
            "Do not compress the frame and answer into one full sentence when subpoints would reduce cognitive load.",
            "If a point says X happens because/so/when/which Y, make X the main point and Y a subpoint.",
            "If a point gives an order or list, make the order/list frame the main point and each item a subpoint.",
            "If a point contains prose plus an equation, keep the prose as the main point and put the complete equation in one subpoint.",
            "Good: 'Preorder traversal visits nodes in this order:' then subpoints 'visit the current node first', 'then traverse the left subtree', 'then traverse the right subtree'.",
            "Use visible bullet-line count to decide when a card is too dense: main bullet + every nested subbullet each count as 1 line.",
            "Cards without visual_description should stay at or below 6 visible bullet lines.",
            "Cards with visual_description or state-transition content should stay at or below 4 visible bullet lines.",
            "Never split a main bullet away from its subbullet tree. Split only between complete main-bullet trees, using the same blueprint_key and title for the continuation card.",
            "Do not include a 'why this matters' point unless it names a specific technical capability, constraint, result, or failure it prevents.",
            "If the only reason is that the topic prepares for later lessons, omit the point.",
            "Do not justify importance with industry applications or generic study-path motivation.",
            "Only explain why learning an older or prior method matters when that history is central to the topic's meaning or progression.",
            "Benefits and limitations must be immediately understandable from the initial framing — if they require later lesson knowledge, omit them or simplify to the learner-readable consequence.",
            "Keep complex tradeoffs, proof-level limitations, implementation constraints, and rare exceptions out of background unless they are core to why the topic exists.",
            "Do not use vague phrases such as 'specific order', 'important concept', 'useful technique', 'key idea', 'fundamental concept', 'plays a crucial role', 'helps you understand', 'various', 'several', 'different ways', 'in many cases', 'sets the stage', 'builds a foundation', 'future lessons', 'future topics', 'more advanced topics', 'complex applications', 'deeper understanding', or 'important for understanding'.",
            "Do not write learner outcome statements such as 'After this lesson you will be able to...' or 'By the end you will understand...'. Teach the content directly.",
            "Replace generic nouns with the actual rule, behavior, result, condition, or skill for this topic.",
            "For algorithms and processes, name the actual action rule and output/result.",
            "Title each background card as a question, not a noun phrase or statement. 'What is BST Traversal?' is correct. 'What BST Traversal Is' or 'BST Traversal Overview' are wrong. The title should be the question the card answers.",
        ],
    ),
    "components_terms": _lean_rule(
        "key terms, symbols, variables, state pieces, roles, or parts",
        "simple meaning and role of each piece",
        "how the pieces relate",
        visual="plain-English visual_description for labeled diagrams or structural layouts when helpful",
        notes=[
            "Format each term as the main bullet (no colon at the end) with its definition as a sub-bullet. Example: main bullet 'Queue', sub-bullet '  - a structure that processes nodes in arrival order (FIFO)'.",
            "Never end a term bullet with a colon. The term stands alone as the main bullet.",
            "Only create this card when there are at least 3 current-topic terms that genuinely need explanation.",
            "If fewer than 3 terms need explanation, skip this card and explain the needed term briefly inside background or process.",
            "Only include terms and components that are needed to understand or apply the current topic.",
            "Before counting terms, remove all terms listed in the Assumption Ledger as assumed prerequisites, prior taught content, or do_not_reteach.",
            "If only assumed/prior terms remain after filtering, skip this card.",
            "Adjust depth based on what the learner already knows:",
            "  - If a component is new (not in assumed prerequisites or prior topics): explain what it is and its role clearly.",
            "  - If a component is already known from prerequisites or prior topics: name it and its role briefly — do not reteach it.",
            "  - Example: for BST level-order traversal, 'parent node, left subtree, right subtree' are known from BST prerequisites — list them without explanation. 'Queue' may be new — explain it briefly as 'a structure that processes nodes in arrival order (first in, first out).'",
            "Each term point must explain the term's role in this topic, not just name it.",
            "If a term point has multiple role details, use a main point plus indented subpoints.",
            "Use components_terms to introduce current-topic technical terms that would otherwise make background confusing.",
            "Do not turn assumed prerequisites into a full reteaching card unless the topic scope says they need support.",
        ],
    ),
    "process": _lean_rule(
        "starting state: the general structure/data provided, the state trackers used, and what each tracker represents before any concrete input is traced",
        "repeated action: the exact rule the algorithm applies on each iteration or recursive call",
        "state update: what changes after each iteration — pointer moved, value stored, node enqueued/dequeued, counter incremented",
        "stopping condition: when the loop or recursion ends and why",
        "output rule: what is returned or produced and how it is assembled",
        visual="plain-English visual_description showing before state, action/change, and after state for the current step",
        notes=[
            "State each of the five elements explicitly — starting state, repeated action, state update, stopping condition, output rule.",
            "Do not write only that the learner follows steps or that the algorithm processes input in order.",
            "Name the actual tracker roles, data structure operations, or conditions for this specific algorithm.",
            "For non-example process cards, describe state generically. Do not assign concrete example values such as `root = 40`, `current = 40`, `queue = [A]`, `visited = {A}`, or `result = []`.",
            "Use symbolic roles and placeholders for process cards: `root`, `start node`, `current node`, `output starts empty`, `queue starts with the start node`, `call stack begins with the initial call`.",
            "Concrete tracker values belong in worked_example, code_walkthrough, and coding worked_example cards.",
            "For state-based topics, visual_description must name the state before the step, the action/change, and the state after the step.",
            "For progressive reveal continuation cards, visual_description should describe only the newly added state change.",
            "For coding_implementation: starting state includes all variables declared before the loop, their types, and initial values. Repeated action is each line or block inside the loop and what it does. State update lists every variable modified per iteration.",
            "Bad: 'BFS uses a queue to visit nodes level by level.' — this names the tool but not the mechanism.",
            "Bad process starting state: 'root = 40, current = 40, result = []'",
            "Good process starting state: 'queue contains the start node; visited records the start node; output starts empty'",
            "Good tree traversal starting state: 'the first active node or call is the root; output starts empty'",
            "Good repeated action: 'dequeue front node; for each unvisited neighbor: mark visited, enqueue'",
            "Good state update: 'queue shrinks by 1 (front removed), grows by 0–N (neighbors added to back)'",
            "Good stopping condition: 'stop when queue is empty — no reachable unvisited nodes remain'",
            "Good output: 'nodes in dequeue order = level-by-level visit order'",
        ],
    ),
    "worked_example": _lean_rule(
        "Currently — main bullet with label only; each tracker value is its own sub-bullet",
        "[what is happening at this step] — [why this action follows the rule], with sub-bullets for each reason or detail",
        "Now — main bullet with label only; each tracker value is its own sub-bullet",
        visual="plain-English storyboard naming the full state: structure + highlighted node or line + all tracker values",
        notes=[
            "Each worked_example card covers exactly ONE step. Never put multiple steps on one card. One card = one Currently block + one action block + one Now block. If a trace has 7 steps, generate 7 separate worked_example cards, each with its own unique title, its own points, and its own visual_description showing the exact state at that step.",
            "Worked examples should lean toward the difficult side: use strong university midterm/final difficulty rather than textbook warm-up difficulty.",
            "The main worked example should carry the complex solving behavior: irregular structure, branch choices, nuanced decisions, and the full mechanism. Smaller boundary or non-applicability cases belong on edge_case cards.",
            "Never use one easy example as the only example when the topic has meaningful edge cases, irregular structures, branch choices, or common traps.",
            "The main worked example must require at least 5 meaningful steps across its worked_example cards, unless the card is explicitly a tiny boundary case such as empty input or single-node input.",
            "If the main example would naturally have fewer than 5 steps, choose a richer example. Do not use a 3-node tree, 3-item array, or one-iteration trace as the main worked example.",
            "Each worked_example card must have a UNIQUE title: 3–5 words, noun-phrase or verb-phrase style, naming only the key action or transition at that step. Bad: 'Tracing Inorder Traversal' (same for every card), 'Push 40, move left to 30' (too long, too literal). Good: 'Push root onto stack', 'Visit left child', 'Backtrack to parent', 'Pop and output node', 'Search ends — not found'. Treat it like a slide title, not a sentence.",
            "REQUIRED structure: point 1 = 'Currently: [trackers]' with a description sub-bullet, point 2 = action + why, point 3 = 'Now: [trackers]' with a description sub-bullet.",
            "Currently and Now lines: put all tracker values inline after the colon (comma-separated), then add exactly ONE sub-bullet with a plain-English description of what that state means.",
            "Bad: 'Currently: current=30, result=[25], call_stack=[40→30] — we are at node 30' (description inline after em-dash).",
            "Good: 'Currently: current=30, result=[25], call_stack=[40→30]' as main bullet, then '  - we are at node 30, ready to visit its left subtree' as the single description sub-bullet.",
            "Bad: 'Now: result=[25,30], call_stack=[40→30], next=recurse right' (no description sub-bullet).",
            "Good: 'Now: result=[25,30], call_stack=[40→30]' as main bullet, then '  - node 30 is added; next we recurse right to node 35' as the single description sub-bullet.",
            "Do NOT merge Currently/action/Now into one sentence. They must be three separate top-level bullets.",
            "In the action bullet and description sub-bullets, always write variable values inline next to the variable name using the format 'name (value)'. Bad: 'low > high, search ends'. Good: 'low (3) > high (2), search ends'. Bad: 'target is less than array[mid]'. Good: 'target (5) is less than array[mid] (7)'.",
            "Every tracker must appear in Currently and Now sub-bullets: result/output, queue/stack/call_stack, current node, visited set, pointer positions.",
            "For coding: all variables must appear as sub-bullets. 'Currently' then '  - i=0', '  - j=0', '  - k=0', '  - result=[_,_,_,_,_,_]'.",
            "Show arrays as actual values with _ for unfilled slots: result=[2,_,_,_,_].",
            "The visual_description MUST name every tracker with its current value — not a general description.",
            "Good visual_description (tree): 'BST root=40 (children 30,50; 30 has children 25,35; 50 has children 45,60). Node 30 highlighted. Call stack=[40→30] beside tree. Result=[25] below tree.'",
            "Good visual_description (code): 'Merge function. Line 4 (result[k]=left[i]) highlighted. i=1, j=0, k=1. left=[1,3,5], right=[2,4,6], result=[1,_,_,_,_,_].'",
            "Very obvious consecutive steps may be grouped only when combining them does not hide important state changes.",
            "Continuation cards must continue the same example state.",
            "For tree or graph traversal, use a non-trivial structure: at least 7 nodes, not a complete/perfect tree. A 3-node traversal example is invalid except as a separate tiny edge_case card after the main example.",
            "For BST inorder traversal: non-complete BST with at least 7 nodes, left-only/right-only branches, leaf nodes, parent returns, final sorted output.",
            "--- CODING IMPLEMENTATION TOPICS: use code-trace format instead of algorithm-trace format ---",
            "For coding_implementation topics, do NOT use the Currently/action/Now format. Use code-trace format: trace the actual code line by line (or block by block) for one specific input.",
            "Pick one test case that exercises every major branch in the code (both if and else paths, loop entry and exit, edge inputs if short enough). The CARD title should state the exact input values, e.g. 'Tracing merge([1,2,3,0,0,0], 3, [2,5,6], 3)'. Each step group uses the same card title since they all belong to the same code block.",
            "Group lines into functional units: one initialization group (all setup lines together), then one group per meaningful iteration step or branch decision. A 'group' = one top-level bullet. Do not give every single line its own card.",
            "Top-level bullet format for each group: briefly name what this block does (e.g. 'Initialization — copy nums1 and set all pointers to 0'). Always include current variable values inline with format 'name (value)' for the variables involved.",
            "Sub-bullets under each group: one sub-bullet per line or sub-step, showing what it does and the resulting state change. Always write values inline: 'nums1[idx (0)] = nums1Copy[i (0)] = 1, advance i → 1, idx → 1'.",
            "For branch decisions (if/else, while condition), make the condition check its own sub-bullet: 'j (0) >= n (3)? No → check next condition: i (0) < m (3) and nums1Copy[i] (1) <= nums2[j] (2)? Yes → take if branch'.",
            "Show array state as actual values with _ for unfilled slots: 'nums1 = [1, _, _, _, _, _]'.",
            "End the trace with a sub-bullet showing the final output/return value.",
            "REQUIRED output fields for coding_implementation worked_example cards: 'code_snippet' (the full implementation function as a string, using the same language as the code_walkthrough card) and 'highlight_lines_per_step' (a JSON array of [start_line, end_line] pairs, one pair per top-level bullet in points, 1-indexed). The i-th pair corresponds to which lines of code_snippet are being executed in the i-th bullet group. Example: if bullets are [Initialization, Loop iter 1, Loop iter 2, End] and initialization is lines 1-3, loop body lines 5-9, etc., then highlight_lines_per_step = [[1,3],[5,9],[5,9],[10,10]].",
            "The code_snippet must be the actual complete function code, not a pseudocode or partial snippet. Use the same implementation shown in the code_walkthrough card.",
        ],
    ),
    "comparison": _lean_rule(
        "what the ideas share",
        "the deciding difference",
        "when to use each idea",
        visual="plain-English visual_description for side-by-side or decision visuals when helpful",
        notes=[
            "Each point must name the actual shared feature, difference, or decision criterion.",
            "Do not write generic comparison points like 'these ideas have similarities and differences'.",
        ],
    ),
    # "common_mistake": _lean_rule(
    #     "the tempting wrong interpretation or step",
    #     "why it is wrong",
    #     "the correct way to think or act",
    # ),
    "edge_case": _lean_rule(
        "the special case",
        "what changes from the normal case",
        "what stays governed by the same idea",
        notes=[
            "Name the exact edge case; do not say only that edge cases exist.",
            "Include the consequence of the edge case or omit the card.",
            "Edge_case cards should cover smaller focused boundary cases, not the complex exam-grade mechanism. Use them for empty input/structure, single element/node, missing child/subtree, no valid path, disconnected component, duplicate/boundary value, impossible input, failed precondition, or the condition where the algorithm/method should not be used.",
            "If the edge case requires more than 2 meaningful actions to solve, it is too complex for edge_case and should be handled as worked_example coverage instead.",
            "If multiple small edge cases matter, create adjacent edge_case continuation cards with the same blueprint_key. Each card should cover one boundary condition or a small cluster of closely related boundaries.",
            "For BST traversal edge cases, use focused cases such as empty tree -> [], single node -> [node], only-left/only-right skew behavior, or missing subtree behavior. Keep the irregular 7+ node traversal in worked_example cards.",
            "The main bullet MUST be the descriptive name of the specific input or condition — never write 'Edge case 1', 'Edge case 2', or any 'Edge case N' label. Use the actual condition as the label: 'Empty array input', 'k larger than array length', 'All elements negative', etc.",
            "Each main bullet is a different edge case condition, not a numbered placeholder.",
        ],
    ),
    "implementation_plan": _lean_rule(
        "function goal: what it computes, its inputs, and its return value",
        "variables and state: every variable needed, its type, starting value, and what it tracks",
        "control flow: the loop or recursion structure, what each branch handles, and the termination condition",
        "base cases and edge cases: what inputs require special handling and what the code does for each",
        notes=[
            "Name every variable with its type and starting value. Do not say 'we need a counter' — say 'i: int = 0, tracks current index in left array'.",
            "This card is an implementation design plan, not an algorithm process card. Do not restate the abstract algorithm steps.",
            "Focus only on the concrete code artifacts needed to implement the previously taught algorithm or operation.",
            "Keep the implementation_plan on one card unless the card becomes too long. Use adjacent implementation_plan continuation cards only for overflow, not for one tiny code artifact per card.",
            "Name the exact data structure when relevant: queue/deque for level-order traversal, call stack/recursive calls for recursive traversal, explicit stack for iterative DFS, pointers for two-pointer/sliding-window code, hash map/set for lookup state.",
            "State the loop structure explicitly: 'while i < len(left) and j < len(right)' not 'iterate until both arrays exhausted'.",
            "When this follows an algorithm walkthrough, keep it solely technical: translate the algorithm into code decisions.",
            "Do not repeat background, motivation, or why the algorithm matters.",
            "Every point should answer: what code artifact, variable, or control-flow construct do we need and why does it have this shape?",
        ],
    ),
    "code_walkthrough": _lean_rule(
        "short code blocks or code steps",
        "why each major line or block exists",
        "how code maps to state or concept behavior",
        visual="plain-English visual_description for code-state mapping when helpful",
        notes=[
            "This card is required for coding_implementation topics. If the implementation needs several functional blocks, create adjacent code_walkthrough continuation cards until the whole implementation is built.",
            "The left-side visual focus for every code_walkthrough card is the code block itself. Use visual_type='code_trace'; do not use a comparison table, state-change table, step flow, or prose fallback for code_walkthrough.",
            "Raw code belongs in code_snippet only. Points should explain what the code does in plain English; do not make a bullet that is only a code line like 'def inorder(root):'.",
            "Put related code ideas on the same code_walkthrough card when they explain one coherent functional addition. Do not split function signature, initializations, guard + return, loop header + body skeleton, or paired recursive calls into separate tiny cards unless the card would become too long.",
            "Start from a tiny valid beginning: usually the function signature, then base case or initialization. Each later code_walkthrough card must show code_snippet as the full implementation-so-far.",
            "Do not show the completed code until the final code_walkthrough card. Earlier cards must not include future lines or future branches.",
            "Explain the newly added functional block only. Do not re-explain the algorithm behavior already taught in the walkthrough topic.",
            "Use sub-bullets under each main bullet for how the code works, why it is shaped that way, and which state/variable changes. Do not flatten those details into separate unrelated main bullets.",
            "For each major line or block: state what it does, why it must exist, and what variable/structure it changes.",
            "Do not write 'this loop iterates over elements' — write what the loop variable holds, what the condition checks, and what changes per iteration.",
            "If a line initializes a variable, name the variable, its type, and its starting value and why that starting value is correct.",
            "Map each code construct to the code responsibility it fulfills: setup, base case, loop/recursion, branch, state update, or return.",
            "REQUIRED output fields for coding_implementation code_walkthrough cards: code_snippet and highlight_lines_per_step.",
            "For code_walkthrough, code_snippet should contain only the implementation code built up through the current functional block; do not include future code that has not been introduced yet.",
            "Each adjacent code_walkthrough card must include all prior code plus exactly one new meaningful line or functional block, such as an if block, loop block, recursive-call pair, queue operation block, pointer update block, or final return.",
            "Use one highlight_lines_per_step range per top-level bullet group, pointing to the newly introduced line or functional block. The frontend reveals only code up to the current block and highlights that block.",
        ],
    ),
    "formula_breakdown": _lean_rule(
        "the formula or method meaning",
        "each symbol or input",
        "conditions for valid use",
        "use LaTeX or structured text, not formula images",
    ),
    "proof_plan": _lean_rule(
        "the proof strategy",
        "why the strategy fits",
        "givens, target, and major milestones",
    ),
    "roadmap": _lean_rule(
        "preview the major topics the learner will study",
        "explain why they appear in this order",
        "show how each upcoming topic builds toward the overall goal",
        "this is not a generic list — explain the learning journey",
        notes=[
            "Only include when the path covers multiple subtypes of one central idea (e.g. inorder, preorder, postorder, level-order all being BST traversals).",
            "Skip when the upcoming topics are largely independent or when a list would add no insight.",
        ],
    ),
    "practice": _lean_rule(
        "one reconstruction, trace, or application task — not a recognition or definition question",
        "question, answer, and the exact skill being tested",
        "the concrete action the learner must perform: trace the algorithm, write the output, predict state, debug code",
        notes=[
            "Practice must require the learner to DO something: trace an algorithm step by step, produce an output sequence, compute a value, identify a bug, or apply the rule to new input.",
            "Do not ask questions answerable by pattern-matching a definition or recalling a vocabulary term.",
            "Bad: 'What data structure does BFS use?' — answerable from memory of a label.",
            "Good: 'BFS starts at node 1. After visiting nodes 1 and 2, what is in the queue? (1→2, 1→3, 2→4, 3→4)' — requires tracing.",
            "Good: 'Trace merge sort merging [1,3,5] and [2,4,6]. Write result after the first 3 comparisons.' — requires applying the process.",
            "For coding_implementation: ask the learner to trace through code with specific inputs, predict output, or spot incorrect state.",
            "Practice question must be specific enough that only a learner who understood the mechanism can answer it.",
        ],
    ),

}


STAGE_RULES.update(
    {
        "concept_intuition": _UNIVERSAL_LEAN_RULES,
        "terminology_components": _UNIVERSAL_LEAN_RULES,
        "process_walkthrough": _UNIVERSAL_LEAN_RULES,
        "algorithm_walkthrough": _UNIVERSAL_LEAN_RULES,
        "data_structure_operation": _UNIVERSAL_LEAN_RULES,
        "coding_implementation": _UNIVERSAL_LEAN_RULES,
        "math_formula_method": _UNIVERSAL_LEAN_RULES,
        "proof_reasoning": _UNIVERSAL_LEAN_RULES,
        "compare_distinguish": _UNIVERSAL_LEAN_RULES,
        "problem_solving_application": _UNIVERSAL_LEAN_RULES,
        "science_mechanism": _UNIVERSAL_LEAN_RULES,
        "study_path_introduction": {
            "background": _lean_rule(
                "what the overall concept area is",
                "the central idea that ties all upcoming topics together",
                "why it matters in the context of the study path — what it enables or what problem it solves for the learner",
                "the main mental model the learner should carry into the path",
                "keep this broad and orienting — do not teach any subtopic here",
                visual="plain-English visual_description for a high-level overview diagram when the concept area has a natural spatial or structural form (e.g. a tree, a graph, a chain) that helps the learner picture the central idea before the path begins",
            ),
            "components_terms": _lean_rule(
                "the minimum vocabulary the learner needs before the rest of the path makes sense",
                "simple meaning and role of each term",
                "how the terms relate to each other",
                visual="plain-English visual_description for a labeled diagram that shows how the terms fit together — only when the concept area has a clear structural or spatial form",
                notes=[
                    "Only include this card when at least 3 bridge terms remain after removing assumed prerequisites and later topic titles/subtopics.",
                    "Do not include assumed prerequisites here; name them only if absolutely needed and do not explain them.",
                    "Do not define upcoming topics or traversal variants here; preview those in roadmap instead.",
                    "If only one or two bridge terms remain, skip this card and mention the term briefly in background or roadmap.",
                    "Only include when the learner genuinely cannot follow the upcoming topics without these terms.",
                    "Keep it lightweight — do not turn this into a full terminology lesson unless the first real topic is terminology_components.",
                ],
            ),
            "roadmap": _lean_rule(
                "group the upcoming topics into natural categories when they fall into distinct families",
                "for each topic, give a one-sentence summary of its key concept — what it does or what makes it distinct",
                "keep each summary at the level of 'what this topic is about', not a full explanation",
                "do not explain topic order or learning journey — just preview the key ideas with their grouping",
                visual="",
                notes=[
                    "Only include when the path covers multiple subtypes of one central idea — for example inorder, preorder, postorder, and level-order as subtypes of BST traversal.",
                    "Skip when the upcoming topics are largely independent of each other.",
                    "Cover all upcoming topics — do not truncate the list. If the path has many topics, continue with a second roadmap card using the same blueprint_key.",
                    "Bad: 'We will start with inorder traversal, then move to preorder, building up to level-order.'",
                    "Good example (BST traversal intro):",
                    "  Depth-first traversals (explore a branch fully before moving on):",
                    "    Inorder (left → node → right): produces sorted output on a BST.",
                    "    Preorder (node → left → right): visits the root first, used for copying or serializing a tree.",
                    "    Postorder (left → right → node): visits children before the parent, used in deletion and expression evaluation.",
                    "  Breadth-first traversal (explore level by level):",
                    "    Level-order: visits all nodes at depth 0, then depth 1, then depth 2, using a queue.",
                ],
            ),
        },
    }
)
