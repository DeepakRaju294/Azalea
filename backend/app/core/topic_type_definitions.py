"""
Canonical definitions for all Azalea topic types.

This version uses the 12-topic-type lesson system:

1. concept_intuition
2. terminology_components
3. process_walkthrough
4. algorithm_walkthrough
5. data_structure_operation
6. coding_implementation
7. math_formula_method
8. proof_reasoning
9. compare_distinguish
10. problem_solving_application
11. science_mechanism
12. study_path_introduction

Import TOPIC_TYPE_DEFINITIONS for structured access, or
call format_topic_types_for_prompt() to get a prompt-ready string.
"""

from __future__ import annotations


TOPIC_TYPE_DEFINITIONS: dict[str, dict] = {
    "concept_intuition": {
        "name": "Concept / Intuition",
        "definition": (
            "Used when the learner needs to understand one idea clearly: what it means, "
            "why it exists, what to picture, what parts it has, how it works at a high level, "
            "and where learners usually get confused."
        ),
        "use_when": [
            "the topic is mainly about understanding one idea",
            "the learner needs a mental model before doing problems",
            "the topic introduces a core concept needed later",
            "the topic is not mainly algorithm tracing, code implementation, proof, formula use, or problem-pattern application",
        ],
        "includes": [
            "what the concept is",
            "why the concept matters when not self-evident",
            "where the concept fits in the bigger picture",
            "components or terms only when needed",
            "core idea / mental model",
            "worked example",
            "common mistake when useful",
            "edge case when useful",
            "application-based practice",
        ],
        "excludes": [
            "full coding implementation unless requested",
            "long historical background",
            "unrelated advanced extensions",
            "many similar concepts compared at once",
            "standalone prerequisite lessons unless needed as earlier topics",
            "popups, interactive links, microchecks, or generated visuals",
        ],
        "typical_card_sequence": [
            "background",
            "components_terms optional",
            "worked_example",
            "edge_case optional",
            "practice",
        ],
        "examples": [
            "What recursion means",
            "What a binary search tree is",
            "What conditional probability means",
            "What a derivative represents",
            "What graph traversal means",
            "What a hash table is",
            "What dynamic programming is for",
        ],
    },
    "terminology_components": {
        "name": "Terminology / Components",
        "definition": (
            "Used when confusion mainly comes from unfamiliar words, parts, symbols, notation, "
            "component roles, or how related pieces fit together."
        ),
        "use_when": [
            "the learner needs to understand a set of related terms",
            "the topic is mainly about parts, labels, roles, notation, or vocabulary",
            "later topics depend on correctly recognizing these terms",
            "the terms should be grouped together instead of split into tiny separate topics",
        ],
        "includes": [
            "what term/component set is being learned",
            "why the terms matter when not self-evident",
            "related term groups",
            "simple meaning of each important term",
            "role of each term",
            "how terms relate to each other",
            "same example labeled progressively",
            "common confusing term pairs when useful",
            "term-use practice",
        ],
        "excludes": [
            "deep procedures",
            "full algorithms",
            "advanced applications",
            "one full topic per tiny term",
            "random glossary lists with no structure",
            "popups, interactive links, microchecks, or generated visuals",
        ],
        "typical_card_sequence": [
            "background",
            "components_terms",
            "worked_example",
            "practice",
        ],
        "examples": [
            "Tree nodes and parent-child structure",
            "Graph vertices, edges, and neighbors",
            "Matrix rows, columns, and entries",
            "Random variables and events",
            "Function parameters and return values",
            "HTML elements and attributes",
            "CPU, memory, disk, and process terminology",
        ],
    },
    "process_walkthrough": {
        "name": "Process Walkthrough",
        "definition": (
            "Used when the learner needs to learn a repeatable sequence of steps that is not primarily "
            "a CS algorithm, code implementation, or data-structure operation."
        ),
        "use_when": [
            "the topic teaches a general procedure or method",
            "the learner must follow steps in order",
            "the process has inputs, conditions, or stages",
            "the main skill is applying the procedure correctly",
            "the topic is step-by-step but not best classified as algorithm_walkthrough, coding_implementation, or math_formula_method",
        ],
        "includes": [
            "what the process is",
            "why the process matters when not self-evident",
            "when to use the process",
            "inputs, pieces, conditions, or roles when needed",
            "core logic behind the process",
            "steps in order",
            "why each step happens",
            "worked example",
            "common mistake when useful",
            "edge case when useful",
            "process-application practice",
        ],
        "excludes": [
            "memorized steps without explanation",
            "formula dumping",
            "multiple unrelated methods",
            "code implementation details unless requested",
            "algorithm trace details when algorithm_walkthrough is a better fit",
            "popups, interactive links, microchecks, or generated visuals",
        ],
        "typical_card_sequence": [
            "background",
            "components_terms optional",
            "process",
            "worked_example",
            "edge_case optional",
            "practice",
        ],
        "examples": [
            "How to solve a Bayes' rule word problem",
            "How to set up induction",
            "How to normalize a vector",
            "How to read a confusion matrix",
            "How to conduct a hypothesis test",
            "How to parse a grammar rule",
            "How to use the chain rule as a procedure",
        ],
    },
    "algorithm_walkthrough": {
        "name": "Algorithm Walkthrough",
        "definition": (
            "Used when the learner needs to understand how an algorithm moves step by step, usually "
            "with changing state, decisions, and an output/order/path/table/result."
        ),
        "use_when": [
            "the topic has ordered algorithm steps",
            "the learner needs to trace what happens next",
            "state changes over time",
            "the topic uses algorithm state such as a queue, stack, visited set, pointer, index, table, or search range",
            "the main skill is following or reasoning about the algorithm correctly",
        ],
        "includes": [
            "what the algorithm is",
            "why the algorithm matters when not self-evident",
            "input and output/result",
            "state/components used",
            "main rule or strategy",
            "step-by-step behavior",
            "comprehensive trace/walkthrough",
            "common tracing mistake when useful",
            "edge case when useful",
            "brief comparison near the end only if it prevents confusion and the related algorithm has already been taught",
            "trace or reasoning practice",
        ],
        "excludes": [
            "full code unless the topic is coding_implementation or a coding continuation",
            "broad concept introduction beyond what is needed",
            "proof of correctness unless proof_reasoning is the goal",
            "standalone comparison topic unless compare_distinguish is truly needed",
            "unrelated advanced algorithm variants",
            "popups, interactive links, microchecks, or generated visuals",
        ],
        "typical_card_sequence": [
            "background",
            "components_terms",
            "process",
            "worked_example",
            "edge_case optional",
            "comparison optional near the end",
            "practice",
        ],
        "examples": [
            "Inorder traversal",
            "Breadth-first search",
            "Depth-first search",
            "Binary search",
            "Dijkstra's algorithm",
            "Merge sort",
            "Dynamic programming table filling",
        ],
    },
    "data_structure_operation": {
        "name": "Data Structure Operation",
        "definition": (
            "Used when the learner needs to understand how an operation changes a data structure "
            "while preserving its rules, properties, or invariants."
        ),
        "use_when": [
            "a data structure changes before/current/after",
            "cases matter",
            "pointer, edge, node, array index, or structural updates matter",
            "the learner must preserve a property like BST ordering, heap order, linked-list connection, or hash table lookup behavior",
            "the topic is about an operation such as insert, delete, search, update, push, pop, enqueue, dequeue, or traversal as a structural operation",
        ],
        "includes": [
            "what operation is being performed",
            "why the operation matters when not self-evident",
            "operation goal",
            "input/action and expected result",
            "structure property or invariant to preserve",
            "parts involved in the operation",
            "operation steps and cases",
            "comprehensive before/after example",
            "validity/invariant check",
            "common invalid update when useful",
            "edge case when operation behavior changes",
            "operation practice",
        ],
        "excludes": [
            "full implementation unless the topic is coding_implementation or a coding continuation",
            "every operation on the data structure",
            "generic concept explanation without structural change",
            "unrelated data structure theory",
            "popups, interactive links, microchecks, or generated visuals",
        ],
        "typical_card_sequence": [
            "background",
            "components_terms",
            "process",
            "worked_example",
            "edge_case optional",
            "practice",
        ],
        "examples": [
            "BST insertion",
            "BST deletion cases",
            "Heap insertion and bubble-up",
            "Heap pop",
            "Linked list deletion",
            "Hash table collision handling",
            "Queue enqueue/dequeue",
            "Stack push/pop",
        ],
    },
    "coding_implementation": {
        "name": "Coding Implementation",
        "definition": (
            "Used when the learner needs to turn an idea, algorithm, formula, process, or data-structure "
            "operation into working code. This type teaches implementation mechanics, not the underlying "
            "algorithm behavior unless that behavior has not been taught anywhere else."
        ),
        "use_when": [
            "the user asks how to code or implement something",
            "implementation choices matter",
            "variables, state, base cases, loops, recursion, or control flow matter",
            "the learner needs to debug, modify, or complete code",
            "the source material focuses on implementation",
        ],
        "includes": [
            "what the code should accomplish",
            "input and output",
            "variables/state needed",
            "helper data structures such as queues, stacks, hash maps, pointers, or recursive calls",
            "base cases or edge cases when relevant",
            "incremental code walkthrough that builds the implementation block by block",
            "program dry run / worked example using the completed code",
            "common implementation bug when useful",
            "implementation practice",
        ],
        "excludes": [
            "reteaching the algorithm walkthrough when the implementation follows that walkthrough",
            "worked examples that replay the abstract algorithm instead of executing the completed program",
            "unrelated syntax tutorials",
            "advanced optimization unless relevant",
            "large unexplained code dumps",
            "starting with code before the learner understands the behavior when behavior is not obvious",
            "popups, interactive links, microchecks, or generated visuals",
        ],
        "typical_card_sequence": [
            "background",
            "components_terms optional",
            "code_walkthrough",
            "worked_example",
            "edge_case optional",
            "practice",
        ],
        "examples": [
            "Implement inorder traversal in C++",
            "Code BFS using a queue",
            "Implement binary search",
            "Write recursive DFS",
            "Implement linked list deletion",
            "Debug a recursive traversal function",
            "Translate Bayes' rule into a Python function",
        ],
    },
    "math_formula_method": {
        "name": "Math Formula / Method",
        "definition": (
            "Used when the learner needs to understand and apply a formula, equation, calculation method, "
            "symbolic procedure, or mathematical setup."
        ),
        "use_when": [
            "formulas, equations, or symbols matter",
            "the learner must set up a method correctly",
            "the learner must calculate, manipulate, substitute, or interpret a result",
            "assumptions, conditions, or domain restrictions affect correctness",
            "the main skill is formula/method application rather than proof construction",
        ],
        "includes": [
            "what formula/method is being learned",
            "why the formula/method matters when not self-evident",
            "what problem it solves",
            "symbols, inputs, and conditions",
            "formula/method meaning",
            "step-by-step use",
            "worked example",
            "common setup/calculation mistake when useful",
            "edge case or condition issue when useful",
            "method-application practice",
        ],
        "excludes": [
            "visual images for equations or formulas",
            "vague formula memorization",
            "long derivations unless needed",
            "full proof logic unless the topic is proof_reasoning",
            "unrelated advanced theorem discussion",
            "popups, interactive links, microchecks, or generated visuals",
        ],
        "implementation_note": (
            "Formulas and equations should use LaTeX. Tables should use styled UI. "
            ""
        ),
        "typical_card_sequence": [
            "background",
            "components_terms",
            "formula_breakdown",
            "process",
            "worked_example",
            "edge_case optional",
            "practice",
        ],
        "examples": [
            "Use Bayes' rule in word problems",
            "Expected value",
            "Calculate variance",
            "Apply the chain rule",
            "Find eigenvalues from a 2x2 matrix",
            "Use the binomial theorem",
            "Solve a recurrence with substitution",
            "Matrix multiplication",
        ],
    },
    "proof_reasoning": {
        "name": "Proof / Reasoning",
        "definition": (
            "Used when the learner needs to justify why something is true, understand proof structure, "
            "track assumptions, validate logical steps, or avoid invalid reasoning."
        ),
        "use_when": [
            "proof structure matters",
            "each step must be justified",
            "the learner must identify what is given and what must be shown",
            "the learner must choose or follow a proof strategy",
            "the topic is about correctness, validity, implication, contradiction, induction, invariant reasoning, or theorem justification",
        ],
        "includes": [
            "what claim is being proven or justified",
            "why the proof/reasoning matters when not self-evident",
            "meaning of the claim",
            "givens, assumptions, definitions, or allowed facts when needed",
            "reasoning intuition",
            "proof plan",
            "step-by-step reasoning",
            "worked proof or proof segment",
            "common invalid reasoning trap when useful",
            "proof/reasoning practice",
        ],
        "excludes": [
            "formula calculation practice unless it supports the proof",
            "long derivations without explaining why steps are valid",
            "symbol-heavy reasoning without plain-English explanation",
            "proofs that are unnecessary for the learner's goal",
            "popups, interactive links, microchecks, or generated visuals",
        ],
        "implementation_note": (
            "Mathematical proof steps should use LaTeX where appropriate, with plain-English reasoning beside them."
        ),
        "typical_card_sequence": [
            "background",
            "components_terms optional",
            "proof_plan",
            "process",
            "worked_example",
            "practice",
        ],
        "examples": [
            "Use induction to prove a formula",
            "Prove a set identity",
            "Why binary search is O(log n)",
            "Why inorder traversal of a BST is sorted",
            "Prove a function is injective",
            "Prove correctness of an algorithm",
            "Use loop invariants",
        ],
    },
    "compare_distinguish": {
        "name": "Compare / Distinguish",
        "definition": (
            "Used when the topic itself is about separating similar or confusing ideas by showing "
            "what they share, how they differ, when to use each, and what mistakes learners make when mixing them up."
        ),
        "use_when": [
            "two or more ideas are commonly confused",
            "the learner needs to distinguish ideas, not deeply relearn each idea",
            "the distinction itself deserves focused treatment",
            "choosing the wrong concept changes the answer, method, design, or interpretation",
        ],
        "includes": [
            "what ideas are being compared",
            "why the distinction matters when not self-evident",
            "why learners confuse them",
            "comparison dimensions when needed",
            "what they share",
            "main difference",
            "secondary differences when useful",
            "when to use each",
            "same example applied to both when useful",
            "common mix-up when useful",
            "comparison/decision practice",
        ],
        "excludes": [
            "deep full lessons on each option unless needed first",
            "generic pros/cons with no scenario",
            "comparison that only needs one misconception card inside another topic",
            "comparing ideas before both have been introduced",
            "choosing based on trendiness or vague preference",
            "popups, interactive links, microchecks, or generated visuals",
        ],
        "typical_card_sequence": [
            "background",
            "components_terms optional",
            "comparison",
            "worked_example",
            "practice",
        ],
        "examples": [
            "Stack vs queue",
            "Array vs linked list",
            "Permutation vs combination",
            "Independent vs mutually exclusive events",
            "Supervised vs unsupervised learning",
            "REST vs WebSockets",
            "SQL vs NoSQL",
        ],
    },
    "problem_solving_application": {
        "name": "Problem-Solving / Application",
        "definition": (
            "Used when the learner needs to recognize a reusable problem pattern, choose an approach, "
            "apply previous ideas to realistic problems, or transfer knowledge to new scenarios."
        ),
        "use_when": [
            "pattern recognition matters",
            "the learner needs to choose the first move or strategy",
            "the learner must apply previous concepts to solve realistic problems",
            "the topic is exam/interview-oriented or transfer-oriented",
            "the learner needs to distinguish when a method applies versus when it does not",
        ],
        "includes": [
            "what kind of problem this pattern/application handles",
            "why the pattern matters when not self-evident",
            "problem signals",
            "reusable strategy/template",
            "decision/application process",
            "worked realistic problem",
            "common trap when useful",
            "edge case or variation when useful",
            "application/transfer practice",
        ],
        "excludes": [
            "only explanation without practice",
            "only one solved example with no pattern extraction",
            "shallow memorization questions",
            "full concept reteaching unless user is weak",
            "multiple unrelated problem types in one topic",
            "popups, interactive links, microchecks, or generated visuals",
        ],
        "typical_card_sequence": [
            "background",
            "process",
            "worked_example",
            "edge_case optional",
            "practice",
        ],
        "examples": [
            "Sliding window pattern",
            "Two pointers",
            "Recursion trees",
            "Greedy-choice reasoning",
            "Dynamic programming pattern recognition",
            "Choose BFS or DFS for a graph problem",
            "LeetCode tree traversal prep",
            "Quant probability interview prep",
            "Use conditional probability in word problems",
        ],
    },
    "study_path_introduction": {
        "name": "Study Path Introduction",
        "definition": (
            "Used at the start of a study path to frame the overall concept area, give light background, "
            "show why the path matters, and prepare the learner for the topics that follow. "
            "The whole lesson is orienting — it does not teach any subtopic in depth."
        ),
        "use_when": [
            "the study path covers multiple related subtopics under one larger concept",
            "all upcoming topics share one central idea the learner needs to understand first",
            "the learner benefits from knowing the big picture before the details begin",
            "later topics depend on understanding the overall goal, vocabulary, or motivation",
            "the topic sequence would feel abrupt without a framing topic",
            "the learner asked for a broad goal, not one narrow subtopic",
            "example: introduction to BST traversal before inorder, preorder, postorder, level-order — all share the same central idea of visiting every node in a defined order",
            "example: introduction to graph traversal before BFS and DFS",
            "example: introduction to dynamic programming before memoization, tabulation, and patterns",
            "example: introduction to proofs before induction, contradiction, and invariants",
        ],
        "do_not_use_when": [
            "the study path covers multiple ideas or equations that do NOT build on each other and do not share a central idea — for example Bayes' theorem and law of total probability each stand alone as separate formulas with their own use cases",
            "the study path covers math equations or formulas explained independently with no overarching concept tying them together",
            "the user asks for one specific narrow topic and the background can fit inside that topic's background card",
            "the study path has only one topic",
            "the introduction would repeat the first real topic",
            "the introduction becomes a vague overview with no specific learning outcome",
        ],
        "includes": [
            "what the overall concept area is and why it matters",
            "light background to orient the learner before the path begins",
            "the central mental model or idea that ties the upcoming topics together",
            "minimum vocabulary needed before the path makes sense, when essential",
            "a preview of the major topics and why they appear in this order",
            "how the upcoming topics connect to the overall goal",
        ],
        "excludes": [
            "deep teaching of any individual subtopic",
            "detailed algorithm traces",
            "full implementation",
            "advanced edge cases",
            "long historical background",
            "vague filler with no learning outcome",
            "practice testing detailed mastery of subtopics",
            "standalone comparison unless it frames the whole path",
            "popups, interactive links, microchecks, or generated visuals",
        ],
        "typical_card_sequence": [
            "background — combined orientation and core concept; starts teaching immediately from the level where prior topics or assumed prerequisites ended",
            "components_terms optional - only when common terms will be used throughout study path which are not prerequisites or taught in first topic (not intro type)",
            "roadmap optional — one-sentence key concept preview per upcoming topic, only when subtopics are close enough that previewing what distinguishes each one helps the learner orient",
        ],
        "examples": [
            "Introduction to BST traversal before inorder, preorder, postorder, level-order",
            "Introduction to graph traversal before BFS and DFS",
            "Introduction to dynamic programming before memoization, tabulation, and patterns",
            "Introduction to proofs before induction, contradiction, and invariants",
            "Introduction to derivatives before chain rule, product rule, and applications",
            "Introduction to cellular respiration before glycolysis, Krebs cycle, and electron transport chain",
        ],
    },
    "science_mechanism": {
        "name": "Science Concept / Mechanism",
        "definition": (
            "Used for biology, physics, chemistry, neuroscience, and other science topics where the main goal "
            "is understanding a process, mechanism, model, or cause-effect chain."
        ),
        "use_when": [
            "components interact in a mechanism",
            "one variable affects another",
            "the learner must trace cause and effect",
            "the learner must predict what happens if one part changes",
            "graphs, data, models, or spatial structures may be needed",
            "the topic is science-specific, not just a generic concept",
        ],
        "includes": [
            "what the mechanism/process/model is",
            "why it matters when not self-evident",
            "where it happens or what system it belongs to",
            "components and roles",
            "core mechanism",
            "cause-effect chain",
            "variable changes or perturbations when useful",
            "graph/data/model interpretation when applicable",
            "worked mechanism example",
            "common misconception when useful",
            "mechanism-based practice",
        ],
        "excludes": [
            "only vocabulary definitions",
            "unrelated advanced biology/physics/chemistry details",
            "formulas as images",
            "mechanism diagrams without explaining cause-effect",
            "historical background unless needed for understanding",
            "popups, interactive links, microchecks, or generated visuals",
        ],
        "typical_card_sequence": [
            "background",
            "components_terms",
            "process",
            "worked_example",
            "edge_case optional",
            "practice",
        ],
        "examples": [
            "Photosynthesis",
            "Cellular respiration",
            "Action potentials",
            "Enzyme kinetics",
            "Newton's laws",
            "Electric fields",
            "Chemical equilibrium",
            "Osmosis and diffusion",
            "DNA replication",
        ],
    },
}


def format_topic_types_for_prompt() -> str:
    """Render all topic type definitions as a prompt-ready string."""
    lines: list[str] = []

    for type_id, defn in TOPIC_TYPE_DEFINITIONS.items():
        lines.append(f"  TOPIC TYPE: {type_id} - {defn['name']}")
        lines.append(f"  Definition: {defn['definition']}")
        lines.append(f"  Use when: {'; '.join(defn['use_when'])}")
        lines.append(f"  Includes: {', '.join(defn['includes'])}")
        lines.append(f"  Does not include: {', '.join(defn['excludes'])}")

        if "implementation_note" in defn:
            lines.append(f"  Note: {defn['implementation_note']}")

        if "typical_card_sequence" in defn:
            lines.append(f"  Typical card sequence: {', '.join(defn['typical_card_sequence'])}")

        lines.append(f"  Examples: {', '.join(defn['examples'])}")
        lines.append("")

    return "\n".join(lines)
