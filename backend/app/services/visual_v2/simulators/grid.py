"""Grid/DP simulators (VISUAL_SYSTEM_SPEC §6.1).

unique_paths: classic 2-D DP — dp[i][j] = dp[i-1][j] + dp[i][j-1], edges = 1. Each
step fills one cell, recording the active cell, its value, the two dependency
arrows it sums, and completion. The simulator owns the trace.
"""
from __future__ import annotations

from ..schemas import (
    DELTA_SCHEMA_VERSION,
    SIMULATOR_VERSION,
    VISUAL_SPEC_VERSION,
    CanonicalExample,
    Trace,
    TraceStep,
)


def simulate_unique_paths(example: CanonicalExample) -> Trace:
    base = example.get("base_structure") or {}
    rows = int(base.get("rows") or 0)
    cols = int(base.get("cols") or 0)
    dp = [[0] * cols for _ in range(rows)]
    steps: list[TraceStep] = []

    for i in range(rows):
        for j in range(cols):
            delta: dict = {"set_active_cell": [i, j]}
            if i == 0 or j == 0:
                dp[i][j] = 1
                notice = f"Edge cell ({i},{j}): only one way to reach it → 1."
            else:
                dp[i][j] = dp[i - 1][j] + dp[i][j - 1]
                delta["set_dependency_arrows"] = [
                    {"from": [i - 1, j], "to": [i, j]},
                    {"from": [i, j - 1], "to": [i, j]},
                ]
                notice = f"({i},{j}) = ({i-1},{j}) + ({i},{j-1}) = {dp[i-1][j]} + {dp[i][j-1]} = {dp[i][j]}."
            delta["fill_cell"] = {"cell": [i, j], "value": dp[i][j]}
            delta["complete_cell"] = [i, j]
            steps.append(
                TraceStep(
                    step_index=len(steps),
                    trace_step_id=f"s{len(steps)}",
                    kind="fill_cell",
                    delta=delta,
                    primary_change="fill_cell",
                    learner_should_notice=notice,
                )
            )

    return Trace(
        trace_id=f"{example.get('example_id', 'ex')}:unique_paths",
        example_id=str(example.get("example_id", "")),
        trace_source="deterministic_simulator",
        initial_state={"active_cell": None, "completed_cells": [], "cell_values": {}, "dependency_arrows": []},
        steps=steps,
        visual_spec_version=VISUAL_SPEC_VERSION,
        delta_schema_version=DELTA_SCHEMA_VERSION,
        simulator_version=SIMULATOR_VERSION,
    )


def simulate_coin_change(example: CanonicalExample) -> Trace:
    """Min-coins DP on a 1 x (amount+1) strip: dp[j] = 1 + min(dp[j - coin]) over
    coins that fit; dp[0] = 0. Each step fills one cell with its dependency arrows."""
    base = example.get("base_structure") or {}
    coins = [int(c) for c in (base.get("coins") or [])]
    amount = int(base.get("amount") or (int(base.get("cols") or 1) - 1))
    if not coins or amount < 0:
        raise ValueError("coin_change requires coins[] and amount >= 0")

    INF = float("inf")
    dp: list[float] = [0.0] + [INF] * amount
    steps: list[TraceStep] = []

    def emit(j: int, value: float, deps: list[int], notice: str) -> None:
        delta: dict = {"set_active_cell": [0, j]}
        if deps:
            delta["set_dependency_arrows"] = [{"from": [0, d], "to": [0, j]} for d in deps]
        shown = "-" if value == INF else str(int(value))
        delta["fill_cell"] = {"cell": [0, j], "value": shown}
        delta["complete_cell"] = [0, j]
        steps.append(TraceStep(
            step_index=len(steps), trace_step_id=f"s{len(steps)}", kind="fill_cell",
            delta=delta, primary_change="fill_cell", learner_should_notice=notice,
        ))

    emit(0, 0, [], "Amount 0 needs zero coins — the base case.")
    for j in range(1, amount + 1):
        candidates = [(dp[j - coin] + 1, j - coin, coin) for coin in coins if coin <= j and dp[j - coin] != INF]
        if candidates:
            best, src, coin = min(candidates)
            dp[j] = best
            others = sorted({j - c for c in coins if c <= j and dp[j - c] != INF})
            emit(j, best, others,
                 f"Amount {j}: best is amount {src} ({int(dp[src])} coins) + one {coin}-coin = {int(best)}.")
        else:
            emit(j, INF, [], f"Amount {j}: no combination of these coins reaches it.")

    return Trace(
        trace_id=f"{example.get('example_id', 'ex')}:coin_change",
        example_id=str(example.get("example_id", "")),
        trace_source="deterministic_simulator",
        initial_state={"active_cell": None, "completed_cells": [], "cell_values": {}, "dependency_arrows": []},
        steps=steps,
        visual_spec_version=VISUAL_SPEC_VERSION,
        delta_schema_version=DELTA_SCHEMA_VERSION,
        simulator_version=SIMULATOR_VERSION,
        final_state={},
    )
