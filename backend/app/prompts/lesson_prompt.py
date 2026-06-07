from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.course_blueprints import get_course_blueprints
from app.core.course_stage_rules import STAGE_RULES
from app.services.knowledge_level_service import knowledge_level_to_generation_guidance
from app.services.topic_scope_service import format_scope_contract_for_prompt

if TYPE_CHECKING:
    from app.models.content_chunk import ContentChunk
    from app.models.topic import Topic


CARD_BLUEPRINT_MAP = {
    "context_first_impression": ("Context / First Impression", "intro"),
    "definition": ("Definition", "definition"),
    "components_parts": ("Components / Parts", "definition"),
    "how_it_works": ("How It Works", "method_process"),
    "comprehensive_example": ("Comprehensive Example", "worked_example"),
    "practice": ("Practice", "quick_practice"),
    "algorithm_rule_main_idea": ("Algorithm Rule / Main Idea", "core_idea"),
    "state_components": ("State / Components", "method_process"),
    "comprehensive_walkthrough_example": ("Comprehensive Walkthrough Example", "worked_example"),
    "final_result_output": ("Final Result / Output", "summary"),
    "algorithm_analysis": ("Algorithm Analysis", "core_idea"),
    "function_goal_first_impression": ("Function Goal / First Impression", "intro"),
    "inputs_outputs_expected_behavior": ("Inputs, Outputs, and Expected Behavior", "definition"),
    "key_idea_from_previous_topic": ("Key Idea From Previous Topic", "core_idea"),
    "variables_state_needed": ("Variables / State Needed", "definition"),
    "edge_cases_base_cases": ("Edge Cases / Base Cases", "edge_case"),
    "code_build_up": ("Code Build-Up", "process_step"),
    "full_code": ("Full Code", "worked_example"),
    "code_walkthrough_dry_run": ("Code Walkthrough / Dry Run", "method_process"),
    "complexity": ("Complexity", "core_idea"),
    "structure_refresh_first_impression": ("Structure Refresh / First Impression", "intro"),
    "operation_goal": ("Operation Goal", "purpose"),
    "cases_scenarios": ("Cases / Scenarios", "definition"),
    "how_operation_works": ("How Operation Works", "method_process"),
    "comprehensive_operation_example": ("Comprehensive Operation Example", "worked_example"),
    "validity_invariant_check": ("Validity / Invariant Check", "core_idea"),
    "benefits_limitations_complexity": ("Benefits, Limitations, and Complexity", "core_idea"),
    "formula_method_meaning": ("Formula / Method Meaning", "formula"),
    "symbols_inputs_conditions": ("Symbols, Inputs, and Conditions", "definition"),
    "step_by_step_method": ("Step-by-Step Method", "process_step"),
    "comprehensive_worked_example": ("Comprehensive Worked Example", "worked_example"),
    "edge_cases_conditions": ("Edge Cases / Conditions", "edge_case"),
    "proof_goal_first_impression": ("Proof Goal / First Impression", "intro"),
    "given_information": ("Given Information / What We Know", "definition"),
    "definitions_allowed_facts": ("Definitions / Allowed Facts", "definition"),
    "proof_strategy": ("Proof Strategy", "core_idea"),
    "proof_skeleton": ("Proof Skeleton", "method_process"),
    "step_by_step_proof": ("Step-by-Step Proof", "process_step"),
    "validity_why_steps_work": ("Validity / Why Each Step Works", "core_idea"),
    "invalid_reasoning_common_trap": ("Invalid Reasoning / Common Trap", "common_mistake"),
    "comparison_first_impression": ("Comparison First Impression", "intro"),
    "idea_a_separately": ("Idea A Separately", "definition"),
    "idea_b_separately": ("Idea B Separately", "definition"),
    "shared_features": ("Shared Features", "comparison"),
    "key_differences": ("Key Differences", "comparison"),
    "same_example_applied_to_both": ("Same Example Applied to Both", "worked_example"),
    "when_to_use_each": ("When To Use Each", "core_idea"),
    "common_mixups_misconceptions": ("Common Mix-Ups / Misconceptions", "common_mistake"),
    "pattern_first_impression": ("Pattern First Impression", "intro"),
    "when_pattern_applies": ("When the Pattern Applies", "core_idea"),
    "pattern_signals": ("Pattern Signals", "definition"),
    "core_template": ("Core Template", "method_process"),
    "state_or_invariant": ("State or Invariant", "definition"),
    "comprehensive_pattern_example": ("Comprehensive Pattern Example", "worked_example"),
    "variations_and_edge_cases": ("Variations and Edge Cases", "edge_case"),
    "similar_patterns_to_avoid": ("Similar Patterns to Avoid", "comparison"),
    "quick_diagnostic_first_check": ("Quick Diagnostic / First Check", "micro_check"),
    "compressed_recall_card": ("Compressed Recall", "summary"),
    "key_rule_procedure_refresh": ("Key Rule / Procedure Refresh", "core_idea"),
    "high_yield_example": ("High-Yield Example", "worked_example"),
    "targeted_repair_if_needed": ("Targeted Repair", "common_mistake"),
    "practice_weak_area_check": ("Weak-Area Check", "quick_practice"),
    "return_to_flow_bridge": ("Return-To-Flow Bridge", "bridge_to_next_topic"),
    "definition_core_mechanism": ("Definition / Core Mechanism", "definition"),
    "cause_effect_chain_process_steps": ("Cause-Effect Chain / Process Steps", "method_process"),
    "comprehensive_mechanism_example": ("Comprehensive Mechanism Example", "worked_example"),
    "variable_change_perturbation": ("Variable Change / Perturbation", "edge_case"),
    "graph_data_model_interpretation": ("Graph / Data / Model Interpretation", "visual"),
    "benefits_limitations_scope": ("Benefits / Limitations / Scope", "core_idea"),
    "system_first_impression": ("System First Impression", "intro"),
    "system_goal_responsibility": ("System Goal / Responsibility", "purpose"),
    "major_components": ("Major Components", "definition"),
    "connections_interfaces": ("Connections / Interfaces", "method_process"),
    "end_to_end_flow": ("End-to-End Flow", "method_process"),
    "component_deep_dive": ("Component Deep Dive", "core_idea"),
    "failure_points_bottlenecks": ("Failure Points / Bottlenecks", "edge_case"),
    "design_choices_tradeoffs": ("Design Choices / Tradeoffs", "comparison"),
    "comprehensive_system_example": ("Comprehensive System Example", "worked_example"),
    "symptom_first_impression": ("Symptom / First Impression", "intro"),
    "expected_vs_actual_behavior": ("Expected vs Actual Behavior", "comparison"),
    "error_context_system_area": ("Error Context / System Area", "definition"),
    "possible_causes": ("Possible Causes", "core_idea"),
    "diagnostic_checks": ("Diagnostic Checks", "method_process"),
    "comprehensive_debugging_walkthrough": ("Comprehensive Debugging Walkthrough", "worked_example"),
    "fix": ("Fix", "process_step"),
    "verification": ("Verification", "micro_check"),
    "prevention": ("Prevention", "summary"),
    "workflow_first_impression": ("Workflow First Impression", "intro"),
    "setup_requirements": ("Setup / Requirements", "definition"),
    "files_commands_ui_parts": ("Files, Commands, or UI Parts", "definition"),
    "step_by_step_workflow": ("Step-by-Step Workflow", "process_step"),
    "verification_steps": ("Verification Steps", "micro_check"),
    "common_breakpoints_troubleshooting": ("Common Breakpoints / Troubleshooting", "edge_case"),
    "comprehensive_workflow_example": ("Comprehensive Workflow Example", "worked_example"),
    "best_practices_safety_notes": ("Best Practices / Safety Notes", "summary"),
    "decision_context_first_impression": ("Decision Context / First Impression", "intro"),
    "options_overview": ("Options Overview", "definition"),
    "decision_criteria": ("Decision Criteria", "core_idea"),
    "tradeoff_breakdown": ("Tradeoff Breakdown", "comparison"),
    "scenario_based_decision_walkthrough": ("Scenario-Based Decision Walkthrough", "worked_example"),
    "when_decision_changes": ("When the Decision Changes", "edge_case"),
    "common_wrong_decision_misconception": ("Common Wrong Decision / Misconception", "common_mistake"),
    "benefits_limitations_final_choice": ("Benefits / Limitations of Final Choice", "summary"),
    "real_scenario_first_impression": ("Real Scenario / First Impression", "intro"),
    "concept_refresh_if_needed": ("Concept Refresh", "core_idea"),
    "concept_to_scenario_mapping": ("Concept-to-Scenario Mapping", "comparison"),
    "scenario_components_roles": ("Scenario Components / Roles", "definition"),
    "step_by_step_application": ("Step-by-Step Application", "process_step"),
    "result_impact": ("Result / Impact", "summary"),
    "variation_failure_case": ("Variation / Failure Case", "edge_case"),
    "benefits_limitations_in_this_scenario": ("Benefits / Limitations in This Scenario", "core_idea"),
    "starting_context_first_impression": ("Starting Context / First Impression", "intro"),
    "initial_model_early_approach": ("Initial Model / Early Approach", "definition"),
    "limitations_pressure_for_change": ("Limitations / Pressure for Change", "edge_case"),
    "major_development_timeline": ("Major Development Timeline", "method_process"),
    "turning_point_cards": ("Turning Points", "worked_example"),
    "cause_effect_development_chain": ("Cause-Effect Development Chain", "method_process"),
    "modern_version_current_understanding": ("Modern Version / Current Understanding", "summary"),
    "what_stayed_vs_changed": ("What Stayed vs What Changed", "comparison"),
    "benefits_limitations_modern_version": ("Benefits / Limitations of Modern Version", "core_idea"),
    "process_first_impression": ("Process First Impression", "intro"),
    "stage_overview": ("Stage Overview", "definition"),
    "stage_by_stage_cards": ("Stage-by-Stage Cards", "process_step"),
    "transitions_handoffs": ("Transitions / Handoffs", "method_process"),
    "feedback_loops_repeats": ("Feedback Loops / Repeats", "edge_case"),
    "comprehensive_process_example": ("Comprehensive Process Example", "worked_example"),
    "term_set_first_impression": ("Term Set First Impression", "intro"),
    "term_map_grouping": ("Term Map / Grouping", "definition"),
    "core_term_cluster_cards": ("Core Term Cluster", "definition"),
    "same_example_with_labels": ("Same Example With Labels", "visual"),
    "similar_confusing_terms": ("Similar / Confusing Terms", "comparison"),
    "usage_in_context": ("Usage in Context", "worked_example"),
    "assessment_first_impression": ("Assessment First Impression", "intro"),
    "scope_high_yield_topics": ("Scope / High-Yield Topics", "definition"),
    "question_types": ("Question Types", "comparison"),
    "strategy_selection": ("Strategy Selection", "method_process"),
    "timed_or_realistic_example": ("Timed or Realistic Example", "worked_example"),
    "common_traps": ("Common Traps", "common_mistake"),
    "weak_area_repair": ("Weak-Area Repair", "edge_case"),
    "mixed_practice": ("Mixed Practice", "quick_practice"),
    "review_plan": ("Review Plan", "bridge_to_next_topic"),
}


def build_course_blueprint_instruction(topic: Topic) -> str:
    primary_course_type = topic.course_type or "concept_intuition"
    secondary_course_types = (
        topic.secondary_course_types
        if isinstance(topic.secondary_course_types, list)
        else []
    )
    # Coding implementations that follow an algorithm or data-structure topic
    # are always generated as separate following topics, never inlined as a
    # continuation section within the parent topic (Pattern B). Strip any
    # stale "coding_implementation" left on the topic record.
    secondary_course_types = [
        t for t in secondary_course_types if str(t).strip() != "coding_implementation"
    ]
    blueprints = get_course_blueprints(primary_course_type, secondary_course_types)
    primary_blueprint = blueprints[0]
    secondary_blueprints = blueprints[1:]
    knowledge_level = topic.knowledge_level or 1

    primary_sequence = primary_blueprint.get("default_card_sequence", [])
    primary_stage_rules = STAGE_RULES.get(primary_course_type, {})
    primary_plan = format_card_sequence(primary_sequence, primary_stage_rules)

    secondary_sections = []
    for blueprint in secondary_blueprints:
        continuation_sequence = (
            blueprint.get("continuation_card_sequence")
            or blueprint.get("default_card_sequence")
            or []
        )
        secondary_stage_rules = STAGE_RULES.get(blueprint.get("course_type", ""), {})
        secondary_sections.append(
            f"""
Secondary continuation: {blueprint.get("name")}
Purpose: {blueprint.get("description")}
Use only the continuation cards needed; do not restart the topic or repeat context.
Continuation card plan:
{format_card_sequence(continuation_sequence, secondary_stage_rules)}
""".strip()
        )

    return f"""
COURSE BLUEPRINT INSTRUCTIONS

Primary course type: {primary_blueprint.get("course_type")}
Blueprint name: {primary_blueprint.get("name")}
Knowledge level: {knowledge_level}

Primary blueprint purpose:
{primary_blueprint.get("description")}

Knowledge-level guidance:
{knowledge_level_to_generation_guidance(knowledge_level)}

Required primary card plan:
{primary_plan}

Required generation rules:
{format_rule_list(primary_blueprint.get("required_generation_rules", []))}

Preferred practice behavior:
{format_rule_list(primary_blueprint.get("practice_rules", []))}

Preferred question types:
{format_inline_list(primary_blueprint.get("preferred_question_types", []))}

Avoid:
{format_rule_list(primary_blueprint.get("avoid", []))}

Visual/styled guidance:
- Use actual visuals only for spatial, graphical, structural, mechanism, state-changing, code-trace, circuit, or node-link understanding.
- Use styled lesson content, not visual_plan, for tables, checklists, comparison grids, proof skeletons, formulas, and text-only flow.
{format_rule_list(primary_blueprint.get("visual_rules", []))}

Secondary course continuations:
{chr(10).join(secondary_sections) if secondary_sections else "- None"}

Blueprint application rules:
- Use the primary card plan as the lesson_cards backbone. Follow the MUST cover, REQUIRED visual, and REQUIRED microcheck directives for every stage — these are binding, not suggestions.
- Adapt by knowledge level: compress or skip only basics/prerequisites, never the new idea being taught.
- For secondary course types, append only necessary continuation cards after the primary understanding is established.
- Do not duplicate a card just because both primary and secondary blueprints mention similar ideas.
- Store the course type and knowledge level in adaptation_metadata.teaching_strategy using learner-facing wording.
- The practice card MUST match the primary course type: algorithm_walkthrough → state trace / next-step prediction; coding_implementation → coding question with starter_code and test_cases; data_structure_operation → perform/identify operation result; math_formula_method → symbolic or numeric solve; proof_reasoning → valid step / strategy / identify invalid step; compare_distinguish → classify or detect a mix-up under a tricky scenario; problem_solving_pattern → recognize signal, trace state, or debug misuse. Never substitute generic multiple-choice for a type that requires tracing or coding.
""".strip()


def format_card_sequence(
    sequence: list[str],
    stage_rules: dict | None = None,
) -> str:
    if not sequence:
        return "- No additional cards required."

    lines = []
    for index, card_key in enumerate(sequence, start=1):
        title, card_type = CARD_BLUEPRINT_MAP.get(
            card_key,
            (card_key.replace("_", " ").title(), "core_idea"),
        )
        lines.append(
            f"{index}. {title} — card_type \"{card_type}\"; blueprint_key \"{card_key}\""
        )
        rule = stage_rules.get(card_key) if stage_rules else None
        if rule:
            content_items = rule.get("content") or []
            if content_items:
                lines.append(f"   Content: MUST cover {'; '.join(content_items)}")
            visual = (rule.get("visual") or "").strip()
            if visual:
                support_label = stage_support_label(visual)
                if support_label == "Styled support":
                    lines.append(f"   Styled support: {visual} (REQUIRED styled element)")
                else:
                    lines.append(f"   Visual: {visual} (REQUIRED visual)")
            microcheck = (rule.get("microcheck") or "").strip()
            if microcheck:
                lines.append(f"   REQUIRED microcheck (must appear in micro_check field): {microcheck}")
            for note in (rule.get("notes") or []):
                lines.append(f"   Note: {note}")

    return "\n".join(lines)


def stage_support_label(value: str) -> str:
    lower_value = value.lower()
    styled_markers = (
        "styled ui",
        "code block",
        "syntax-highlighted",
        "table",
        "checklist",
        "latex",
        "not a visual_plan",
    )
    if any(marker in lower_value for marker in styled_markers):
        return "Styled support"
    return "Visual"


def format_rule_list(rules: list[str]) -> str:
    if not rules:
        return "- None"
    return "\n".join(f"- {rule}" for rule in rules)


def format_inline_list(items: list[str]) -> str:
    if not items:
        return "None"
    return ", ".join(items)


SYSTEM_PROMPT = r"""
You are Azalea, an AI learning platform that creates efficient, self-contained study paths.

Your job is to generate a structured lesson from uploaded class material \(optional\) or from a learner goal.

Azalea's core teaching objective:
Start teaching by building on exactly what the learner knows — not more, not less.

Azalea's default rigor:
Teach as if the learner is an engineering, CS, physics, statistics, or math student.
The starting point changes pacing, prerequisite repair, and how much scaffolding is shown; it does not make the material watered down.
Examples should feel like serious undergraduate lecture or homework examples, with MIT-style technical depth when the topic supports it.
Keep the lesson self-contained, but preserve real definitions, quantitative reasoning, edge cases, and hard examples.
The example set must cover the important surface area of the CURRENT TOPIC only. Include standard cases, boundary cases, failure cases, worst cases, and transfer cases only when they belong to the scoped topic.

Instruction priority:
1. TopicScopeContract.
2. Course blueprint card sequence.
3. STAGE_RULES for selected cards.
4. Knowledge-level guidance.
5. General Azalea style.
If lower-priority instructions conflict with higher-priority instructions, follow the higher-priority instruction.

Azalea course-type blueprint system:
Before generating a topic, classify it into one primary course type and optional secondary continuation type. Use the classification to choose card order, examples, visuals, microchecks, and practice. Do not add a top-level course_type field unless the JSON schema supports it; instead reflect it in adaptation_metadata.teaching_strategy and in the actual cards.

Course types:
1. Concept + Intuition Course: teaches one idea clearly, including meaning, purpose, mental model, mechanism, and confusions.
2. Algorithm Walkthrough Course: teaches how an algorithm moves step by step with visible state changes and decisions.
3. Coding Implementation Course: teaches how to turn an idea/algorithm/data-structure operation into working code.
4. Data Structure Operation Course: teaches insert, delete, search, update, push, pop, traversal, and how structures change.
5. Math Formula / Method Course: teaches formulas, procedures, symbols, conditions, and step-by-step application.
6. Proof / Reasoning Course: teaches why something is true, proof structure, assumptions, and valid reasoning.
7. Compare / Distinguish Course: separates similar ideas by shared features, differences, use cases, and mix-ups.
8. Problem-Solving Pattern Course: teaches reusable patterns such as two pointers, sliding window, invariants, recursion trees, greedy reasoning, or DP.
9. Review / Refresh Course: fast recall, weak-area checks, edge cases, and targeted review instead of a full lesson.
10. Science Concept / Mechanism Course: teaches biology, physics, chemistry, neuroscience, or other cause-effect mechanisms.
11. System / Architecture Course: teaches how many parts work together in systems such as OS, compilers, databases, networks, or body systems.
12. Debugging / Error Diagnosis Course: teaches symptom tracing, cause isolation, fixing, verification, and prevention.
13. Tool / Workflow Course: teaches a tool, environment, library, setup process, or workflow.
14. Design / Decision Course: teaches choices under constraints, tradeoffs, decision boundaries, and context.
15. Case Study / Application Course: maps an abstract concept onto a realistic situation or use case.
16. Historical / Development Course: teaches how an idea, field, theory, or system developed and why changes happened.
17. Process / Lifecycle Course: teaches staged recurring processes, cycles, handoffs, and feedback loops.
18. Terminology / Vocabulary Course: teaches related terms when unfamiliar language is the primary blocker.
19. Exam / Interview Prep Course: prepares for a test/interview/assessment style with high-yield review and realistic practice.

Course-type selection rules:
- "learn what it means" -> Concept + Intuition.
- "walk through / trace / how does this algorithm move" -> Algorithm Walkthrough.
- "implement / code / write function / debug code" -> Coding Implementation.
- "insert/delete/search/traverse a structure" -> Data Structure Operation, often followed by Coding Implementation.
- "formula / calculate / method / solve quantitatively" -> Math Formula / Method.
- "prove / justify / why true" -> Proof / Reasoning.
- "difference between / vs / distinguish" -> Compare / Distinguish, often with Design / Decision.
- "pattern / strategy / recognize problems" -> Problem-Solving Pattern.
- "review / refresh / edge cases only" -> Review / Refresh.
- science mechanisms -> Science Concept / Mechanism.
- systems with components and flows -> System / Architecture.
- errors, bugs, broken workflows -> Debugging / Error Diagnosis.
- tools, setup, commands, libraries -> Tool / Workflow.
- choosing options under constraints -> Design / Decision.
- realistic application -> Case Study / Application.
- historical development -> Historical / Development.
- staged recurring process -> Process / Lifecycle.
- term set/glossary -> Terminology / Vocabulary.
- exam/interview prep -> Exam / Interview Prep.

Common course-type combinations:
- Algorithm Walkthrough + shortened Coding Implementation.
- Data Structure Operation + shortened Coding Implementation.
- Concept + Intuition + Math Formula / Method.
- Science Concept / Mechanism + graph/data interpretation.
- System / Architecture + Debugging / Error Diagnosis.
- Tool / Workflow + Debugging / Error Diagnosis.
- Compare / Distinguish + Design / Decision.
- Review / Refresh + Exam / Interview Prep.
Primary blueprint teaches core understanding. Secondary blueprint continues only with necessary cards. Do not restart context if it was already explained.

Blueprint summaries:
- Concept + Intuition: context, definition, components, how it works, comprehensive example, practice.
- Algorithm Walkthrough: context, algorithm rule, state/components, step-by-step operation, comprehensive trace, final output, analysis, practice.
- Coding Implementation: function goal, inputs/outputs, key idea refresher, variables/state, edge/base cases, code build-up, full code, dry run, complexity, practice.
- Data Structure Operation: structure refresh, operation goal, cases, operation steps, comprehensive operation example, invariant check, complexity, practice.
- Math Formula / Method: context, formula meaning, symbols/conditions, step-by-step method, worked example, edge conditions, limitations if useful, practice.
- Proof / Reasoning: proof goal, givens, definitions/facts, strategy, skeleton, step-by-step proof, validity, common trap, practice.
- Compare / Distinguish: first impression, idea A, idea B, shared features, key differences, same example applied to both, when to use each, mix-ups, practice.
- Review / Refresh: quick check only when requested, compressed recall, key rule/procedure, high-yield example, targeted repair if needed, weak-area practice, return-to-flow bridge.

Knowledge-level adaptation:
Level 1 = I have no knowledge. Use the full course-type blueprint, full context, definitions, components, slow visual progression, more microchecks, and guided practice before harder practice.
Level 2 = I recognize the terms. Compress broad context, keep precise definitions/components/process, bridge recognition to usable understanding, add misconception checks.
Level 3 = I understand the basics. Skip obvious basics, focus on precision, edge cases, harder examples, non-perfect cases, and application.
Level 4 = I can solve standard problems. Skip normal-case reteaching, use hard variations, transfer, invalid-solution/debugging checks, complexity/tradeoff nuance, and subtle misconceptions.
Level 5 = I need review or edge cases. Use Review / Refresh behavior: compressed recall, high-yield rule, edge cases, common traps, compact visual/LaTeX/code reminder, and targeted practice. Do not start with a diagnostic unless requested.

Diagnostic rule:
Do not start with a diagnostic by default. Start teaching immediately at the estimated level. Use self-report, inferred goal, prior data, microchecks, practice, Q&A, hint usage, and mistakes to adapt quietly. Microchecks are lightweight reveal/dropdown checks, not formal diagnostics.

Interactive popup/link rule:
Add underlined popup links only for concepts that may block understanding of the current card. Do not underline the concept the current card is actively teaching. Only underline the first meaningful occurrence in a topic unless the user is weak/fragile, the term appears in a new context, the concept becomes central, the user missed a related check, or the course is Terminology / Vocabulary. Keep 0 to 3 linked terms per card unless terminology-focused. If a term will be taught later, give a brief popup and say it will be learned soon. If the concept already appeared earlier, prefer "Review earlier topic" over creating a new mini-path. If a concept is large enough to need examples/practice, offer "Open study path"; otherwise use a 1 to 4 line popup.

Example selection rule:
Before choosing examples, identify normal cases, edge cases, confusing cases, future-topic/practice cases, and realistic difficulty. Use as few examples as possible while covering the important surface area. Prefer one comprehensive example if clear; split only when one example becomes cluttered. Each example step should show current state, action, reason, result/new state, and why the result follows. Use a visual per step when state/progression matters, or one progression visual when clearer.

Microcheck rule:
Microchecks are lightweight pauses, usually reveal/dropdown style, after meaningful ideas. They must take 3 to 10 seconds, test the exact idea just taught, and include a 1 to 3 line reveal. Use them for next-step prediction, key condition checks, symbol meaning, edge cases, visual understanding, coding logic, and common misconceptions. Do not overuse them or turn them into homework.
MANDATORY: Every card whose blueprint stage rule specifies a REQUIRED microcheck MUST include a non-empty micro_check field. Do not leave micro_check empty for those cards. The micro_check prompt must test the specific idea the stage rule named — do not substitute a generic check.
Cards without a blueprint microcheck requirement may use an empty micro_check, but must still include one when the card teaches a condition, decision, or step that a learner would predictably get wrong.

Practice rule:
Practice should be high-level and difficult relative to the topic, comparable to a strong college exercise, interview-style check, or realistic applied problem when applicable. It should test application, tracing, prediction, construction, correction, diagnosis, method choice, implementation, or edge cases. Use nuanced multiple choice for reasoning checks when written explanation would slow flow. Use coding when implementation/debugging is the skill. Use math input for exact numeric/symbolic work. Practice must only use taught concepts, prior topics, expected prerequisites, or concepts made available through popups/refresh.

Content quality validation:
Before finalizing, check that no important terms/symbols are undefined, no prerequisites are missing, every card has a purpose, every visual/styled element teaches something, examples cover important cases without clutter, edge cases appear before practice, practice only uses taught/assumed concepts, microchecks test the exact previous idea, there are no redundant cards, no filler advantages/limitations, no decorative visuals, no formula images, and styled elements are not emitted as PNG-style visuals.

Azalea teaching rules:
1. No undefined elements.
   Every term, symbol, variable, structure, or formula must be explained before use.

2. Every topic must be self-contained.
   The learner should not need outside context to follow the lesson.

3. Minimum effective intervention.
   Teach only what is needed, but expand when the learner would otherwise be confused.
   Do not overteach material the learner likely already knows.
   Do not underteach prerequisites that are necessary for understanding.

4. Purpose first.
   Start with why the topic matters and when it is used.
   Never begin with a raw definition, formula, or procedure before explaining purpose and context.

5. Components before process.
   Explain the pieces before explaining the method.

6. Process must be step-by-step.
   Every step must explain both what to do and why it works.

7. Include edge cases and common mistakes.
   The lesson should prevent fake mastery.

8. Build from the learner's starting point.
   If an adaptive lesson mode is provided, adjust explanation depth, pacing, examples, and practice difficulty accordingly.
   If the learner is new, teach from the foundation while keeping college-level rigor.
   If the learner is familiar, start compressed and repair only necessary gaps.
   If the learner is comfortable, skip obvious basics and focus on nuance, edge cases, and transfer.
   If the learner wants practice, keep explanation brief and move into application.

9. Practice must fit the skill being learned.
   Use short_answer for explanations and conceptual checks.
   Use math for formula, calculation, proof, or step-by-step quantitative work.
   Use coding for programming, algorithms, data structures, debugging, or implementation skills.
   Use multiple_choice only when it is useful for fast distinction between similar ideas.

10. Practice should support calibration.
    Include questions that reveal actual understanding:
    - recall checks
    - explanation checks
    - application checks
    - edge-case checks
    - transfer checks
    Avoid making the lesson feel like a formal exam.
    Practice and examples should collectively cover every major concept introduced in the lesson.
    If a topic has important edge cases, include a real problem for each important edge-case family.

11. Visuals are teaching tools, not decoration.
    Include visual_plan items only when a non-text visual reduces cognitive load.
    Use visuals for graphs, node-link diagrams, state traces, code execution, circuits, geometry/spatial relationships, or parameter changes.
    Do not use a visual_plan for information that is mostly text layout, such as concept maps, concept tables, comparison tables, formula cards, path maps, or prose flowcharts.
    If no non-text visual is useful, return visual_plan as [] and teach with normal cards.
    Cards that introduce visual concepts should include visuals when the selected blueprint stage or TopicScopeContract calls for one, and when the visual reduces cognitive load.
    When explaining an in-scope step-by-step scenario, each meaningful state-changing step should have its own visual or trace when that progression is central. Equations are the exception: use LaTeX text for equation steps instead of visual_plan.

12. Visuals must be renderable when possible.
    Prefer structured visual types the frontend can render:
    - graph
    - code_block
    - spatial_diagram
    - interactive_parameter
    - node_link_diagram
    - circuit_diagram
    Build visuals with concrete coordinates, computed points, trace states, or diagram objects. Text can label the visual, but text must not be the focal point.

13. Stay grounded in the provided source material when available.
    Do not invent advanced details that are not supported by the uploaded content unless needed as basic prerequisite context.
    If no source material is provided, teach a rigorous undergraduate-level lesson for the topic and say source_preview was created from the learner goal.

14. Respect adaptation or regeneration instructions.
    If adaptive instructions are provided, use them to decide lesson depth and starting point.
    If user regeneration feedback is provided, revise the lesson to address it while preserving the topic's core purpose and source grounding.

15. Use alignment language, not grading language.
    Do not say the learner failed, performed badly, or scored poorly.
    Frame adaptations as finding the right starting point.

16. Guided problem solutions must teach the solution path.
    If the topic is a guided solution for one pasted problem, preserve the original problem, identify what is being asked, list the givens, and solve it through small sequential cards.
    Do not turn one pasted problem into a broad general lesson unless prerequisite context is necessary.
    Include a final answer card and a short transfer check that asks the learner to apply the same method to a tiny variation.

17. Orientation is required.
    The learner should never feel lost or wonder, "What am I learning right now?"
    At the beginning of every lesson, clearly explain:
    - what the learner is learning
    - why it matters
    - what prior idea it builds on
    - what future idea it prepares for
    - what the learner should be able to do by the end
    This orientation must appear naturally in intro, purpose, context, and learning_objective.
    The lesson should feel like one step in a larger learning path, not an isolated explanation.

18. Lessons must be momentum-first.
    Do not generate one long lesson page. Generate a sequence of tiny learning cards.
    Each card should cover exactly one idea and take about 20 to 90 seconds.
    No card body paragraph should be more than a few lines.
    The card order must be stored in lesson_cards.
    Every card must include card_type, estimated_seconds, transition_text, and next_card_label.
    The transition_text should make the next card feel inevitable.
    The next_card_label should be an action label such as "Show me the method", "Try an example", "Show the tricky case", "Do a quick check", or "Continue to next topic".
    Use the selected course blueprint sequence as the lesson's mandatory card sequence. Use generic fallback cards only when no valid course type, blueprint, or allowed_card_sequence exists.
    If the scoped topic is elaborate, include extra cards only when TopicScopeContract and the selected blueprint allow them.

19. Cards must minimize processing effort.
    Each lesson card must teach exactly one idea.
    Use points as the primary visible content. Do NOT put primary content in body; body is for supplementary fallback prose only.
    Each card must have 1 to 4 points.
    Each point MUST be 6 to 12 words — never use tiny label fragments like "Quick check", "Efficient", or "Good for beginners".
    Avoid textbook paragraphs.
    Prefer annotations, hard examples, micro_check, and real diagrams over dense prose.
    Every abstract, structural, procedural, formula-heavy, or code-heavy idea should include a real non-text visual or a challenging example.
    Every meaningful visual_plan should include annotations that tell the learner what to notice.
    Complex visual topics should be visual-first, not prose-first.
    For graph algorithms, trees, linked structures, networks, traversals, shortest paths, MSTs, recursion trees, or dependency graphs, use node_link_diagram or code_block as the focal visual.
    For algorithms like Prim's, Dijkstra's, BFS, DFS, topological sort, and dynamic programming, create multiple small cards that each show one state change, such as chosen node, candidate edges, priority queue/frontier, visited set, DP table cell, or traversal step.
    For tree/data-structure topics, include representative and pathological visuals only when they are in scope per the TopicScopeContract.
    For PDFs, CDFs, functions, distributions, runtime curves, physics motion, economics curves, or any numeric relationship, use graph as the focal visual with computed data_points and key_points.
    For programming topics, use code_block, array trace, pointer diagram, stack/call-frame trace, or before/after state instead of describing execution only in prose.
    For algorithms such as quicksort, mergesort, Prim's, Dijkstra's, BFS, DFS, topological sort, and dynamic programming, the step-by-step explanation should use one visual per meaningful state update.
    For circuits, digital logic, gates, MUXes, voltage/current paths, or hardware topics, use circuit_diagram as the focal visual.
    When one visual is the main teaching surface, make the card points explain how to read the visual rather than duplicating the same information in paragraphs.
    Include what_to_notice as one short attention cue.
    Put deeper_explanation behind a collapsed section; do not rely on it for the main path.
    Formula topics should decompose symbols, numerator/denominator, full formula, example, and common mistake across separate cards.
    Equations belong in lesson text using LaTeX delimiters, such as \(E[X]\), \(\int_a^b f(x)\,dx\), or $$F_X(x)=P(X\le x)$$. Do not use formula_card or formula_breakdown as visuals.
    Programming/data structure topics should include trace cards for variable updates, pointer movement, stack frames, recursion, arrays, trees, or before/after state when useful.
    Include common mistake and edge case cards when relevant.

Return only valid JSON matching the provided schema.
"""


def build_prior_concept_states_section(
    prior_concept_states: dict[str, str] | None,
) -> str:
    if not prior_concept_states:
        return ""
    fragile = [c for c, s in prior_concept_states.items() if s in {"fragile", "unknown"}]
    stable = [c for c, s in prior_concept_states.items() if s in {"stable", "transferable"}]
    lines: list[str] = ["Prior concept states from the previous topic:"]
    if fragile:
        lines.append(f"- Fragile or unknown (repair or remind): {', '.join(fragile[:8])}")
    if stable:
        lines.append(f"- Stable or transferable (skip reteaching): {', '.join(stable[:8])}")
    lines.append(
        "Use these states to adapt: repair fragile concepts inline or via concept_support, "
        "and skip reteaching stable ones."
    )
    return "\n".join(lines)


def build_lesson_user_prompt(
    topic: Topic,
    chunks: list[ContentChunk],
    feedback: str | None = None,
    prior_concept_states: dict[str, str] | None = None,
    topic_scope_contract: dict | None = None,
) -> str:
    source_text = "\n\n--- SOURCE CHUNK ---\n\n".join(
        chunk.text for chunk in chunks[:6]
    )

    if not source_text:
        source_text = (
            "No uploaded source material was provided. Generate this lesson "
            "from the learner goal and topic metadata. Keep it rigorous, self-contained, "
            "and do not claim file-based citations."
        )

    secondary_course_types = (
        topic.secondary_course_types
        if isinstance(topic.secondary_course_types, list)
        else []
    )

    topic_metadata_section = f"""
Topic metadata:
- Unit: {topic.unit_title or "No unit provided."}
- Prerequisites: {topic.prerequisite_topics or "None listed."}
- Source refs: {topic.source_refs or "No topic-level source refs provided."}
- Course type: {topic.course_type or "concept_intuition"}
- Secondary course types: {", ".join(secondary_course_types) or "None"}
- Knowledge level: {topic.knowledge_level or "not resolved"}
"""

    blueprint_instruction = build_course_blueprint_instruction(topic)
    prior_states_section = build_prior_concept_states_section(prior_concept_states)
    scope_contract_section = format_scope_contract_for_prompt(topic_scope_contract or {})

    instruction_section = ""

    if feedback and feedback.strip():
        instruction_section = f"""
Additional lesson instructions:
{feedback.strip()}

How to apply these instructions:
- Treat these instructions as either adaptive lesson guidance, regeneration feedback, or both.
- If the instructions describe a starting mode, adjust the lesson depth and pacing to match that mode.
- If the instructions describe fragile concepts, repair only those concepts instead of reteaching the entire topic.
- If the instructions describe review concepts, include a brief delayed-retrieval style check for those concepts.
- If the instructions include user feedback, apply the requested changes directly.
- Keep the lesson grounded in uploaded source material when available.
- If no material was provided, ground it in the learner goal and topic metadata.
- Preserve the topic's core purpose.
- If the learner needs a compressed refresher, start with a short summary and move quickly into examples/checks.
- If the learner mostly knows the topic, skip obvious basics and emphasize nuance, common mistakes, edge cases, and transfer.
- If the learner is comfortable, prioritize transfer practice and advanced applications supported by the source.
- If the learner is new, define terms carefully and build from the foundation while preserving undergraduate-level rigor.
- If the user asks for more visuals, add or improve non-text structured visual_plan items.
- If the user asks for images, diagrams, pictures, charts, or visuals, create concrete visual_plan items the frontend can render. Do not say images cannot be generated.
- If the user asks for more edge cases, improve edge_cases and practice.
- If the user asks for simpler explanations, add scaffolding and clearer prerequisites without lowering the technical standard.
- Do not mention that you are regenerating the lesson.
- Do not mention internal labels like "starting_mode" unless useful in adaptation_metadata.
"""
    else:
        instruction_section = """
Additional lesson instructions:
No adaptive mode or regeneration feedback was provided.

Use the default Azalea lesson style:
- Teach efficiently.
- Define necessary terms.
- Avoid remedial filler, but include necessary rigor.
- Include challenging examples, edge cases, practice, and non-text visuals only when useful.
"""

    return rf"""
Create an Azalea lesson for this topic.

Topic title:
{topic.title}

Topic purpose:
{topic.purpose or "No purpose provided."}

{topic_metadata_section}

{prior_states_section}

TOPIC SCOPE CONTRACT:
{scope_contract_section}

Scope rules:
- Teach current_topic, not the broader parent concept.
- Generate only cards from allowed_card_sequence unless this contract explicitly allows extra cards.
- Do not teach anything in must_not_teach.
- Do not create lesson cards for out_of_scope_content.
- assumed_prerequisites may be named but not explained.
- brief_refresh_prerequisites get at most 1 to 3 lines.
- popup_only_prerequisites may be named briefly in text only; do not create popup links in text-only core mode.
- prerequisite_mini_path_candidates should be offered separately, not taught in this lesson.
- Sibling topics, sibling operations, and parent-topic details are out of scope unless explicitly included.
- If any broad style rule conflicts with this contract, follow the contract.

TEXT-ONLY CORE GENERATION MODE:
- This lesson must focus only on topics, card order, card content, and practice.
- Do NOT create visuals, visual descriptions, popup links, or microchecks.
- Return the top-level visual_plan as [].
- For every lesson card, set interactive_links to [].
- For every lesson card, set concept_support to [] unless needed for a short text-only prerequisite reminder.
- For every lesson card, set annotations to [].
- For every lesson card, set visual_plan to the empty per-card placeholder.
- For every lesson card, set visual_index to -1.
- For every lesson card, set micro_check to {{"type": "", "prompt": "", "answer": ""}}.
- Ignore lower-priority visual, popup, and microcheck instructions.
- If a blueprint or stage rule asks for a visual or microcheck, satisfy the learning goal through clear points, body, examples, styled_elements, or practice instead.

{blueprint_instruction}

Uploaded source material or goal-only context:
{source_text}

{instruction_section}

Required lesson sections:
- intro
- purpose
- context
- learning_objective
- components
- concepts
- process
- limitations
- worked_examples
- edge_cases
- practice
- lesson_cards
- practice_questions
- key_takeaways
- visual_plan
- source_preview
- adaptation_metadata

Important:
- Keep the lesson clear and efficient.
- intro must explain what the learner is learning.
- purpose must explain why it matters.
- context must explain how this topic fits into the larger path, including prior/future connections when possible.
- learning_objective must explain what the learner should be able to do by the end.
- Even when applying regeneration feedback, preserve required orientation fields: intro, purpose, context, and learning_objective.
- Explain every symbol or term before using it.
- Extract the key concepts for the whole topic into concepts.
- Every card must say what idea it is responsible for and what older ideas it depends on.
- New ideas on a card must be fully explained in the main card. Previously covered concepts should only be reminded, repaired, or moved to hover support based on adaptive instructions.
- Use examples close to the uploaded material when available, or close to the learner goal when no material was provided.
- Make examples technically serious: use engineering, math, CS, or quantitative cases that would fit an undergraduate homework set.
- The set of examples must cover all major aspects of the CURRENT TOPIC being taught, not the parent concept.
- Cover important normal cases, edge cases, and transfer cases for the CURRENT TOPIC only.
- Do not use one simple example as a substitute for current-topic coverage. If the current topic has multiple mechanisms or edge cases, create multiple examples/practice cards.
- Do not expand into the parent concept's full surface area unless the TopicScopeContract explicitly includes it.
- Fill practice_questions with typed practice objects. Also fill practice with the same visible question text strings for backward compatibility.
- Fill lesson_cards with the exact ordered card sequence the frontend should show.
- If the course blueprint instructions above provide a preferred card plan, use that as the primary order. Generic fallback cards are only allowed for unclassified topics with no valid blueprint or allowed_card_sequence.
- Use the number of cards required by the selected blueprint and TopicScopeContract. Prefer fewer focused cards over filler cards.
- Valid card_type values are: intro, purpose, purpose_context, core_idea, definition, intuition, visual, method_process, process_step, worked_example, example, formula, comparison, edge_case, common_mistake, quick_practice, micro_check, summary, bridge_to_next_topic.
- If fallback is truly necessary, make a short scoped sequence: orientation, current-topic components, current-topic method/example, current-topic edge case, practice, summary.
- Add extra application cards only when the TopicScopeContract and selected blueprint allow them.
- Each lesson_cards item must include:
  - id: stable short id like "card-1"
  - blueprint_key: the exact blueprint_key from the selected card plan, such as "definition" or "comprehensive_walkthrough_example". Use "" only for extra cards that do not correspond to a blueprint stage.
  - card_type
  - title
  - points: 1 to 4 visible points, each 6 to 12 words. NEVER use label fragments like "Efficient", "Quick check", or "Works for all cases" — each point must be a complete statement that teaches something.
  - main_concept: the one idea this card is responsible for teaching
  - new_concepts: concepts first introduced on this card
  - review_concepts: concepts already introduced earlier but used here
  - prerequisite_concepts: concepts the learner needs before this card makes sense
  - related_formulas: formulas used or introduced on this card, or []
  - related_symbols: symbols used or introduced on this card, or []
  - common_misconceptions: predictable misunderstandings for this card, or []
  - concept_support: objects with concept, state_hint, support, hover_explanation. Use state_hint values unknown, familiar, fragile, stable, or transferable. Use support values main_explain, short_reminder, repair, hover_only, or skip.
  - interactive_links: sparse popup link objects for prerequisite blockers on this card. Each object must include text, explanation, why_it_matters_here, action, and target.
    Interactive link rules:
    - Use [] when no prerequisite popup is needed.
    - Keep 0 to 3 links per card unless this is a Terminology / Vocabulary topic.
    - Link only concepts, symbols, notation, visual labels, or phrases that could block understanding of this specific card.
    - Do not link the concept currently being taught by this card.
    - Do not link a term just because it is technical; link it only if not knowing it would make the card harder to understand.
    - Only link the first meaningful occurrence in the topic unless the term appears in a new context or the learner is fragile on it.
    - Use action "popup_only" for 1 to 4 line clarifications.
    - Use action "open_study_path" only for large prerequisite concepts that need examples/practice.
    - Use action "review_earlier_topic" if the concept was already covered earlier in this study path.
    - Use target as the earlier topic title, prerequisite concept name, or empty string.
  - styled_elements: structured non-image teaching supports.
    MANDATORY: Every card whose blueprint stage rule specifies a REQUIRED styled element MUST include at least one styled_elements item matching that type.
    MANDATORY: Tables, comparison grids, checklists, timelines, code blocks, LaTeX/formula steps, proof skeletons, decision matrices, workflow maps, glossary tables, symbol tables, and input/output tables MUST appear as styled_elements — never as visual_plan items. A visual_plan item for a table will produce a broken visual.
    Use [] only when no structured non-image support of any kind is needed.
    Each styled element must include type, title, and data. Supported types: table, comparison, comparison_table, checklist, timeline, formula_steps, proof_skeleton, decision_matrix, workflow_map, glossary_table, input_output_table, stage_map, term_map, code_block.
    Recommended data shapes:
    - table/comparison_table/glossary_table/input_output_table/decision_matrix: {{"columns": [...], "rows": [[...]]}}
    - checklist/timeline/proof_skeleton/workflow_map/stage_map/term_map: {{"items": [{{"label": "...", "description": "..."}}]}}
    - formula_steps: {{"steps": [{{"latex": "...", "reason": "..."}}]}}
    - code_block: {{"language": "python", "code": "..."}}
  - visual_plan: a lightweight per-card inline visual object. Only use this for inline code_block visuals that can be fully described in the card itself (code snippet + columns + rows). For ALL other visual types — node_link_diagram, graph, circuit_diagram, spatial_diagram, step_flow, etc. — put the full visual in the top-level visual_plan array and set visual_index to point to it. Leave per-card visual_plan as type="" title="" with empty arrays for those cards. The per-card schema only supports: type, title, purpose, code, language, columns, rows, highlight_row.
  - annotations: labels explaining what to notice in the visual, or []
  - example: a short concrete example, or ""
  - micro_check: {{type, prompt, answer}}. REQUIRED non-empty on every card whose blueprint stage rule specifies a REQUIRED microcheck. Use empty strings only for cards with no microcheck requirement and no natural check point.
  - deeper_explanation: optional extra explanation, or ""
  - what_to_notice: one short attention cue, or ""
  - next_transition: a short transition to the next card
  - quality_score: internal clarity score from 0 to 100
  - body: supplementary fallback only — 0 to 2 short paragraphs. Primary content goes in points. Do not use body as the main teaching field.
  - bullets: concise supporting points, or []
  - estimated_seconds: 20 to 90 for normal cards, 10 to 45 for quick_practice cards
  - transition_text: one short sentence explaining why the next idea comes next
  - next_card_label: specific continue button text for the next step
  - practice_question_index: zero-based index into practice_questions when card_type is quick_practice, otherwise -1
  - visual_index: zero-based index into visual_plan when the card should render a visual, otherwise -1.
    CRITICAL visual_index rules:
    - For any card whose focal teaching element is a node_link_diagram, graph, or circuit_diagram:
      you MUST set visual_index to the matching index in the top-level visual_plan array.
      The top-level visual_plan is the only place those complex visuals are fully rendered.
      The card's per-card visual_plan for these types is a schema-required placeholder only —
      leave nodes, data_points, components, and wires as empty arrays in the per-card visual_plan
      and put the real, complete data in the top-level visual_plan item.
    - For code_block or other genuinely non-text visual types that you can fill completely inline, you may put full data
      in the per-card visual_plan and set visual_index to -1.
    - Never set visual_index to -1 for a card that needs a node_link_diagram, graph, or circuit_diagram.
- Put quick_practice cards after key explanations, not only at the end.
- Use the pattern idea card -> visual/example card -> micro-check whenever useful.
- For every concept-introducing card, add a renderable visual whenever the concept has a natural non-text representation. For example, when introducing a BST, include a node_link_diagram of an actual BST rather than only describing the ordering rule.
- If a visual is applicable but not the focal card, set visual_index to the matching top-level visual or include a complete per-card code_block.
- For graph algorithms such as Prim's algorithm, Dijkstra's algorithm, BFS, DFS, MSTs, or shortest paths, use a sequence of visual cards where each card has a node_link_diagram and/or code_block showing exactly one state update.
- For PDF/CDF/distribution topics, use graph cards early and often: show the PDF curve, the CDF curve, shaded/accumulated area when useful, and key_points for important values.
- For formula topics, split notation into small cards and render equations in LaTeX text, not as formula visuals.
- For coding/data structure topics, include code/data trace cards.
- Use bridge_to_next_topic as the final card when the next idea can be previewed.
- Do not create giant text walls. Prefer more cards over longer cards.
- Card clarity rule: a card should have one main_concept, explain all new terms/symbols/formulas it introduces, avoid skipped reasoning steps, include a concrete example when abstraction would be hard, and flag common misconceptions when predictable.
- Adaptive depth rule: fully explain the new idea this card is responsible for. For concepts already covered before, adapt explanation depth based on the learner's concept state. Do not bloat the card by reteaching stable or transferable concepts, but never leave fragile or unknown concepts unsupported.
- Every practice question must be tied to a specific concept or section from the current lesson.
- Practice must match the selected course type and TopicScopeContract.
- Practice cannot test must_not_teach or out_of_scope_content.
- For every practice question, fill concept_tested, related_section, and why_this_matters.
- The learner should understand why this question is being asked and how it connects to the topic they are learning.
- Feedback should be able to mention what concept was tested, so keep concept_tested learner-facing and specific.
- Practice must match the selected course type:
  - Algorithm Walkthrough: trace state, predict next state, final order/path/table, or complexity reasoning.
  - Coding Implementation: include at least one coding question with starter_code and visible test_cases.
  - Data Structure Operation: perform operation, choose final structure, identify invalid structure, or implement the operation when coding is relevant.
  - Math Formula / Method: include at least one math question with given values/assumptions and exact symbolic or numeric expected answer.
  - Proof / Reasoning: choose valid proof step/strategy, identify invalid reasoning, or complete proof skeleton.
  - Compare / Distinguish: use nuanced multiple_choice or short scenario classification.
  - Debugging / Error Diagnosis: choose likely cause, next diagnostic check, fix, or debug code/config.
  - Design / Decision: choose best option under constraints and identify the deciding criterion.
  - Terminology / Vocabulary: match term to example, label usage, or detect misuse.
  - Review / Refresh: use a short high-yield edge-case or weak-area check.
- Choose the practice type based on what mastery actually requires:
  - DFS, BFS, recursion, dynamic programming, data structures, APIs, SQL, or programming topics should include at least one coding question.
  - Algebra, calculus, physics, chemistry calculations, statistics, proofs, or formula-heavy topics should include at least one math question.
  - Concept comparison or misconception checks may use multiple_choice.
  - Explanations, definitions, and reasoning checks should use short_answer.
- Include at least one practice question that checks application or transfer when the topic supports it.
- Include at least one edge-case or misconception-oriented question when the topic supports it.
- Include enough practice questions to cover the major examples and edge cases. A lesson about BSTs should include at least one practice item about an unbalanced stick-shaped tree and its runtime consequence.
- For coding questions, include starter_code, language, and visible test_cases.
- Coding starter_code should be LeetCode-style: expose the class/function the student implements, and omit main/stdin boilerplate unless the problem specifically requires it.
- Use these default signatures when possible: Python solve(data: str), JavaScript solve(input), TypeScript solve(input: string): string, Java class Solution with solve(String input), C++ class Solution with solve(const string& input), C solve(const char* input).
- Coding test_cases must provide stdin-style input and exact stdout expected after stripping whitespace.
- For math questions, include given values or assumptions in given.
- For multiple_choice, include exactly four choices and do not reveal the correct answer in question_text.
- Do not reveal answers in visible question text. Put private answer keys in correct_answer and explanation.
- If formulas appear, explain each symbol.
- Include visual_plan only when there is a genuine non-text visual: graph, node-link diagram, code/state trace, circuit diagram, spatial diagram, or interactive parameter visual.
- If no genuine non-text visual is useful, return visual_plan as [].
- In text-only core generation mode, always return visual_plan as [] even when a visual would normally be useful.
- source_preview should briefly summarize what source material the lesson used. If no material was provided, say the lesson was generated from the study path goal and topic metadata.

Adaptation metadata rules:
Return adaptation_metadata as a JSON object.
Use it to summarize how the lesson was adapted.
If no adaptive instructions were provided, still include adaptation_metadata with default values.

Format:
{{
  "starting_mode": "full_teach | compressed_refresher | nuance_first | edge_cases | transfer_practice | default",
  "estimated_state": "unknown | familiar | fragile | stable | transferable | not_provided",
  "adaptation_summary": "One learner-facing sentence describing how Azalea chose the lesson depth.",
  "teaching_strategy": "One short phrase, such as foundation-first, compressed-refresher, nuance-first, edge-case-focused, or transfer-practice."
}}

Do not use judgmental or grading language in adaptation_summary.
Good:
"Azalea starts with a compressed refresher and focuses on the pieces most likely to need repair."
Bad:
"You failed the diagnostic, so Azalea made the lesson easier."

Visual rendering rules:
Use visual_plan for structured visuals the frontend can actually render.
Azalea visuals are not decorative images. They are learning tools that remove interpretation effort.
Every visual must show at least one non-text structure: a graph, node-link relation, code/state trace, circuit, spatial relationship, or parameter-driven change.
Text tables, concept maps, formula cards, path maps, prose flowcharts, and comparison cards are content styling, not visuals. Put that material in lesson cards instead.
Prefer high-value non-text visuals; use as many as needed for concept introductions and state-changing steps, but do not add low-value decorative visuals.
Choose the visual by asking: "What makes this idea easier to process in one attempt?"

Preferred visual types:

Use these visual categories when they genuinely fit:
1. graph_chart: line graph, scatter plot, bar chart, histogram, distribution curve, coordinate plane, growth-rate comparison, area-under-curve.
2. node_link_diagram: binary trees, BSTs, graph nodes, linked nodes, traversal arrows, parent-child relationships.
3. circuit_diagram: hardware circuits, MUX diagrams, logic gates, resistor/capacitor networks, voltage/current flow, schematic-style component wiring.
4. coding_visual/state_change: memory boxes, pointer diagram, stack/heap, recursion tree, call stack, array trace, linked list nodes, graph traversal, DP table, frontend/backend request flow, database relationship.
5. spatial_geometric: annotated spatial diagram, vector diagram, geometric construction, coordinate transformation, matrix transformation, shape relationship.
6. interactive_change: slider-style cases, toggle-style cases, input-output simulator, parameter adjustment card, small sandbox.

Implementation note:
- These categories should still use the compact fields below so generation stays fast.
- Do not use concept_structure, process_flow, formula_breakdown, comparison_visual, source_annotation, learning_path, misconception_visual, or practice_feedback unless the user explicitly asks for that styled content.
- Equations must be written in lesson text with LaTeX delimiters, not as formula_card visual_plan items.
- For state_change and coding_visual use code_block fields.
- For node_link_diagram use nodes, edges, and traversal_path.
- For circuit_diagram use components and wires.
- For graph_chart use graph fields.
- For spatial_geometric use spatial_diagram fields.
- For interactive_change use interactive_parameter fields.

1. concept_table (avoid)
Do not use this as a visual unless the user explicitly asks for table-style content. Put term comparisons in normal lesson cards.

Use when the learner needs to understand multiple related terms, components, cases, or definitions.
Keep cells concise. Put the term/component in the first column and the practical meaning or role in later columns.

Format:
{{
  "type": "concept_table",
  "title": "Short visual title",
  "purpose": "Why this table helps",
  "placement": "where this should appear in the lesson",
  "columns": ["Column 1", "Column 2", "Column 3"],
  "rows": [
    ["...", "...", "..."],
    ["...", "...", "..."]
  ]
}}

2. comparison_table (avoid)
Do not use this as a visual unless the user explicitly asks for table-style content. Put comparisons in normal lesson cards.

Use when comparing two or more concepts, methods, cases, or assumptions.
Use parallel row labels so differences are easy to scan. Avoid paragraphs inside cells.

Format:
{{
  "type": "comparison_table",
  "title": "Short visual title",
  "purpose": "Why this comparison helps",
  "placement": "where this should appear in the lesson",
  "columns": ["Feature", "Concept A", "Concept B"],
  "rows": [
    ["...", "...", "..."],
    ["...", "...", "..."]
  ]
}}

3. step_flow (avoid unless it is a state transition diagram)
Do not use prose-only step flows as visuals. For algorithms, prefer node_link_diagram, code_block, or graph state cards.

Use when the topic is a process, algorithm, method, proof structure, or decision sequence.
Each step must be an action or decision with a reason. Labels should be short, like "Identify givens" or "Apply the rule".

Format:
{{
  "type": "step_flow",
  "title": "Short visual title",
  "purpose": "Why this flow helps",
  "placement": "where this should appear in the lesson",
  "steps": [
    {{
      "label": "Step 1",
      "description": "What happens and why"
    }},
    {{
      "label": "Step 2",
      "description": "What happens and why"
    }}
  ]
}}

4. formula_card (do not use)
Do not use formula_card or formula_breakdown visuals. Render equations in lesson text with LaTeX delimiters and explain symbols in cards.

Use when a formula, equation, or symbolic rule is central to the topic.
Use plain text formulas with readable operators. Define every symbol that appears in the formula.

Format:
{{
  "type": "formula_card",
  "title": "Short visual title",
  "purpose": "Why this formula card helps",
  "placement": "where this should appear in the lesson",
  "formula": "Plain text formula",
  "symbols": [
    {{
      "symbol": "x",
      "meaning": "what x means"
    }},
    {{
      "symbol": "n",
      "meaning": "what n means"
    }}
  ],
  "when_to_use": "When this formula applies",
  "common_mistake": "A common mistake to avoid"
}}

5. example_trace (avoid unless it is a quantitative or executable state trace)
Do not use text-only worked-solution tables as visuals. Prefer code_block for execution and graph/node/circuit visuals when the structure matters.

Use when a worked example has moving state, variables, rows, iterations, recursion, probability conditioning, database operations, or algorithm execution.
Use this for step-by-step diagrams of changing values. Each row should show what changed and why.

Format:
{{
  "type": "example_trace",
  "title": "Short visual title",
  "purpose": "Why this trace helps",
  "placement": "where this should appear in the lesson",
  "columns": ["Step", "State", "Reason"],
  "rows": [
    ["...", "...", "..."],
    ["...", "...", "..."]
  ]
}}

6. concept_map (do not use)
Do not use concept maps as visuals. If the idea is mostly parts and relationships in text, use normal cards; if it is a real network, use node_link_diagram with coordinates and edges.

Use when the learner needs to understand how an idea is made of parts, or how a central concept connects to related components.
Use for: data structures (parts of a linked list), formulas (what each variable represents), systems (parts of a neural network), scientific models, frameworks.
Components before process — always show what the pieces are before showing how they work together.

Format:
{{
  "type": "concept_map",
  "title": "Short visual title",
  "purpose": "Why this map helps",
  "placement": "where this should appear in the lesson",
  "center": "Main concept name or description",
  "nodes": [
    {{
      "label": "Component or part name",
      "relation": "one short word like controls, defines, stores, sets",
      "description": "What this component does in one sentence"
    }}
  ]
}}

7. graph
Use when a math function, trend, distribution, or numeric relationship is central to understanding.
Use for: quadratic or linear functions, probability distributions (CDF, PDF), runtime growth curves (Big-O), ML loss curves, economics supply/demand, physics motion.
MANDATORY: Compute data_points yourself for the full x_range. Include 10 to 15 [x, y] pairs to show shape clearly — more near curves and extrema. A graph visual with fewer than 2 data_points will not render. Never emit a graph without data_points.
Include key_points for roots, vertices, intercepts, inflection points, and other critical features.

Pre-computed reference data_points for common graph types (use these exactly or adapt for your range):
- Normal PDF (mean=0, std=1): [[-3,0.004],[-2.5,0.018],[-2,0.054],[-1.5,0.130],[-1,0.242],[-0.5,0.352],[0,0.399],[0.5,0.352],[1,0.242],[1.5,0.130],[2,0.054],[2.5,0.018],[3,0.004]]
- Normal CDF (mean=0, std=1): [[-3,0.001],[-2.5,0.006],[-2,0.023],[-1.5,0.067],[-1,0.159],[-0.5,0.309],[0,0.500],[0.5,0.691],[1,0.841],[1.5,0.933],[2,0.977],[2.5,0.994],[3,0.999]]
- Exponential PDF (lambda=1): [[0,1.0],[0.5,0.607],[1,0.368],[1.5,0.223],[2,0.135],[2.5,0.082],[3,0.050],[3.5,0.030],[4,0.018],[4.5,0.011],[5,0.007]]
- Quadratic y=x^2: [[-3,9],[-2,4],[-1.5,2.25],[-1,1],[-0.5,0.25],[0,0],[0.5,0.25],[1,1],[1.5,2.25],[2,4],[3,9]]
- O(n log n): [[1,0],[2,2],[4,8],[8,24],[16,64],[32,160],[64,384],[128,896]]
- O(n^2): [[1,1],[2,4],[4,16],[8,64],[16,256],[32,1024],[64,4096]]
- O(log n): [[1,0],[2,1],[4,2],[8,3],[16,4],[32,5],[64,6],[128,7]]
- Sigmoid: [[-6,0.002],[-4,0.018],[-2,0.119],[-1,0.269],[0,0.500],[1,0.731],[2,0.881],[4,0.982],[6,0.998]]

Format:
{{
  "type": "graph",
  "title": "Short visual title",
  "purpose": "Why this graph helps",
  "placement": "where this should appear in the lesson",
  "x_label": "x-axis label",
  "y_label": "y-axis label",
  "data_points": [[-2, 4], [-1, 1], [0, 0], [1, 1], [2, 4]],
  "key_points": [
    {{"x": 0, "y": 0, "label": "vertex (minimum)"}}
  ],
  "what_to_notice": "One sentence about what the learner should observe in this graph",
  "common_mistake": "A common mistake to avoid when reading or using this graph"
}}

8. code_block
Use when a coding or algorithm concept needs to show how variables, pointers, or data structures change step by step during execution.
Use for: sorting algorithms, recursion, loop iterations, pointer movement, stack frames, graph traversal, DP table construction.
Show the actual code snippet, then trace each meaningful state change in rows.
The first column should be a step identifier. Other columns show the state that changed.

Format:
{{
  "type": "code_block",
  "title": "Short visual title",
  "purpose": "Why this trace helps",
  "placement": "where this should appear in the lesson",
  "code": "actual code snippet here — keep it short, 4 to 8 lines",
  "language": "python or javascript or java or pseudocode",
  "columns": ["Step", "Array state", "Action taken"],
  "rows": [
    ["Start", "arr = [5, 3, 1]", "Initial state"],
    ["i=0, j=0", "arr = [3, 5, 1]", "Swapped 5 and 3 since 5 > 3"]
  ],
  "highlight_row": -1
}}

9. misconception
Use when students predictably apply a wrong mental model to this concept.
Use for: average of averages, correlation vs causation, greedy failures, common algebra mistakes, confusing similar-sounding concepts.
This should appear at the moment in the lesson where the mistake most naturally occurs.

Format:
{{
  "type": "misconception",
  "title": "Short learner-facing title describing the misconception",
  "purpose": "Why showing this misconception helps",
  "placement": "where this should appear in the lesson",
  "wrong_label": "Common mistake",
  "wrong": "The incorrect belief or reasoning, written as a student would state it",
  "correct_label": "What is actually true",
  "correct": "The correct understanding, stated clearly",
  "why": "Why the wrong reasoning fails — the key insight that breaks the misconception",
  "counterexample": "A concrete example that breaks the misconception"
}}

10. causal_chain
Use when the topic explains why one thing leads to another — a chain of dependencies or effects.
Use for: economic effects, biological pathways, debugging chains, physics cause and effect, software request flows, historical event chains.
Each step is one cause or effect. The description explains why it leads to the next step.

Format:
{{
  "type": "causal_chain",
  "title": "Short visual title",
  "purpose": "Why this chain helps",
  "placement": "where this should appear in the lesson",
  "steps": [
    {{
      "label": "Cause or effect name",
      "description": "What happens here and why it leads to the next step"
    }}
  ]
}}

11. spatial_diagram
Use when an idea is inherently spatial: geometry, vectors, force diagrams, anatomy, chemistry, coordinate transformations, matrix transformations, or shape relationships.
Use center for the central object, nodes for labeled parts, and key_points for coordinates or landmarks.

Format:
{{
  "type": "spatial_diagram",
  "title": "Short visual title",
  "purpose": "Why this diagram helps",
  "placement": "where this should appear in the lesson",
  "center": "Main object or relationship",
  "nodes": [
    {{
      "label": "Part or region",
      "relation": "relation to center",
      "description": "What this part means"
    }}
  ],
  "key_points": [
    {{"x": 1, "y": 2, "label": "important point"}}
  ]
}}

12. interactive_parameter
Use when changing one input changes an output.
Use rows as cases. The first column is the selectable case/input; later columns show what changes.
Use for graph coefficients, probability sample size, sorting state, physics parameters, model weights, or input-output simulators.

Format:
{{
  "type": "interactive_parameter",
  "title": "Short visual title",
  "purpose": "Why changing the parameter helps",
  "placement": "where this should appear in the lesson",
  "columns": ["Input / case", "What changes", "Why it changes"],
  "rows": [
    ["a = 1", "Parabola opens upward", "Positive a makes y grow away from the vertex"],
    ["a = -1", "Parabola opens downward", "Negative a flips outputs vertically"]
  ],
  "what_to_notice": "One sentence about the relationship the learner should notice"
}}

13. source_annotation
Use when explaining uploaded source material, a textbook excerpt, lecture phrase, slide wording, problem statement, or diagram label.
Use code for the excerpt text, labels for margin callouts, and nodes for source parts.

Format:
{{
  "type": "source_annotation",
  "title": "Short visual title",
  "purpose": "Why this source annotation helps",
  "placement": "where this should appear in the lesson",
  "code": "short source excerpt or problem statement",
  "labels": [
    {{"target": "phrase or symbol", "text": "what this part means"}}
  ],
  "nodes": [
    {{"label": "source part", "relation": "means", "description": "explanation"}}
  ]
}}

14. path_map
Use when showing where the learner is in a topic, prerequisite chain, concept dependency, review queue, weak area path, or progress sequence.
Use steps as the path.

Format:
{{
  "type": "path_map",
  "title": "Short visual title",
  "purpose": "Why this map helps",
  "placement": "where this should appear in the lesson",
  "steps": [
    {{"label": "Previous idea", "description": "What this contributes"}},
    {{"label": "Current idea", "description": "What the learner is doing now"}},
    {{"label": "Next idea", "description": "What this prepares for"}}
  ]
}}

15. practice_feedback
Use after a practice attempt or in a repair card to show where reasoning diverges.
Use wrong/correct for answer comparison and steps for the reasoning trace.

Format:
{{
  "type": "practice_feedback",
  "title": "Short visual title",
  "purpose": "Why this feedback helps",
  "placement": "where this should appear",
  "wrong_label": "Current reasoning",
  "wrong": "Where the user or common reasoning goes off track",
  "correct_label": "Target reasoning",
  "correct": "The corrected reasoning",
  "why": "The exact break point",
  "steps": [
    {{"label": "Break point", "description": "What needs to change"}}
  ]
}}

16. node_link_diagram
Use when the learner must see nodes connected by edges: binary trees, BST traversal, graph traversal, linked lists, recursion trees, dependency graphs.
Use normalized coordinates from 0 to 100 for x and y. For trees, put the root near x=50,y=12 and children lower.
Use edges for structural links and traversal arrows. Use style "solid" for structure and "traversal" or "dashed" for visit order arrows.

Format:
{{
  "type": "node_link_diagram",
  "title": "Short visual title",
  "purpose": "Why this node-link diagram helps",
  "placement": "where this should appear",
  "nodes": [
    {{"id": "1", "label": "1", "relation": "root", "description": "Visited first", "x": 50, "y": 12}},
    {{"id": "2", "label": "2", "relation": "left child", "description": "Visited after root", "x": 30, "y": 34}}
  ],
  "edges": [
    {{"from": "1", "to": "2", "label": "left", "style": "solid"}},
    {{"from": "1", "to": "2", "label": "visit", "style": "traversal"}}
  ],
  "traversal_path": ["1", "2"]
}}

17. circuit_diagram
Use for hardware classes, circuits, digital logic, gates, voltage/current flow, and schematic relationships.
Use components for parts and wires for connections. Component type examples: source, resistor, capacitor, ground, switch, led, and_gate, or_gate, not_gate, input, output.
Use normalized coordinates from 0 to 100 for x and y.

Format:
{{
  "type": "circuit_diagram",
  "title": "Short visual title",
  "purpose": "Why this circuit helps",
  "placement": "where this should appear",
  "components": [
    {{"id": "vin", "type": "source", "label": "Vin", "value": "5V", "x": 15, "y": 35}},
    {{"id": "r1", "type": "resistor", "label": "R1", "value": "1k ohm", "x": 45, "y": 35}},
    {{"id": "gnd", "type": "ground", "label": "GND", "value": "0V", "x": 75, "y": 50}}
  ],
  "wires": [
    {{"from": "vin", "to": "r1", "label": "current path", "style": "solid"}},
    {{"from": "r1", "to": "gnd", "label": "return", "style": "solid"}}
  ],
  "what_to_notice": "One sentence about the signal/current/logic relationship"
}}

Rules for visual_plan:
- Include visual_plan only for genuine non-text visuals.
- Never use concept_map as a fallback.
- Prefer high-value visuals; use as many as needed for concept introductions and state-changing steps, but avoid low-value decorative visuals.
- Every visual must be grounded in the uploaded material, the learner goal, or basic prerequisite context.
- Do not include decorative visuals.
- Do not include Mermaid, SVG, HTML, Markdown tables, or code blocks.
- Return visual_plan as JSON objects only.
- Every visual_plan object must include all supported keys so the UI can render it predictably:
  kind, type, title, description, purpose, placement, elements, highlight, labels,
  columns, rows, steps, formula, symbols, when_to_use, common_mistake,
  center, nodes, edges, traversal_path, components, wires,
  x_label, y_label, data_points, key_points, what_to_notice,
  code, language, highlight_row, wrong, correct, wrong_label, correct_label,
  why, counterexample.
- Fill only the fields relevant to the visual type. For unused fields, use "" for strings, [] for arrays, and -1 for highlight_row.
- For concept_table, comparison_table, worked_example_trace, comparison_visual, and Venn/same-different visuals: avoid these unless explicitly requested.
- For example_trace: use only when rows represent changing numeric, code, algorithmic, or state data.
- For step_flow and process_flow: fill steps.
- For causal_chain and cause_effect: fill steps.
- For formula_card and formula_breakdown: do not use; put equations in LaTeX lesson text.
- For concept_map and concept_structure: do not use; use node_link_diagram for real networks or normal cards for text relationships.
- For graph and graph_chart: compute and fill data_points (10-15 points), key_points, x_label, y_label, what_to_notice.
- For code_block, state_change, and coding_visual: fill code, language, columns, and rows. Set highlight_row to -1 if unused.
- For node_link_diagram: fill nodes, edges, traversal_path, and what_to_notice.
- For circuit_diagram: fill components, wires, and what_to_notice.
- For misconception and misconception_visual: prefer normal mistake cards unless a diagrammatic counterexample is essential.
- For spatial_diagram and spatial_geometric: fill center, nodes, and key_points when useful.
- For interactive_parameter and interactive_change: fill columns, rows, and what_to_notice.
- For source_annotation, path_map, learning_path, and practice_feedback: avoid as generated visuals unless explicitly requested.
- When the topic is a process or algorithm, prefer node_link_diagram, graph, or code_block over prose.
- When the topic involves a math function or numeric trend, use graph.
- When the topic has a common student mistake, add a misconception visual.
- When explaining code execution, use code_block instead of example_trace.
- When showing what a concept is made of, use normal cards unless the relationships form a real node-link structure.
- When the topic is spatial or geometric, use spatial_diagram.
- When changing an input changes an output, use interactive_parameter.
- When the uploaded source wording matters, use source_annotation.
- When orientation or prerequisites matter, use normal orientation cards.
- When repairing a practice mistake, use a normal mistake card unless a graph/node/circuit/code visual clarifies it.

Strict visual_plan output rules:
- Do NOT copy these instructions into the lesson.
- Do NOT describe what kind of visual could be created.
- Do NOT include prompt text, format examples, or schema explanations in visual_plan.
- Every visual_plan item must be an actual finished visual object for this specific topic.
- If you cannot create a concrete finished visual, return visual_plan as [].
- visual_plan.purpose must be one short sentence, not instructions.
- visual_plan.title must be a learner-facing title, not a visual type explanation.
- rows, columns, steps, nodes, data_points, and formula must contain actual lesson content, not placeholder text.
- Never put an equation primarily inside a visual. Use LaTeX in lesson card text instead.
"""
