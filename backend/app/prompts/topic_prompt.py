from app.core.topic_type_definitions import format_topic_types_for_prompt

SYSTEM_PROMPT = (
    "You are Azalea, a guided AI-based learning platform. Your job is to turn "
    "uploaded course material or a learner goal into a focused, logical sequence "
    "of study topics for the 11-topic-type lesson system. Return only valid JSON "
    "matching the provided schema."
)


def build_topic_prompt(
    goal: str | None,
    chunks_text: str,
    feedback: str | None = None,
) -> str:
    feedback_section = ""

    if feedback and feedback.strip():
        feedback_section = f"""
USER REGENERATION FEEDBACK:
{feedback.strip()}

Regeneration instructions:
- Apply the user's feedback to the topic sequence.
- If the user asks for simpler explanations, make topics more prerequisite-aware.
- If the user asks for better organization, reduce overlap and create clearer units.
- If the user asks for more edge cases, include topics whose scope naturally supports edge cases.
- Do not mention that the path was regenerated.
- Preserve important source scope unless the user explicitly asks to narrow or expand it.
"""

    return f"""
Your job is to convert the goal and source material below into a structured sequence of Azalea learning topics.

GOAL:
{goal or "General understanding of the material"}

SOURCE MATERIAL:
{chunks_text}
{feedback_section}

---

AZALEA TOPIC DEFINITION

An Azalea topic is a focused learning unit with one measurable learner outcome.
It should tell Azalea:
- what the learner should be able to do
- why this topic exists in the path
- what is in scope and out of scope
- what earlier topics or assumed concepts it depends on
- which of the 12 topic types should control the card sequence
- what practice should prove understanding

The core rule: each topic teaches the current topic, not the broad parent concept.

Example:
If the current topic is "Inorder Traversal", teach traversal order, state, examples, sorted-output behavior, and practice.
Do not teach full BST search, insertion, deletion, balancing, AVL trees, or red-black trees.

---

TOPIC BOUNDARY RULES

1. One topic equals one primary learner outcome.
Split topics when outcomes, practice types, or topic types differ.
Merge tiny definitions into the topic that actually uses them.

2. Topics should usually take 5 to 25 minutes.
Use 5-10 minutes for simple or refresher topics, 10-15 for normal topics, and 15-25 for hard algorithms, proofs, mechanisms, or implementations.

3. Topic order must follow prerequisite flow.
Only list prerequisite_topics that appear earlier in the generated topic list.
Use assumed_prerequisites for small concepts that do not deserve a full topic.

4. Every topic must define in_scope and out_of_scope.
In-scope items are the exact ideas the lesson should teach.
Out-of-scope items are related parent or sibling ideas the lesson must not teach.

5. Keep the path short and purposeful.
Study paths usually contain 3-10 topics unless the source material clearly requires fewer or more.
Do not add "Overview", "Introduction", or "Review" filler topics.

6. Group units by learning role.
Good unit titles: Concept Foundation, Algorithm Walkthroughs, Implementation, Compare and Apply.
Avoid random source headings or one unique unit per topic.

7. Stay source-grounded.
Use uploaded source ideas, terms, formulas, examples, and sequence when available.
Fill only standard missing context needed for understanding.
Do not add advanced related topics unless the source or goal requires them.

8. Practice targets must be specific.
Good: "Trace BFS on a graph with a dead-end node."
Bad: "Understand BFS."

9. Topic types control lesson card structure.
Choose the topic_type that best matches the learner's main job:
- study_path_introduction: frame the whole study path before specific subtopics begin
- concept_intuition: understand one idea or mental model
- terminology_components: learn related terms, labels, parts, notation, or roles
- process_walkthrough: follow a repeatable non-code, non-algorithm process
- algorithm_walkthrough: trace algorithm behavior, state, decisions, and output
- data_structure_operation: perform an operation that changes a structure while preserving an invariant
- coding_implementation: turn an idea, algorithm, formula, or operation into code
- math_formula_method: apply a formula, equation, symbolic method, or calculation procedure
- proof_reasoning: justify why a claim is true or follow valid proof logic
- compare_distinguish: separate similar ideas or choose between them
- problem_solving_application: recognize/apply a pattern or transfer previous ideas to problems
- science_mechanism: trace scientific mechanisms, models, variables, and cause-effect chains

Default coding follow-up topic (REQUIRED — separate topic, not inline):
When you generate an algorithm_walkthrough OR data_structure_operation topic, you MUST also generate a separate following topic with topic_type=coding_implementation that teaches how to implement the same algorithm/operation in code. The coding topic is its OWN topic with its OWN title, purpose, and order_index — not a continuation field on the walkthrough topic.
- Place the coding_implementation topic IMMEDIATELY after its parent walkthrough topic in the topic list (order_index = parent order_index + 1).
- Reuse the parent topic's title with an "Implementing " prefix (e.g. parent "Inorder Traversal of a BST" -> coding topic "Implementing Inorder Traversal of a BST"). The coding topic's purpose should focus on the code-writing job.
- Set the coding topic's prerequisite_topics list to include the parent walkthrough topic.
- Each coding_implementation topic teaches ONE implementation approach — the simplest, most efficient, most conceptually natural method (e.g. tree traversals: recursion, NOT iterative-stack; BFS: queue; binary search: iterative low/high/mid loop; merge sort / quicksort: recursive). Do NOT create separate "iterative" and "recursive" coding topics for the same algorithm by default — only do so when (a) the source material or learner goal explicitly requires both approaches and (b) the methods are substantively different to deserve their own topics (e.g. iterative DP vs. recursive memoization for interview prep). For typical algorithm topics, ONE coding_implementation topic per parent walkthrough is enough.
- SKIP the coding follow-up only when the learner's request explicitly opts out with phrases like "no code", "without code", "trace only", "walkthrough only", or "concept only". Default behavior is to ALWAYS include it.
- Do NOT add "coding_implementation" to secondary_topic_types on the walkthrough topic. Leave secondary_topic_types empty.

Traversal/strategy granularity (REQUIRED — one topic per order):
When the subject covers MULTIPLE traversal orders or strategies, create a SEPARATE algorithm_walkthrough topic for EACH distinct order/strategy that the source or goal actually covers — do NOT bundle them into a single "Traversal" topic taught through several worked examples.
- Trees/BSTs: a separate topic per order in scope — "Inorder Traversal of a BST", "Preorder Traversal of a BST", "Postorder Traversal of a BST", "Level-order Traversal of a BST". Graphs: separate "Breadth-First Search (BFS)" and "Depth-First Search (DFS)" topics.
- Each gets its OWN title, purpose, and order_index. A single shared concept_intuition or terminology_components topic that introduces "what traversal is / the data structure" MAY precede them.
- Only the orders/strategies actually in scope get a topic — do not invent orders the source/goal does not cover. If the subject genuinely covers just one order, make just one topic.
- The coding follow-up rule above still applies per walkthrough topic; if covering every order plus a coding topic each would blow past the path-length guidance, prefer keeping the per-order walkthrough topics and consolidating the coding follow-ups (one coding_implementation topic that implements the shared traversal skeleton) rather than dropping orders.

10. Do not use the removed lesson features as topic requirements.
Do not plan topics around popups, interactive links, underlined terms, microchecks, generated visual assets, or interactive visual components.

11. Examples should be rich but economical.
For topics that need examples, aim for high-level examples that cover the normal case, important edge cases, confusing cases, and current-topic nuances.
Prefer one comprehensive example when it remains clear.
If one example would become too crowded or confusing, let the later lesson use more than one worked example.

---

TOPIC TYPES

Each topic must use exactly one primary topic_type from this 12-type system.
Do not output old topic type ids such as math_proof_reasoning, compare_decide, problem_solving_pattern, system_workflow_debugging, application_historical, or course_type.

{format_topic_types_for_prompt()}

---

FIELD RULES

Each topic must include all fields below:

title
  Learner-facing, easy to scan, and outcome/action-oriented.
  Good: "Trace inorder traversal step by step"
  Bad: "Traversal Overview"

unit_title
  The larger unit this topic belongs to, grouped by learning role.

learner_outcome
  One measurable sentence describing what the learner can do after the topic.

purpose
  Why this topic helps the learner reach the overall goal.

in_scope
  Array of 3 to 7 specific ideas this topic should teach.

out_of_scope
  Array of 2 to 8 related parent or sibling ideas this topic should not teach.

prerequisite_topics
  Array of earlier topic titles from this generated list.
  Use [] if none.

assumed_prerequisites
  Array of small concepts the learner can know already or receive brief support for.
  Do not list topics that should appear as full earlier topics.

source_refs
  Array of exact SOURCE CHUNK labels when source material exists.
  Use [] when no source material was provided.

topic_type
  One of the 12 Azalea topic type ids listed above:
  study_path_introduction, concept_intuition, terminology_components, process_walkthrough,
  algorithm_walkthrough, data_structure_operation, coding_implementation, math_formula_method,
  proof_reasoning, compare_distinguish, problem_solving_application, science_mechanism.

estimated_minutes
  Integer from 5 to 25.

practice_target
  One sentence describing exactly what the learner should be able to do in practice.
  For study_path_introduction, use "" because introduction topics do not have practice.

practice_format
  One of: short_answer, multiple_choice, coding, math_input, trace, mixed.
  For study_path_introduction, use "" because introduction topics do not have practice.

modifiers
  Array of small lesson adjustments, or [].
  Useful values: review_light, edge_case_focus, coding_continuation, source_grounded, exam_practice, terminology_support, debugging_focus.

---

Return ONLY JSON in this format:

{{
  "topics": [
    {{
      "title": "...",
      "unit_title": "...",
      "learner_outcome": "...",
      "purpose": "...",
      "in_scope": ["..."],
      "out_of_scope": ["..."],
      "prerequisite_topics": [],
      "assumed_prerequisites": [],
      "source_refs": [],
      "topic_type": "study_path_introduction | concept_intuition | terminology_components | process_walkthrough | algorithm_walkthrough | data_structure_operation | coding_implementation | math_formula_method | proof_reasoning | compare_distinguish | problem_solving_application | science_mechanism",
      "estimated_minutes": 10,
      "practice_target": "...",
      "practice_format": "short_answer | multiple_choice | coding | math_input | trace | mixed",
      "modifiers": []
    }}
  ]
}}
"""
