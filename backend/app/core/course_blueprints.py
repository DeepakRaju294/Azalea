from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.core.course_types import TopicType


Blueprint = dict[str, Any]


COMMON_RULES = {
    "card_density": [
        "Each card teaches one main idea or one meaningful step.",
        "Use the main bullet as the frame, and put the answer, ordered actions, reasons, consequences, caveats, examples, and elaborations as subpoints.",
        "Use subpoints when a bullet would otherwise contain multiple actions, reasons, conditions, or a prose sentence followed by an equation.",
        "If a bullet says X happens because/so/when/which Y, use X as the main bullet and Y as a subpoint.",
        "If a bullet gives an order or list, use the order/list frame as the main bullet and each item as a separate subpoint.",
        "For process/state cards, keep frames such as Starting state, Repeated action, State update, Stopping condition, and Output rule as main bullets; put variables, actions, conditions, and results as subpoints.",
        "For recursive algorithms, refer to the call stack. For iterative algorithms, refer to an explicit stack. Do not use vague wording like stateful stack.",
        "Card budget: visual cards may contain at most 2 main bullets and 4 total visible bullet lines. No-visual cards may contain at most 3 main bullets and 6 total visible bullet lines.",
        "Split by complete teaching units, not by raw text length. An idea group is one main bullet plus all subpoints, one trace state plus action/result, one code line/block plus explanation, one edge case plus consequence, one proof step plus justification, one formula step plus interpretation, or one visual step plus its matching explanation.",
        "Never split a main bullet away from its subbullet tree; split only between complete idea groups.",
        "Never split inside a bracketed state like stack=[A,B,C], queue=[A, B], result=[10, 20], visited={A, B}, or Call stack: [40 -> 30].",
        "Never split a visual step from its matching explanation, a code line/block from its explanation, a proof step from its justification, or a formula calculation from its interpretation.",
        "If adding the next main-bullet tree would exceed the budget, continue with the immediately next card using the same blueprint_key and title.",
        "A continuation card means same blueprint_key, same instructional job, and the same example/process/proof/formula/term set continues because content is too long or the trace has more steps.",
        "Do not title continuation cards Card 2, Continuation, Part 2, or More Details; use role-specific titles that name the current step or unit.",
        "Continuation cards should not repeat setup. For worked examples, code traces, proofs, and math continuations, include a state handoff: previous state, current action, and resulting state.",
        "Use progressive reveal when the learner is doing the same cognitive task and only the next substep changes; use a new card type when the instructional job changes.",
        "Prefer fewer focused cards over filler cards.",
        "Keep new/current-topic ideas fully explained.",
        "Do not include a why-this-matters point unless it names a specific technical capability, constraint, result, or failure it prevents. If the only reason is that the topic prepares for later lessons, omit the point.",
        "Do not use study-path filler such as sets the stage, builds a foundation, future lessons, future topics, more advanced topics, complex applications, deeper understanding, or important for understanding.",
    ],
    "scope_rules": [
        "The topic type chooses which card roles exist.",
        "Stage rules choose what belongs inside selected cards.",
        "Topic scope contract can narrow any blueprint card.",
        "Algorithm walkthrough topics include a coding implementation continuation by default unless the learner explicitly asks for no code, trace-only, walkthrough-only, or concept-only treatment.",
        "Standalone coding_implementation topics keep their background card.",
        "Coding implementation continuations that follow an algorithm_walkthrough or data_structure_operation for the same idea skip background and begin with technical implementation planning.",
    ],
    "rich_content_rules": [
        "Do not generate popups, interactive links, microchecks, generated visual assets, or interactive visual components.",
        "Use visual_description only when a visual would help the learner.",
        "For state-based topics, visual_description should describe the before state, the action/change, and the after state.",
        "Use visual_description as a storyboard for future visuals, not as instructions to generate actual assets.",
        "For algorithms, recursion, data structures, code, math procedures, proofs, systems, debugging, and science mechanisms, name the state trackers that matter on the card. Use concrete tracker values only on worked_example, code_walkthrough, coding worked_example, or cards that explicitly trace a concrete input.",
        "If a card is a progressive reveal continuation, visual_description should describe only the new visual change being added.",
    ],
    "components_terms_rules": [
        "Create a components_terms/key terms card only when there are at least 3 current-topic terms that genuinely need explanation.",
        "If there are fewer than 3 terms, skip the components_terms card and explain the needed term briefly inside another card.",
        "Do not use components_terms to reteach assumed prerequisites or preview terms that will be taught as later topics.",
        "Use the Assumption Ledger before counting terms: remove assumed prerequisites, prior taught content, and do_not_reteach items from the candidate terms.",
        "Never create components_terms solely from terms the learner is assumed to know, such as node/root/subtree in a BST traversal lesson.",
    ],
    "example_rules": [
        "Worked examples must be high-level relative to the topic.",
        "Use coverage examples: worked examples should be complex enough to reveal important normal cases, confusing cases, branch choices, and nuances for the current topic.",
        "Examples should lean toward the difficult side: use strong university midterm/final difficulty rather than textbook warm-up difficulty.",
        "Prefer a complicated but teachable example over an easy example that leaves nothing to learn.",
        "The main worked example should carry the complex solving behavior. Edge_case cards should carry smaller boundary, non-applicability, or minimal-structure cases.",
        "If one example cannot cover all complex cases, or doing so would make it cluttered/confusing, split coverage across multiple worked_example continuation cards.",
        "If several small edge cases matter, use adjacent edge_case continuation cards with the same blueprint_key instead of forcing them into the main worked example.",
        "Edge_case cards should be focused and simple: empty input/structure, single element/node, missing child/subtree, no valid path, disconnected component, duplicate/boundary value, impossible input, failed precondition, or the condition where the algorithm/method should not be used.",
        "Do not turn an edge_case card into a second large worked example. If an edge case requires more than 2 meaningful actions to solve, treat it as worked_example coverage instead.",
        "Never use one easy example as the only example when the topic has meaningful edge cases, irregular structures, branch choices, or common traps.",
        "Do not use toy examples that make the process look obvious or leave nothing meaningful to teach.",
        "A worked example should include enough structure, steps, or cases that the learner must actually apply the rule.",
        "The main worked example must require at least 5 meaningful steps across its worked_example cards.",
        "Count only steps where the learner must apply a rule, update state, choose a branch, transform an expression, justify a proof move, or interpret a result.",
        "If the example would naturally have fewer than 5 steps, choose a richer example instead of using a tiny one.",
        "The worked_example card sequence must run to full completion — trace all the way to the terminal state (empty queue/stack, recursion fully unwound, array sorted, problem fully solved, final output confirmed). Do not stop partway through a trace because the 5-card minimum has been reached.",
        "The final worked_example card must show the terminal state: the complete output, empty trackers, and confirmation that no further steps remain.",
        "For tree or graph traversal topics, use a non-trivial structure: usually at least 7 nodes, not a complete/perfect tree, with missing children or uneven branches when those details affect the trace.",
        "A 3-node tree or graph is invalid as the main traversal worked example; use it only as a separate tiny boundary example if needed.",
        "For BST inorder traversal, use a non-complete BST with at least 7 nodes and include left-only/right-only branches, leaf nodes, returns to parent nodes, and the final sorted output.",
        "Use as few examples as possible without harming clarity.",
        "Prefer one comprehensive example when it can cover the important surface area cleanly.",
        "Use multiple worked_example cards when one example cannot cover all important cases or would become too crowded or confusing.",
        "When an example spans multiple cards, each worked_example card should explain a coherent step or small group of obvious steps.",
        "Every non-obvious example step must explain the action, why that action is allowed or chosen, the resulting state/output, and what the learner should notice.",
        "Very obvious steps can be grouped with the nearest non-obvious step instead of getting their own card.",
        "Across worked_example plus edge_case cards, all essential cases and nuances for the current topic should be covered unless they are explicitly out of scope.",
    ],
}


EXAMPLE_TYPE_DEFINITIONS: dict[str, dict[str, str]] = {
    "none": {
        "purpose": "No example role is needed for this card.",
        "best_for": "cards that teach orientation, vocabulary, or pure takeaway content",
        "structure": "leave example fields empty unless a tiny inline illustration is necessary",
        "teaching_goal": "avoid forcing examples where they would be filler",
    },
    "state_trace_example": {
        "purpose": "Show how system state changes step by step over time.",
        "best_for": "algorithms, graph traversal, recursion, DP, queues/stacks, parsers, pointer movement",
        "structure": "initial state -> action taken -> updated state -> why the state changed -> progressive continuation",
        "teaching_goal": "help the learner internalize how the system evolves over time",
    },
    "concept_application_example": {
        "purpose": "Show an abstract concept in one realistic situation.",
        "best_for": "concept intuition topics where a concrete case makes the idea easier to picture or apply",
        "structure": "realistic situation -> concept appears -> what the concept explains or predicts",
        "teaching_goal": "turn an abstract idea into usable understanding",
    },
    "concept_boundary_example": {
        "purpose": "Show where a simple interpretation stops working.",
        "best_for": "concept intuition topics with meaningful non-standard cases or limits",
        "structure": "normal interpretation -> boundary/non-standard case -> what changes -> corrected scope",
        "teaching_goal": "teach the concept's limits without overloading the main explanation",
    },
    "concept_transfer_prompt": {
        "purpose": "Ask the learner to recognize or apply the concept in a new case.",
        "best_for": "concept practice and transfer checks",
        "structure": "new scenario -> learner identifies/applies concept -> feedback target",
        "teaching_goal": "verify concept understanding beyond the original example",
    },
    "boundary_or_irregular_state_example": {
        "purpose": "Show that the rule still works under messy or irregular structure.",
        "best_for": "trees, graphs, arrays, recursion, traversal",
        "structure": "irregular input/state -> what changes -> what remains invariant",
        "teaching_goal": "prevent overfitting to clean textbook examples",
    },
    "transfer_trace_prompt": {
        "purpose": "Ask the learner to apply the same mechanism to a new-looking structure.",
        "best_for": "traversal, recursion, algorithms, process tracing",
        "structure": "unfamiliar-looking input -> same underlying rule -> learner prediction or trace",
        "teaching_goal": "measure transfer ability rather than memorization",
    },
    "operation_case_example": {
        "purpose": "Show how an operation modifies a structure while preserving invariants.",
        "best_for": "BST operations, heaps, linked lists, hash tables",
        "structure": "initial structure -> operation target -> structural updates -> invariant preservation",
        "teaching_goal": "teach how operations maintain correctness",
    },
    "special_case_operation_example": {
        "purpose": "Teach structurally unique operation cases separately.",
        "best_for": "deletion operations, rotations, collisions, edge operations",
        "structure": "special structural condition -> why normal process is insufficient -> modified handling process",
        "teaching_goal": "teach case recognition and specialized handling",
    },
    "operation_transfer_prompt": {
        "purpose": "Ask the learner to perform the operation on a new structure.",
        "best_for": "data-structure operation practice",
        "structure": "new starting structure -> operation target -> learner chooses case/update -> invariant check",
        "teaching_goal": "verify the operation transfers beyond the taught structure",
    },
    "line_by_line_execution_example": {
        "purpose": "Trace actual code execution one line at a time.",
        "best_for": "coding implementation, recursion, debugging",
        "structure": "input -> current line -> variable states -> branch decisions -> return values",
        "teaching_goal": "bridge algorithm understanding to implementation understanding",
    },
    "execution_trace_example": {
        "purpose": "Show overall code behavior on meaningful input.",
        "best_for": "implementation walkthroughs, recursion, loops",
        "structure": "input -> major execution states -> variable evolution -> final output",
        "teaching_goal": "build mental execution models",
    },
    "test_case_boundary_example": {
        "purpose": "Show the exact case that breaks incomplete implementations.",
        "best_for": "coding edge cases, debugging",
        "structure": "boundary input -> expected behavior -> naive failure -> corrected handling",
        "teaching_goal": "teach implementation robustness",
    },
    "implementation_transfer_task": {
        "purpose": "Force adaptation of an implementation to a modified condition.",
        "best_for": "coding, algorithms, problem solving",
        "structure": "existing implementation -> changed requirement/input -> learner adapts solution",
        "teaching_goal": "prevent memorized implementation dependency",
    },
    "setup_calculation_interpretation_example": {
        "purpose": "Teach the full math workflow from setup to interpretation.",
        "best_for": "formulas, statistics, physics, engineering math",
        "structure": "given information -> variable mapping -> setup -> calculation -> interpretation",
        "teaching_goal": "teach formulas as reasoning tools instead of memorized equations",
    },
    "condition_boundary_example": {
        "purpose": "Show when a formula or method stops applying or changes behavior.",
        "best_for": "math, probability, calculus, statistics",
        "structure": "boundary/restriction case -> why normal method changes/fails -> correct handling",
        "teaching_goal": "teach applicability conditions",
    },
    "math_transfer_prompt": {
        "purpose": "Ask the learner to apply the method to a new setup.",
        "best_for": "math formula or method practice",
        "structure": "new given information -> variable mapping -> learner setup/calculation/interpretation",
        "teaching_goal": "verify the method transfers to a different problem statement",
    },
    "proof_step_justification_example": {
        "purpose": "Teach why each proof step is logically valid.",
        "best_for": "proofs, derivations, formal reasoning",
        "structure": "current proof state -> reasoning step -> justification -> resulting state",
        "teaching_goal": "build rigorous logical reasoning",
    },
    "next_proof_step_prompt": {
        "purpose": "Make the learner determine the next valid proof step.",
        "best_for": "proof practice, derivations",
        "structure": "current proof state -> available facts -> learner predicts next step",
        "teaching_goal": "develop active reasoning ability",
    },
    "side_by_side_contrast_example": {
        "purpose": "Show two similar ideas under the same setup so differences become obvious.",
        "best_for": "compare/distinguish topics",
        "structure": "shared setup -> behavior/result under idea A -> behavior/result under idea B -> comparison takeaway",
        "teaching_goal": "clarify distinctions and prevent confusion",
    },
    "classification_example": {
        "purpose": "Teach how to identify which concept or pattern applies.",
        "best_for": "pattern recognition, compare/distinguish topics",
        "structure": "scenario -> identifying clues -> chosen concept -> why others do not apply",
        "teaching_goal": "teach concept selection",
    },
    "classification_transfer_prompt": {
        "purpose": "Ask the learner to classify a new scenario.",
        "best_for": "compare/distinguish practice",
        "structure": "new scenario -> close options -> learner selects concept -> deciding clue",
        "teaching_goal": "verify the learner can use the distinction outside the teaching example",
    },
    "pattern_application_example": {
        "purpose": "Show how to recognize and apply a reusable strategy or pattern.",
        "best_for": "problem solving topics",
        "structure": "problem -> pattern signal -> strategy choice -> application steps -> final answer",
        "teaching_goal": "teach reusable problem-solving frameworks",
    },
    "pattern_boundary_example": {
        "purpose": "Show where a pattern needs adjustment or fails.",
        "best_for": "problem solving, transfer",
        "structure": "modified condition -> why standard pattern breaks -> required adjustment",
        "teaching_goal": "teach flexible application",
    },
    "transfer_problem_example": {
        "purpose": "Verify the learner can recognize the same pattern in a different-looking problem.",
        "best_for": "transfer practice",
        "structure": "new surface form -> same underlying mechanism -> misleading detail",
        "teaching_goal": "measure deep understanding rather than memorization",
    },
    "cause_effect_chain_example": {
        "purpose": "Show how changing one component affects the entire mechanism step by step.",
        "best_for": "science, systems, processes",
        "structure": "starting condition -> changed variable/component -> cause-effect progression -> final outcome",
        "teaching_goal": "build causal mental models",
    },
    "perturbation_example": {
        "purpose": "Show how a mechanism changes under modified conditions.",
        "best_for": "science, systems, simulations",
        "structure": "changed condition -> affected mechanism link -> changed outcome",
        "teaching_goal": "teach sensitivity to changing variables",
    },
    "mechanism_prediction_prompt": {
        "purpose": "Ask the learner to predict what changes when one condition changes.",
        "best_for": "science mechanism practice",
        "structure": "changed condition -> learner predicts affected link -> final outcome",
        "teaching_goal": "verify causal reasoning and mechanism transfer",
    },
}


EXAMPLE_CARD_RULES: dict[str, dict[str, dict[str, Any]]] = {
    TopicType.CONCEPT_INTUITION.value: {
        "worked_example": {
            "example_type": "concept_application_example",
            "use_when": "An example would make the abstract idea easier to picture or apply.",
            "skip_when": "The concept can be explained clearly with definition + visual only.",
            "purpose": "Show the concept in one realistic situation.",
        },
        "edge_case": {
            "example_type": "concept_boundary_example",
            "use_when": "A non-standard case changes how the concept should be understood.",
            "purpose": "Show where the simple interpretation stops working.",
        },
        "practice": {
            "example_type": "concept_transfer_prompt",
            "purpose": "Check whether the learner can recognize or apply the concept in a new case.",
        },
    },
    TopicType.TERMINOLOGY_COMPONENTS.value: {
        "worked_example": {
            "example_type": "classification_example",
            "purpose": "Show the terms or components being identified in context.",
        },
        "practice": {
            "example_type": "classification_transfer_prompt",
            "purpose": "Ask the learner to identify or classify the terms in a new case.",
        },
    },
    TopicType.PROCESS_WALKTHROUGH.value: {
        "process": {
            "example_type": "none",
            "purpose": "Explain the general process schema: starting state roles, repeated action, state update, stopping condition, and output rule without concrete example values.",
        },
        "worked_example": {
            "example_type": "state_trace_example",
            "purpose": "Apply the process to a meaningful input with step-by-step state.",
        },
        "edge_case": {
            "example_type": "condition_boundary_example",
            "purpose": "Show when the process changes or stops applying.",
        },
        "practice": {
            "example_type": "transfer_trace_prompt",
            "purpose": "Ask the learner to apply the process to a different-looking input.",
        },
    },
    TopicType.ALGORITHM_WALKTHROUGH.value: {
        "process": {
            "example_type": "none",
            "purpose": "Explain the general algorithm mechanism and tracker roles without tracing one concrete input.",
        },
        "worked_example": {
            "example_type": "state_trace_example",
            "use_when": "The learner must see the algorithm state change over time.",
            "purpose": "Trace the algorithm using meaningful state trackers.",
            "must_include": ["input/state", "changing state trackers", "decisions", "final output"],
        },
        "edge_case": {
            "example_type": "boundary_or_irregular_state_example",
            "use_when": "Irregular input changes or tests the algorithm behavior.",
            "purpose": "Show the algorithm on a non-clean case.",
        },
        "comparison": {
            "example_type": "side_by_side_contrast_example",
            "use_when": "A related algorithm has already been introduced.",
            "purpose": "Show the same input under two related algorithms.",
        },
        "practice": {
            "example_type": "transfer_trace_prompt",
            "purpose": "Ask learner to trace a different-looking input.",
        },
    },
    TopicType.DATA_STRUCTURE_OPERATION.value: {
        "process": {
            "example_type": "none",
            "purpose": "Explain the general operation cases, invariant checks, and state updates without using one concrete structure as the process card.",
        },
        "worked_example": {
            "example_type": "operation_case_example",
            "purpose": "Show the operation while preserving the invariant.",
            "must_include": ["starting structure", "operation target", "case", "before/after state", "invariant check"],
        },
        "edge_case": {
            "example_type": "special_case_operation_example",
            "use_when": "The operation has structurally different cases.",
            "purpose": "Teach case-specific handling.",
        },
        "practice": {
            "example_type": "operation_transfer_prompt",
            "purpose": "Ask learner to perform the operation on a new structure.",
        },
    },
    TopicType.CODING_IMPLEMENTATION.value: {
        "code_walkthrough": {
            "example_type": "line_by_line_execution_example",
            "use_when": "The code has meaningful control flow or state updates.",
            "purpose": "Trace important lines with variable state.",
        },
        "worked_example": {
            "example_type": "execution_trace_example",
            "purpose": "Show the implementation running on a meaningful input.",
        },
        "edge_case": {
            "example_type": "test_case_boundary_example",
            "use_when": "A boundary input is needed for correctness.",
            "purpose": "Show the test case that incomplete code would fail.",
        },
        "practice": {
            "example_type": "implementation_transfer_task",
            "purpose": "Ask learner to complete, adapt, or debug code.",
        },
    },
    TopicType.MATH_FORMULA_METHOD.value: {
        "formula_breakdown": {
            "example_type": "setup_calculation_interpretation_example",
            "purpose": "Anchor the formula meaning in setup and interpretation.",
        },
        "process": {
            "example_type": "none",
            "purpose": "Explain the general setup, calculation, and interpretation workflow without substituting concrete values.",
        },
        "worked_example": {
            "example_type": "setup_calculation_interpretation_example",
            "purpose": "Show setup, calculation, and meaning of the result.",
        },
        "edge_case": {
            "example_type": "condition_boundary_example",
            "use_when": "The formula has restrictions, undefined cases, signs, zero cases, or multiple/no-solution cases.",
            "purpose": "Teach when the method changes or stops applying.",
        },
        "practice": {
            "example_type": "math_transfer_prompt",
            "purpose": "Ask learner to apply the method to a new setup.",
        },
    },
    TopicType.PROOF_REASONING.value: {
        "proof_plan": {
            "example_type": "proof_step_justification_example",
            "purpose": "Show why the planned proof moves are logically valid.",
        },
        "process": {
            "example_type": "none",
            "purpose": "Explain the general proof progression and justification pattern without turning the process card into a full proof example.",
        },
        "worked_example": {
            "example_type": "proof_step_justification_example",
            "purpose": "Show each proof move with its justification.",
        },
        "practice": {
            "example_type": "next_proof_step_prompt",
            "purpose": "Ask learner to choose or write the next valid proof step.",
        },
    },
    TopicType.COMPARE_DISTINGUISH.value: {
        "comparison": {
            "example_type": "side_by_side_contrast_example",
            "purpose": "Use the same setup to show how two ideas behave differently.",
        },
        "worked_example": {
            "example_type": "classification_example",
            "purpose": "Show how to decide which concept applies.",
        },
        "practice": {
            "example_type": "classification_transfer_prompt",
            "purpose": "Ask learner to classify a new scenario.",
        },
    },
    TopicType.PROBLEM_SOLVING_APPLICATION.value: {
        "process": {
            "example_type": "none",
            "purpose": "Explain the general recognition workflow and decision points without solving one concrete problem.",
        },
        "worked_example": {
            "example_type": "pattern_application_example",
            "purpose": "Show how to recognize and apply the reusable pattern.",
        },
        "edge_case": {
            "example_type": "pattern_boundary_example",
            "purpose": "Show where the pattern needs adjustment or fails.",
        },
        "practice": {
            "example_type": "transfer_problem_example",
            "purpose": "Test the same pattern in a different-looking problem.",
        },
    },
    TopicType.SCIENCE_MECHANISM.value: {
        "process": {
            "example_type": "none",
            "purpose": "Explain the general cause-effect mechanism and variable roles without instantiating one perturbation example.",
        },
        "worked_example": {
            "example_type": "cause_effect_chain_example",
            "purpose": "Show how a change moves through the mechanism.",
        },
        "edge_case": {
            "example_type": "perturbation_example",
            "purpose": "Show how the mechanism changes under a different condition.",
        },
        "practice": {
            "example_type": "mechanism_prediction_prompt",
            "purpose": "Ask learner to predict what changes when one condition changes.",
        },
    },
    TopicType.STUDY_PATH_INTRODUCTION.value: {},
}


VISUAL_FAMILY_DEFINITIONS: dict[str, dict[str, Any]] = {
    "none": {
        "purpose": "No visual is needed for this card.",
        "best_for": ["purely verbal cards where a visual would not reduce cognitive load"],
        "should_incorporate": ["leave visual_description empty"],
        "avoid": ["decorative visuals"],
    },
    "node_link_diagram": {
        "purpose": "Show relationships between connected entities and how movement or traversal flows through the structure.",
        "best_for": ["BSTs", "binary trees", "linked lists", "graphs", "DFS/BFS", "recursion trees", "dependency structures", "network flows"],
        "should_incorporate": ["nodes with labels", "edges/connections", "directional arrows when useful", "traversal/order highlighting", "active/current node", "visited state", "grouped or layered structure", "minimal visual clutter", "persistent structure across cards when possible"],
        "avoid": ["giant dense graphs", "decorative node explosions", "unrelated labels"],
        "example": "Irregular BST with traversal path highlighted step by step.",
    },
    "state_change": {
        "purpose": "Show one before/action/after state transition.",
        "best_for": ["algorithm state", "data-structure updates", "array or pointer changes", "code execution"],
        "should_incorporate": ["before state", "action/change", "after state", "changed trackers"],
        "avoid": ["multiple unrelated state transitions in one visual"],
    },
    "array_state_diagram": {
        "purpose": "Show one or more arrays/lists with active indices, pointers, windows, ranges, split/merge levels, and computed annotations.",
        "best_for": ["sliding window", "two pointers", "prefix sums", "binary search", "array scans", "hash map plus array problems", "partitioning", "merge steps", "DP arrays"],
        "should_incorporate": ["array cells with values", "index labels", "named pointers such as left/right/i/j", "highlighted window or range", "computed annotations such as sum or need", "multiple array rows when showing split/merge levels", "before/after pointer movement when useful"],
        "avoid": ["arrays longer than 16 cells", "unlabeled pointer arrows", "too many overlapping ranges"],
        "example": "Merge sort overview showing one array splitting into smaller arrays and merging back into one sorted array.",
    },
    "graph_chart": {
        "purpose": "Show quantitative or mathematical relationships visually.",
        "best_for": ["runtime complexity", "probability distributions", "trends", "statistics", "calculus", "economics", "growth/decay", "coordinate geometry"],
        "should_incorporate": ["axes", "labels", "key points", "curves/bars/lines", "highlighted regions when important", "focused data points", "annotations explaining meaning"],
        "avoid": ["overloaded charts", "meaningless random data", "too many plotted elements"],
        "example": "Runtime growth comparison between O(n), O(log n), and O(n^2).",
    },
    "step_flow": {
        "purpose": "Show sequential progression through a process or transformation.",
        "best_for": ["algorithms", "procedures", "workflows", "proofs", "state machines", "transformations", "multi-step reasoning"],
        "should_incorporate": ["ordered steps", "arrows/transitions", "current active step", "optional branching", "concise explanation per step", "mini visual or compact formula when useful", "visual continuity between states", "before/after transitions"],
        "avoid": ["giant paragraphs inside steps", "too many simultaneous branches"],
        "example": "Merge sort splitting, recursive sorting, then merging.",
    },
    "formula_card": {
        "purpose": "Break formulas into understandable components and meaning.",
        "best_for": ["algebra", "physics", "probability", "statistics", "engineering", "calculus"],
        "should_incorporate": ["formula", "symbol breakdown", "variable meaning", "when to use", "visual grouping", "plain-English interpretation", "annotated substitution when useful"],
        "avoid": ["giant derivations", "unexplained notation", "excessive symbolic density"],
        "example": "Quadratic formula with each term explained.",
    },
    "comparison_table": {
        "purpose": "Show two or more ideas under the same criteria so differences are easy to scan.",
        "best_for": ["compare/distinguish", "algorithm comparisons", "method selection", "case comparison"],
        "should_incorporate": ["shared criteria", "idea A result", "idea B result", "deciding difference", "minimal rows"],
        "avoid": ["large text-heavy tables", "criteria that do not change the learner's decision"],
        "example": "Same graph traced with BFS queue behavior and DFS stack behavior side by side.",
    },
    "circuit_diagram": {
        "purpose": "Show hardware, electrical, or digital logic connections.",
        "best_for": ["circuits", "digital logic", "gates", "hardware systems", "signal flow"],
        "should_incorporate": ["components", "labeled wires", "current/signal direction", "grouped modules", "simple readable layout"],
        "avoid": ["unnecessary engineering-level detail for beginner lessons"],
        "example": "AND/OR gate combination showing signal propagation.",
    },
    "misconception": {
        "purpose": "Contrast wrong reasoning with correct reasoning.",
        "best_for": ["common mistakes", "debugging", "misconceptions", "proof errors", "incorrect mental models"],
        "should_incorporate": ["wrong interpretation/state", "correct interpretation/state", "why wrong seems plausible", "exact correction", "visual comparison", "highlighted difference"],
        "avoid": ["vague 'this is wrong'", "no explanation for why a learner would think it"],
        "example": "Incorrect BFS traversal caused by stack-like behavior vs correct queue behavior.",
    },
    "causal_chain": {
        "purpose": "Show cause-and-effect progression through a system.",
        "best_for": ["science", "economics", "systems", "biology", "networking", "feedback systems"],
        "should_incorporate": ["starting condition", "cause -> effect chain", "directional relationships", "changed variable", "propagated effects", "final outcome"],
        "avoid": ["disconnected events", "unexplained jumps"],
        "example": "How increasing temperature changes pressure in a gas system.",
    },
    "spatial": {
        "purpose": "Show geometric or spatial relationships visually.",
        "best_for": ["geometry", "vectors", "transformations", "physics", "molecular structures", "anatomy"],
        "should_incorporate": ["spatial orientation", "labels", "dimensions/angles when relevant", "movement/transformation", "highlighted relationships"],
        "avoid": ["cluttered annotations"],
        "example": "Vector addition with arrows and resultant vector.",
    },
    "source_annotation": {
        "purpose": "Bridge explanation to uploaded or source material.",
        "best_for": ["lecture slides", "PDFs", "screenshots", "research papers", "diagrams"],
        "should_incorporate": ["highlighted source regions", "annotations", "callouts", "focus area", "concise explanation"],
        "avoid": ["over-annotating entire source"],
        "example": "Annotated lecture slide explaining a highlighted recursion diagram.",
    },
    "path_progress": {
        "purpose": "Show learning progression and conceptual position.",
        "best_for": ["study path navigation", "roadmap", "prerequisites", "mastery tracking", "review systems"],
        "should_incorporate": ["current position", "completed topics", "next topics", "dependencies", "weak/review areas", "progress indicators"],
        "avoid": ["giant overwhelming graphs"],
        "example": "Tree traversal topic highlighted within a larger DFS/BFS learning path.",
    },
    "topic_snapshot": {
        "purpose": "Visual image of the topic with no descriptions (for example for a topic on binary search trees want an image of a binary search tree).",
        "best_for": ["background intro cards", "topic identification", "algorithm or structure at a glance"],
        "should_incorporate": ["central concept label", "1-3 satellite labels MAXIMUM", "structural or role labels only"],
        "avoid": ["descriptions or explanations inside visual", "more than 3 labels", "repeating the text panel"],
        "example": "BST at center; three satellites: sorted order, left<root, right>root.",
    },
    "concept_snapshot": {
        "purpose": "Show the internal structure or anatomy of a concept with labeled key parts — no explanatory text.",
        "best_for": ["data structures", "named structure parts", "concept-anatomy questions"],
        "should_incorporate": ["central object or structure name", "3-5 labeled key parts", "structural relationship labels"],
        "avoid": ["definitions inside visual", "more than 5 labels", "prose or explanations"],
        "example": "Heap at center; root, left child, right child, heap-property satellites.",
    },
    "edge_case_snapshot": {
        "purpose": "Show a boundary condition with an extremely simple visual — empty structure or a single node.",
        "best_for": ["empty input", "null or single-element boundary", "degenerate structure cases"],
        "should_incorporate": ["empty structure OR single node only", "0-2 labels maximum"],
        "avoid": ["multiple nodes", "complex structure", "explanatory text inside visual"],
        "example": "Empty BST (null root) or single-node tree.",
    },
    "progressive_step_flow": {
        "purpose": "Show a process where only the active step is expanded; all other steps appear as compact chips.",
        "best_for": ["algorithm stages", "procedural steps", "sequential processes that advance card-by-card"],
        "should_incorporate": ["ordered steps", "active step expanded with mini_visual cue", "inactive steps as compact name-only chips"],
        "avoid": ["descriptions inside inactive steps", "equal visual weight for all steps", "large text blocks"],
        "example": "Merge Sort: [Split chip] [Sort Left chip] [SORT RIGHT expanded with array visual] [Merge chip].",
    },
    "relationship_map": {
        "purpose": "Show term hierarchy and part relationships using labels only — definitions stay in the text panel.",
        "best_for": ["terminology organization", "named parts of a structure", "part-whole relationships", "component roles"],
        "should_incorporate": ["parent concept", "child or related terms", "1-word relationship labels such as has, is, uses, calls", "tree or grouped layout"],
        "avoid": ["definitions inside visual", "paragraphs", "more than 6 nodes", "restating text panel content"],
        "example": "BST has Root, has Parent, has Child, has Leaf — labels only.",
    },
    "code_trace": {
        "purpose": "Show a code block as the primary focus area, with the currently active line/block highlighted. Used in two modes: (1) GROWING — code_walkthrough cards show the implementation-so-far and add exactly one new non-empty code line per card; (2) EXECUTION — coding_implementation worked_example cards show the COMPLETE program with only the executing line/block highlighted as the example runs.",
        "best_for": ["coding_implementation code_walkthrough cards", "coding_implementation worked_example cards", "line-by-line construction", "execution traces", "recursion stack traces"],
        "should_incorporate": [
            "code block as the left-side focus",
            "active line/block highlight that moves between steps",
            "max_line (how far into the code is visible) when revealing progressively",
            "variable/state panel beside or below the code when relevant",
            "call stack for recursive code",
            "indentation preserved across cards",
            "complete final code on the LAST code_walkthrough card and on every worked_example card",
        ],
        "avoid": [
            "duplicating raw code in the bullet text",
            "highlighting more than one functional block at the same time",
            "splitting one logical code slice across two cards",
            "hiding the surrounding context the active line needs",
            "showing code that hasn't been introduced yet on a walkthrough card",
        ],
        "example": "DFS implementation with `while stack:` highlighted and the stack variable shown beside it.",
    },
    "practice_feedback": {
        "purpose": "Visually explain why a learner answer or process was correct or incorrect.",
        "best_for": ["adaptive feedback", "mistake repair", "reasoning correction", "reconstruction"],
        "should_incorporate": ["learner answer state", "correct answer state", "highlighted mistake", "corrected reasoning", "next-step repair"],
        "avoid": ["generic incorrect feedback"],
        "example": "Highlighting where a learner incorrectly updated a sliding-window boundary.",
    },
}


VISUAL_CARD_RULES: dict[str, dict[str, dict[str, Any]]] = {
    TopicType.STUDY_PATH_INTRODUCTION.value: {
        "background": {"visual_type": "node_link_diagram | array_state_diagram | graph_chart", "purpose": "Show the actual system, process, or structure for the central concept, such as divide-and-conquer splitting/solving/combining, merge sort splitting and merging an array, a graph algorithm on a graph, or a probability topic on a curve."},
        "roadmap": {"visual_type": "none", "purpose": ("Show the conceptual roadmap only: the major ideas, variants, or methods "
            "the learner will understand by the end. Do not mirror the study path topic "
            "list. Merge implementation topics into their underlying algorithm concept. "
            "Exclude coding-only cards unless they add a new conceptual distinction."
        )},
    },
    TopicType.CONCEPT_INTUITION.value: {
        "background": {"visual_type": "node_link_diagram | array_state_diagram | spatial | concept_snapshot", "purpose": "Show the concept itself — a BST, a deque, a probability curve — so the learner immediately sees what they are studying."},
        "components_terms": {"visual_type": "none", "purpose": "Show the terms as labeled parts of one structure; definitions stay in the text panel."},
        "worked_example": {"visual_type": "concept_snapshot | spatial | state_change | node_link_diagram | array_state_diagram | graph_chart", "purpose": "Show the concept applied in a concrete situation; pick whichever family best fits how the concept manifests in this example."},
        "edge_case": {"visual_type": "none", "purpose": "Show a near-empty or boundary instance of the concept, or contrast a tempting wrong reading with the correct one."},
        "practice": {"visual_type": "none", "purpose": "Reserve a prediction or transfer focus area that becomes adaptive feedback after answering."},
    },
    TopicType.TERMINOLOGY_COMPONENTS.value: {
        "background": {"visual_type": "node_link_diagram | array_state_diagram | concept_snapshot", "purpose": "Show the concept structure so terms have a visual home — a real BST, array, or diagram rather than abstract labels."},
        "components_terms": {"visual_type": "none", "purpose": "Show the terms as labeled parts of one structure; definitions stay in the text panel."},
        "worked_example": {"visual_type": "relationship_map | concept_snapshot | source_annotation", "purpose": "Highlight terms within a real structure or example. Use source_annotation ONLY when there is an uploaded diagram/screenshot to annotate."},
        "edge_case": {"visual_type": "none", "purpose": "Show a tricky or overlapping term boundary case."},
        "practice": {"visual_type": "none", "purpose": "Reserve a term-identification focus area that becomes adaptive feedback after answering."},
    },
    TopicType.PROCESS_WALKTHROUGH.value: {
        "background": {"visual_type": "node_link_diagram | array_state_diagram | topic_snapshot", "purpose": "Show the actual structure or data the process operates on — an array being sorted, a graph being traversed — so the learner sees the subject before the steps begin."},
        "components_terms": {"visual_type": "none", "purpose": "Show the named parts of the process or its inputs/outputs as labels."},
        # Process cards stay text-only here: the worked_example cards already
        # carry the structural visual, and a duplicate visual on process
        # creates redundancy (this was a deliberate user decision).
        "process": {"visual_type": "none", "purpose": "Process cards render as text-only; the bullet structure is the explanation. The worked_example cards carry the structural visual for this topic type."},
        "worked_example": {"visual_type": "node_link_diagram | array_state_diagram | state_change", "purpose": "Show process execution on a meaningful example with the structure the process acts on."},
        "edge_case": {"visual_type": "none", "purpose": "Show the minimal boundary state and exactly what behavior changes."},
        "practice": {"visual_type": "none", "purpose": "Reserve a process-prediction focus area that becomes adaptive feedback after answering."},
    },
    TopicType.ALGORITHM_WALKTHROUGH.value: {
        "background": {"visual_type": "node_link_diagram | array_state_diagram | topic_snapshot", "purpose": "Show the actual structure the algorithm operates on — a BST being traversed, an array being sorted — so the learner immediately sees the concept in action."},
        "components_terms": {"visual_type": "none", "purpose": "Show algorithm-related terms (frontier, visited, current) as labels on the structure."},
        # Process cards stay text-only: worked_example carries the structural trace.
        "process": {"visual_type": "none", "purpose": "Process cards render as text-only; the bullet structure is the explanation. The worked_example cards carry the structural trace visual for this topic type."},
        "worked_example": {"visual_type": "node_link_diagram | array_state_diagram", "purpose": "Show the algorithm trace on the actual structure. Reuse the SAME base structure across every continuation card — only the highlights and trackers change."},
        "comparison": {"visual_type": "comparison_table | step_flow | node_link_diagram | array_state_diagram", "purpose": "Show the same input under two related algorithms. For BFS vs DFS or similar, prefer a same-structure trace pair over a text-only table."},
        "edge_case": {"visual_type": "none", "purpose": "Show the boundary structure (empty, single node, disconnected) and how the algorithm's behavior changes."},
        "practice": {"visual_type": "none", "purpose": "Reserve a trace-prediction focus area that becomes adaptive feedback after answering."},
    },
    TopicType.DATA_STRUCTURE_OPERATION.value: {
        "background": {"visual_type": "node_link_diagram | array_state_diagram | concept_snapshot", "purpose": "Show the actual data structure — a BST, heap, deque, linked list — so the learner sees what they are operating on before the operation begins."},
        "components_terms": {"visual_type": "none", "purpose": "Show the labeled parts of the structure (root, child, sentinel, bucket)."},
        # Process cards stay text-only: worked_example carries the visual.
        "process": {"visual_type": "none", "purpose": "Process cards render as text-only; the bullet structure is the explanation. The worked_example cards carry the before/after structure visual for this topic type."},
        "worked_example": {"visual_type": "node_link_diagram | array_state_diagram", "purpose": "Show before, action, and after states of the data structure with the invariant preserved across steps. Reuse the SAME structure across continuation cards."},
        "edge_case": {"visual_type": "edge_case_snapshot | node_link_diagram | array_state_diagram", "purpose": "Show the boundary structure (empty, single element, full) and how the operation handles it."},
        "practice": {"visual_type": "practice_feedback", "purpose": "Reserve an operation-prediction focus area that becomes adaptive feedback after answering."},
    },
    TopicType.CODING_IMPLEMENTATION.value: {
        "background": {"visual_type": "node_link_diagram | array_state_diagram | topic_snapshot", "purpose": "Show the actual data structure or algorithm being implemented — a BST, an array being partitioned, a graph — so the learner sees what the code will manipulate."},
        "components_terms": {"visual_type": "relationship_map | concept_snapshot", "purpose": "Show code-related terms (variable, helper, base case) as labels on the implementation skeleton."},
        "process": {"visual_type": "none", "purpose": "Process cards render as text-only; code_walkthrough cards carry the code visual for this topic type."},
        "code_walkthrough": {
            "visual_type": "code_trace",
            "purpose": "Use the implementation-so-far code block as the left-side focus; each adjacent card adds and highlights exactly one next non-empty code line.",
        },
        "worked_example": {"visual_type": "code_trace | node_link_diagram | array_state_diagram", "purpose": "Show execution state on a meaningful input. code_trace shows the complete code with the executing line highlighted; pair with node_link_diagram or array_state_diagram when the runtime structure is visible. Reuse the same structure across continuation cards."},
        "edge_case": {"visual_type": "code_trace | edge_case_snapshot | state_change", "purpose": "Show the boundary input and which code branch handles it (or fails to)."},
        "practice": {"visual_type": "practice_feedback", "purpose": "Reserve a coding focus area that becomes adaptive feedback after answering."},
    },
    TopicType.MATH_FORMULA_METHOD.value: {
        "background": {"visual_type": "graph_chart | spatial | topic_snapshot", "purpose": "Show the mathematical object the formula applies to — a probability curve, a geometric figure, or a coordinate space — so the learner sees the domain before the formula is introduced."},
        "components_terms": {"visual_type": "relationship_map | concept_snapshot | formula_card", "purpose": "Show the symbols and their meanings as labeled parts."},
        "formula_breakdown": {"visual_type": "formula_card", "purpose": "Break the formula into symbols, meanings, and use conditions."},
        # Process cards stay text-only: formula_breakdown + worked_example carry the visual content.
        "process": {"visual_type": "none", "purpose": "Process cards render as text-only; the bullet structure is the explanation. The formula_breakdown and worked_example cards carry the visual content for this topic type."},
        "worked_example": {"visual_type": "step_flow | graph_chart | formula_card", "purpose": "Show setup, calculation, and interpretation visually."},
        "edge_case": {"visual_type": "formula_card | graph_chart", "purpose": "Show where the formula or method stops applying or changes behavior."},
        "practice": {"visual_type": "practice_feedback", "purpose": "Reserve a math-transfer focus area that becomes adaptive feedback after answering."},
    },
    TopicType.PROOF_REASONING.value: {
        "background": {"visual_type": "node_link_diagram | topic_snapshot", "purpose": "Show the mathematical object or structure being reasoned about — a graph, a tree, a set diagram — so the learner sees what the proof is operating on."},
        "components_terms": {"visual_type": "relationship_map | concept_snapshot", "purpose": "Show the named objects in the proof setup (givens, hypotheses, target)."},
        "proof_plan": {"visual_type": "progressive_step_flow", "purpose": "Show the proof route from givens to target with the active step expanded."},
        # Proof process cards CAN have a visual: a progressive step flow showing
        # the proof state changing under each justified step is genuinely
        # different from the worked_example, which traces a specific case.
        "process": {"visual_type": "progressive_step_flow | causal_chain", "purpose": "Show the proof state advancing one valid step at a time; the active step shows the current claim plus the justification."},
        "worked_example": {"visual_type": "progressive_step_flow | causal_chain | node_link_diagram | formula_card", "purpose": "Show the dependency chain or step-by-step transformation of the proof on a specific case."},
        "edge_case": {"visual_type": "misconception | formula_card", "purpose": "Show a tempting but invalid proof step contrasted with the correct one."},
        "practice": {"visual_type": "practice_feedback", "purpose": "Reserve a proof-step focus area that becomes adaptive feedback after answering."},
    },
    TopicType.COMPARE_DISTINGUISH.value: {
        "background": {"visual_type": "comparison_table | node_link_diagram | array_state_diagram", "purpose": "Show the two concepts side-by-side or as distinct structures so the learner immediately sees the key difference being studied."},
        "components_terms": {"visual_type": "relationship_map | concept_snapshot", "purpose": "Show the deciding criteria as labeled axes."},
        "comparison": {"visual_type": "comparison_table | node_link_diagram | array_state_diagram", "purpose": "Show shared setup and separating dimensions. For behavioral comparisons (BFS vs DFS) prefer same-input trace pairs over a text-only table."},
        "worked_example": {"visual_type": "comparison_table | node_link_diagram | array_state_diagram | state_change", "purpose": "Show the same setup under both concepts. For behavioral differences a side-by-side trace beats a text table."},
        "edge_case": {"visual_type": "misconception | edge_case_snapshot", "purpose": "Show a case where learners commonly confuse the two ideas."},
        "practice": {"visual_type": "practice_feedback", "purpose": "Reserve a classification focus area that becomes adaptive feedback after answering."},
    },
    TopicType.PROBLEM_SOLVING_APPLICATION.value: {
        "background": {"visual_type": "node_link_diagram | array_state_diagram | topic_snapshot", "purpose": "Show the pattern being applied — a sliding window on an array, a graph for shortest path — so the learner sees the structure before the solving technique is introduced."},
        "components_terms": {"visual_type": "relationship_map | concept_snapshot", "purpose": "Show the pattern's named components (window, frontier, residue)."},
        # Process cards stay text-only: worked_example carries the structural visual.
        "process": {"visual_type": "none", "purpose": "Process cards render as text-only; the bullet structure is the explanation. The worked_example cards carry the pattern-application visual for this topic type."},
        "worked_example": {"visual_type": "node_link_diagram | array_state_diagram | state_change | step_flow", "purpose": "Show pattern application on real data."},
        "edge_case": {"visual_type": "edge_case_snapshot | state_change", "purpose": "Show where the pattern needs adjustment or breaks down."},
        "practice": {"visual_type": "practice_feedback", "purpose": "Reserve a transfer-problem focus area that becomes adaptive feedback after answering."},
    },
    TopicType.SCIENCE_MECHANISM.value: {
        "background": {"visual_type": "node_link_diagram | causal_chain | topic_snapshot", "purpose": "Show the mechanism's structure or connected components — a network, a layered system, or interacting parts — so the learner sees the system before the mechanism is explained."},
        "components_terms": {"visual_type": "relationship_map | concept_snapshot", "purpose": "Show the named components of the mechanism."},
        # Mechanism process CAN have a visual: a causal_chain showing the
        # mechanism's flow is genuinely different from a worked_example, which
        # traces a specific perturbation.
        "process": {"visual_type": "causal_chain | progressive_step_flow", "purpose": "Show the mechanism's causal flow with the active link expanded; this is the abstract mechanism, distinct from a specific worked case."},
        "worked_example": {"visual_type": "causal_chain | progressive_step_flow", "purpose": "Show the mechanism in one concrete perturbed case."},
        "edge_case": {"visual_type": "misconception | causal_chain", "purpose": "Show a tempting but incorrect causal story contrasted with the correct one."},
        "practice": {"visual_type": "practice_feedback", "purpose": "Reserve a mechanism-prediction focus area that becomes adaptive feedback after answering."},
    },
}


COMMON_VISUAL_CARD_RULES: dict[str, dict[str, Any]] = {
    "practice": {
        "visual_type": "practice_feedback",
        "deferred_visual_type": "practice_feedback",
        "purpose": "Use a lightweight placeholder focus area during lesson generation; replace with adaptive feedback after the learner answers.",
    },
    "background": {
        "visual_type": "progressive_step_flow | node_link_diagram | array_state_diagram | graph_chart | topic_snapshot",
        "purpose": "Show the actual concept, structure, or object being studied — a graph, an array, a curve — so the learner immediately sees what they are about to learn before reading any text.",
    },
    "process": {
        "visual_type": "none",
        "purpose": "Process cards render as text-only with no visual; the bullet structure is the explanation.",
    },
}


# Temporary hybrid-v2 routing policy:
# legacy topic/card structure remains canonical, but only these card roles
# may request a v2 visual. All other card roles render text-only for now.
_CURRENT_IMPLEMENTED_VISUALS_BY_CARD_ROLE: dict[str, tuple[str, ...]] = {
    "background": (
        "node_link_diagram",
        "array_state_diagram",
        "graph_chart",
        "formula_card",
        "comparison_table",
        "grid_matrix_diagram",
    ),
    "worked_example": (
        "node_link_diagram",
        "array_state_diagram",
        "graph_chart",
        "formula_card",
        "comparison_table",
        "grid_matrix_diagram",
        "code_trace",
    ),
    "code_walkthrough": ("code_trace",),
}

_DEFAULT_VISUALS_BY_CARD_ROLE: dict[str, str] = {
    "background": "node_link_diagram | array_state_diagram | graph_chart",
    "worked_example": "node_link_diagram | array_state_diagram | graph_chart",
    "code_walkthrough": "code_trace",
}


def _normalize_visual_card_rules_for_hybrid_v2() -> None:
    """Constrain blueprint visual routing to currently supported v2 roles.

    The v2 bridge now uses the blueprint card role as the source of truth for
    whether a legacy card receives a v2 visual. This pass prevents older visual
    experiments on process/components/edge/practice/etc. from becoming active
    while keeping background, worked_example, and code_walkthrough routed to
    implemented v2 visual families only.
    """

    def normalized_visual_type(card_key: str, raw_visual_type: str) -> str:
        allowed = _CURRENT_IMPLEMENTED_VISUALS_BY_CARD_ROLE.get(card_key)
        if not allowed:
            return "none"
        requested = [
            part.strip()
            for part in raw_visual_type.split("|")
            if part.strip() and part.strip().lower() != "none"
        ]
        kept = [
            part
            for part in requested
            if part.strip().lower() in allowed
        ]
        if kept:
            return " | ".join(kept)
        return _DEFAULT_VISUALS_BY_CARD_ROLE[card_key]

    for topic_rules in VISUAL_CARD_RULES.values():
        for card_key, rule in topic_rules.items():
            if not isinstance(rule, dict):
                continue
            rule["visual_type"] = normalized_visual_type(
                card_key,
                str(rule.get("visual_type") or ""),
            )
            if rule["visual_type"] == "none":
                rule["purpose"] = f"{card_key} cards render as text-only for now."

    for card_key, rule in COMMON_VISUAL_CARD_RULES.items():
        if not isinstance(rule, dict):
            continue
        rule["visual_type"] = normalized_visual_type(
            card_key,
            str(rule.get("visual_type") or ""),
        )
        if rule.get("deferred_visual_type"):
            rule["deferred_visual_type"] = rule["visual_type"]
        if rule["visual_type"] == "none":
            rule["purpose"] = f"{card_key} cards render as text-only for now."


_normalize_visual_card_rules_for_hybrid_v2()


OPTIONAL_CARD_USAGE: dict[str, dict[str, dict[str, list[str]]]] = {
    TopicType.CONCEPT_INTUITION.value: {
        "components_terms": {
            "use_when": [
                "the concept has named parts, terms, roles, labels, symbols, or notation needed before the core idea",
                "terms would otherwise appear before being explained",
                "there are at least 3 current-topic terms that genuinely need explanation",
            ],
            "skip_when": [
                "there are fewer than 3 current-topic terms that genuinely need explanation",
                "needed terms can be explained naturally inside background",
                "the card would only repeat known vocabulary",
            ],
        },
        "edge_case": {
            "use_when": [
                "a non-standard case changes how the concept should be understood",
                "learners are likely to overgeneralize from the normal case",
                "practice will test the non-standard case",
            ],
            "skip_when": [
                "the case is rare, advanced, or outside the topic scope",
                "the edge case can be mentioned briefly in another card",
            ],
        },
    },
    TopicType.TERMINOLOGY_COMPONENTS.value: {
    },
    TopicType.PROCESS_WALKTHROUGH.value: {
        "components_terms": {
            "use_when": [
                "the process depends on named inputs, variables, roles, conditions, or notation",
                "the learner must identify problem parts before applying the steps",
                "there are at least 3 current-topic terms that genuinely need explanation",
            ],
            "skip_when": [
                "there are fewer than 3 current-topic terms that genuinely need explanation",
                "the process has no special terms beyond the main idea",
                "terms can be explained inside the process card without slowing momentum",
            ],
        },
        "edge_case": {
            "use_when": [
                "a condition, domain issue, or special input changes the process",
                "the method breaks or changes under a common boundary case",
                "the edge case will appear in practice",
            ],
            "skip_when": [
                "the edge case is rare or unrelated to the topic goal",
                "the change can be handled in one bullet on the process card",
            ],
        },
    },
    TopicType.ALGORITHM_WALKTHROUGH.value: {
        "edge_case": {
            "use_when": [
                "the algorithm behaves differently for dead ends, repeated nodes, missing paths, empty input, duplicates, or boundaries",
                "the edge case is common in homework, exams, interviews, or real use",
                "practice asks the learner to handle the edge case",
            ],
            "skip_when": [
                "the edge case introduces complexity not needed for the current algorithm goal",
                "the case can be covered cleanly inside the worked example",
            ],
        },
        "comparison": {
            "use_when": [
                "a related algorithm has already been taught",
                "one brief distinction prevents a likely misconception",
                "the comparison is a small clarification, not the topic's main goal",
            ],
            "skip_when": [
                "the related algorithm has not been introduced",
                "the comparison deserves its own compare_distinguish topic",
                "the comparison distracts from tracing the current algorithm",
            ],
        },
    },
    TopicType.DATA_STRUCTURE_OPERATION.value: {
        "edge_case": {
            "use_when": [
                "the operation behaves differently for a structurally important case",
                "case recognition is part of the operation skill",
                "empty, one-child, two-child, collision, duplicate, or boundary cases matter",
            ],
            "skip_when": [
                "the case is unrelated to the operation goal",
                "the case can be handled briefly in process",
            ],
        },
    },
    TopicType.CODING_IMPLEMENTATION.value: {
        "components_terms": {
            "use_when": [
                "the implementation has several variables, helper functions, parameters, data structures, or return values",
                "code names would be confusing before the walkthrough",
                "there are at least 3 implementation-specific terms that genuinely need explanation",
            ],
            "skip_when": [
                "there are fewer than 3 implementation-specific terms that genuinely need explanation",
                "variables are obvious and can be explained in code_walkthrough",
                "the card would become a syntax tutorial",
            ],
        },
        "edge_case": {
            "use_when": [
                "special input changes code behavior or is necessary for correctness",
                "empty, null, one-element, duplicate, boundary, or no-solution cases matter",
                "tests would fail without handling this case",
            ],
            "skip_when": [
                "the edge case is unrelated to the implementation goal",
                "the implementation plan can cover it in one concise point",
            ],
        },
    },
    TopicType.MATH_FORMULA_METHOD.value: {
        "edge_case": {
            "use_when": [
                "the formula or method has conditions, restrictions, undefined cases, or boundary cases",
                "the method changes or stops applying under a common condition",
                "practice requires condition checking",
            ],
            "skip_when": [
                "the restriction is advanced or outside the current goal",
                "the condition can be covered in components_terms or formula_breakdown",
            ],
        },
    },
    TopicType.PROOF_REASONING.value: {
        "components_terms": {
            "use_when": [
                "the proof uses variables, definitions, assumptions, givens, allowed facts, or notation that must be named clearly",
                "the learner must distinguish what is given from what must be shown",
                "there are at least 3 proof-specific terms that genuinely need explanation",
            ],
            "skip_when": [
                "there are fewer than 3 proof-specific terms that genuinely need explanation",
                "the claim is simple and givens/target are obvious from background",
                "definitions are already established by earlier topics",
            ],
        },
    },
    TopicType.COMPARE_DISTINGUISH.value: {
        "components_terms": {
            "use_when": [
                "the comparison needs criteria, shared vocabulary, or setup terms",
                "learners need dimensions before seeing the distinction",
                "there are at least 3 comparison-specific terms or criteria that genuinely need explanation",
            ],
            "skip_when": [
                "there are fewer than 3 comparison-specific terms or criteria that genuinely need explanation",
                "the comparison dimensions are obvious from the ideas being compared",
                "definitions would duplicate earlier topics",
            ],
        },
    },
    TopicType.PROBLEM_SOLVING_APPLICATION.value: {
        "edge_case": {
            "use_when": [
                "the pattern almost fits but fails",
                "a variation requires adjustment",
                "a boundary condition changes the approach",
                "the case is important for transfer or practice",
            ],
            "skip_when": [
                "the variation is too advanced or unrelated to the current pattern",
                "the case can be mentioned briefly in process",
            ],
        },
    },
    TopicType.SCIENCE_MECHANISM.value: {
        "edge_case": {
            "use_when": [
                "changing one variable, component, condition, or step changes the mechanism outcome",
                "a perturbation helps the learner predict cause and effect",
                "graph, data, or model interpretation depends on changed conditions",
            ],
            "skip_when": [
                "the changed condition is advanced or outside the current mechanism",
                "the variation does not change the causal story",
            ],
        },
    },
    TopicType.STUDY_PATH_INTRODUCTION.value: {
        # NOTE: there is no "components_terms" entry here on purpose.
        # The STUDY_PATH_INTRODUCTION blueprint's `avoid` list explicitly
        # forbids the components_terms card on intro topics ("vocabulary
        # belongs in the subtopic that introduces the term, not in the
        # intro"). Defining usage rules here would contradict the blueprint
        # and the LLM would get conflicting guidance.
        "roadmap": {
            "use_when": [
                "the path covers multiple subtypes of one central idea and a one-sentence preview of each subtopic's key concept would help the learner orient",
                "the subtopics are close enough that the learner benefits from knowing what distinguishes each one before diving in",
            ],
            "skip_when": [
                "the upcoming topics are largely independent of each other",
                "the topic titles already make each subtopic's key concept obvious",
            ],
        },
    },
}


def sequence(*items: str) -> list[str]:
    return list(items)


TOPIC_BLUEPRINTS: dict[str, Blueprint] = {
    TopicType.CONCEPT_INTUITION.value: {
        "name": "Concept / Intuition",
        "description": "Teach what one idea means, why it exists, how to picture it, and how to apply it.",
        "default_card_sequence": sequence(
            "background",
            "components_terms",
            "worked_example",
            "edge_case",
            "practice",
        ),
        "optional_cards": ["components_terms", "edge_case"],
        "preferred_question_types": ["short_answer", "multiple_choice"],
        "avoid": ["Do not drift into sibling topics or implementation unless requested."],
        "combination_rules": [],
    },
    TopicType.TERMINOLOGY_COMPONENTS.value: {
        "name": "Terminology / Components",
        "description": "Teach related words, parts, symbols, labels, or component roles in context.",
        "default_card_sequence": sequence(
            "background",
            "components_terms",
            "worked_example",
            "practice",
        ),
        "optional_cards": [],
        "preferred_question_types": ["short_answer", "multiple_choice"],
        "avoid": ["Do not create random glossary lists with no structure."],
        "combination_rules": [],
    },
    TopicType.PROCESS_WALKTHROUGH.value: {
        "name": "Process Walkthrough",
        "description": "Teach a repeatable non-code, non-CS-algorithm sequence of steps.",
        "default_card_sequence": sequence(
            "background",
            "components_terms",
            "process",
            "worked_example",
            "edge_case",
            "practice",
        ),
        "optional_cards": ["components_terms", "edge_case"],
        "preferred_question_types": ["short_answer", "multiple_choice", "math_input"],
        "avoid": ["Do not teach memorized steps without explaining why each step happens."],
        "combination_rules": [],
    },
    TopicType.ALGORITHM_WALKTHROUGH.value: {
        "name": "Algorithm Walkthrough",
        "description": "Trace algorithm state changes, decisions, and final output.",
        "default_card_sequence": sequence(
            "background",
            "components_terms",
            "process",
            "worked_example",
            "edge_case",
            "comparison",
            "practice",
        ),
        "optional_cards": ["edge_case", "comparison"],
        "preferred_question_types": ["trace", "short_answer", "multiple_choice"],
        "avoid": ["Do not include full code before the algorithm behavior has been explained."],
        "combination_rules": ["Append coding_implementation by default after the walkthrough unless the learner explicitly asks for no code."],
    },
    TopicType.DATA_STRUCTURE_OPERATION.value: {
        "name": "Data Structure Operation",
        "description": "Perform one operation while preserving a data-structure invariant.",
        "default_card_sequence": sequence(
            "background",
            "components_terms",
            "process",
            "worked_example",
            "edge_case",
            "practice",
        ),
        "optional_cards": ["edge_case"],
        "preferred_question_types": ["trace", "multiple_choice", "coding"],
        "avoid": ["Do not teach every operation on the same data structure."],
        "combination_rules": [TopicType.CODING_IMPLEMENTATION.value],
    },
    TopicType.CODING_IMPLEMENTATION.value: {
        "name": "Coding Implementation",
        "description": "Turn an already-taught idea, algorithm, formula, process, or operation into working code; teach implementation choices, code construction, and runtime execution, not the algorithm concept itself.",
        "default_card_sequence": sequence(
            "background",
            "components_terms",
            "code_walkthrough",
            "worked_example",
            "edge_case",
            "practice",
        ),
        "continuation_card_sequence": sequence(
            "components_terms",
            "code_walkthrough",
            "worked_example",
            "practice",
        ),
        "continuation_optional_cards": ["components_terms"],
        "optional_cards": ["components_terms", "edge_case"],
        "preferred_question_types": ["coding", "debugging", "short_answer"],
        "avoid": [
            "Do not show large unexplained code dumps.",
            "Do not reteach the algorithm or operation behavior that the preceding walkthrough already taught.",
            "Do not skip code_walkthrough; build the implementation incrementally with code_snippet on every code_walkthrough card.",
            "Do not make worked_example a replay of the algorithm walkthrough; run a concrete input through the completed program and highlight executing code lines/blocks.",
            "When this topic CONTINUES an algorithm_walkthrough or data_structure_operation for the same idea, do NOT include an edge_case card — that preceding topic already covered the identical edge cases; repeating them here is pure duplication.",
        ],
        "combination_rules": [],
    },
    TopicType.MATH_FORMULA_METHOD.value: {
        "name": "Math Formula / Method",
        "description": "Teach formula meaning, symbols, conditions, setup, calculation, and interpretation.",
        "default_card_sequence": sequence(
            "background",
            "components_terms",
            "formula_breakdown",
            "process",
            "worked_example",
            "edge_case",
            "practice",
        ),
        "optional_cards": ["edge_case"],
        "preferred_question_types": ["math_input", "short_answer", "multiple_choice"],
        "avoid": ["Do not use vague formula memorization as the main learning path."],
        "combination_rules": [],
    },
    TopicType.PROOF_REASONING.value: {
        "name": "Proof / Reasoning",
        "description": "Teach claims, assumptions, proof strategy, valid steps, and reasoning traps.",
        "default_card_sequence": sequence(
            "background",
            "components_terms",
            "proof_plan",
            "process",
            "worked_example",
            "practice",
        ),
        "optional_cards": ["components_terms"],
        "preferred_question_types": ["short_answer", "multiple_choice", "math_input"],
        "avoid": ["Do not use symbol-heavy reasoning without plain-English explanation."],
        "combination_rules": [],
    },
    TopicType.COMPARE_DISTINGUISH.value: {
        "name": "Compare / Distinguish",
        "description": "Separate similar ideas by what they share, how they differ, and when each applies.",
        "default_card_sequence": sequence(
            "background",
            "components_terms",
            "comparison",
            "worked_example",
            "practice",
        ),
        "optional_cards": ["components_terms"],
        "preferred_question_types": ["multiple_choice", "short_answer"],
        "avoid": ["Do not compare ideas before both have been introduced."],
        "combination_rules": [],
    },
    TopicType.PROBLEM_SOLVING_APPLICATION.value: {
        "name": "Problem-Solving / Application",
        "description": "Teach reusable problem patterns, strategy choice, application, and transfer.",
        "default_card_sequence": sequence(
            "background",
            "process",
            "worked_example",
            "edge_case",
            "practice",
        ),
        "optional_cards": ["edge_case"],
        "preferred_question_types": ["mixed", "multiple_choice", "coding", "math_input"],
        "avoid": ["Do not give only one solved example with no pattern extraction."],
        "combination_rules": [],
    },
    TopicType.SCIENCE_MECHANISM.value: {
        "name": "Science Concept / Mechanism",
        "description": "Trace components, cause-effect chains, variable changes, and model interpretation.",
        "default_card_sequence": sequence(
            "background",
            "components_terms",
            "process",
            "worked_example",
            "edge_case",
            "practice",
        ),
        "optional_cards": ["edge_case"],
        "preferred_question_types": ["short_answer", "multiple_choice", "math_input"],
        "avoid": ["Do not turn mechanisms into disconnected vocabulary lists."],
        "combination_rules": [],
    },
    TopicType.STUDY_PATH_INTRODUCTION.value: {
        "name": "Study Path Introduction",
        "description": "Frame the overall concept area, orient the learner, and preview the upcoming topics before any subtopic is taught.",
        "default_card_sequence": sequence(
            "background",
            "roadmap",
        ),
        "optional_cards": ["roadmap"],
        "preferred_question_types": [],
        "avoid": [
            "Do not teach any individual subtopic in depth.",
            "Do not include any practice card, practice question, quiz, check, mastery task, or applied exercise.",
            "Do not include a components_terms card — vocabulary belongs in the subtopic that introduces the term, not in the intro.",
            "Do not write vague filler — every card must have a specific orienting purpose.",
            "Do not repeat content that the first real topic will cover.",
        ],
        "combination_rules": [],
    },
}


COMMON_COMBINATIONS: dict[str, list[str]] = {
    TopicType.ALGORITHM_WALKTHROUGH.value: [TopicType.CODING_IMPLEMENTATION.value],
    TopicType.DATA_STRUCTURE_OPERATION.value: [TopicType.CODING_IMPLEMENTATION.value],
    TopicType.CONCEPT_INTUITION.value: [TopicType.MATH_FORMULA_METHOD.value],
    TopicType.PROCESS_WALKTHROUGH.value: [TopicType.MATH_FORMULA_METHOD.value],
    TopicType.PROBLEM_SOLVING_APPLICATION.value: [TopicType.CODING_IMPLEMENTATION.value],
}


def normalize_topic_type_key(topic_type: str | TopicType | None) -> str:
    if isinstance(topic_type, TopicType):
        return topic_type.value

    key = (topic_type or TopicType.CONCEPT_INTUITION.value).strip().lower()
    if key not in TOPIC_BLUEPRINTS:
        return TopicType.CONCEPT_INTUITION.value
    return key


def get_topic_blueprint(topic_type: str | TopicType | None) -> Blueprint:
    key = normalize_topic_type_key(topic_type)
    blueprint = deepcopy(TOPIC_BLUEPRINTS[key])
    blueprint["topic_type"] = key
    blueprint["course_type"] = key
    blueprint["common_rules"] = COMMON_RULES
    blueprint["optional_card_rules"] = deepcopy(OPTIONAL_CARD_USAGE.get(key, {}))
    blueprint["example_type_definitions"] = deepcopy(EXAMPLE_TYPE_DEFINITIONS)
    blueprint["example_card_rules"] = deepcopy(EXAMPLE_CARD_RULES.get(key, {}))
    blueprint["example_usage_by_card"] = {
        card_key: [str(rule.get("example_type") or "none")]
        for card_key, rule in EXAMPLE_CARD_RULES.get(key, {}).items()
    }
    visual_card_rules = deepcopy(VISUAL_CARD_RULES.get(key, {}))
    for card_key, rule in COMMON_VISUAL_CARD_RULES.items():
        if card_key in (blueprint.get("default_card_sequence") or []):
            visual_card_rules.setdefault(card_key, deepcopy(rule))
    blueprint["visual_family_definitions"] = deepcopy(VISUAL_FAMILY_DEFINITIONS)
    blueprint["visual_card_rules"] = visual_card_rules
    return blueprint


def get_topic_blueprints(
    primary_topic_type: str | TopicType | None,
    secondary_topic_types: list[str | TopicType] | None = None,
) -> list[Blueprint]:
    blueprints = [get_topic_blueprint(primary_topic_type)]
    primary_key = blueprints[0]["topic_type"]

    for topic_type in secondary_topic_types or []:
        key = normalize_topic_type_key(topic_type)
        if key != primary_key:
            blueprints.append(get_topic_blueprint(key))

    return blueprints


def get_default_card_sequence(topic_type: str | TopicType | None) -> list[str]:
    return get_topic_blueprint(topic_type)["default_card_sequence"]


def get_continuation_card_sequence(topic_type: str | TopicType | None) -> list[str]:
    blueprint = get_topic_blueprint(topic_type)
    return blueprint.get("continuation_card_sequence") or blueprint["default_card_sequence"]


def list_topic_blueprints() -> list[Blueprint]:
    return [get_topic_blueprint(topic_type) for topic_type in TOPIC_BLUEPRINTS]


# Backward-compatible names while lesson-generation internals migrate.
COURSE_BLUEPRINTS = TOPIC_BLUEPRINTS
normalize_course_type_key = normalize_topic_type_key
get_course_blueprint = get_topic_blueprint
get_course_blueprints = get_topic_blueprints
list_course_blueprints = list_topic_blueprints
