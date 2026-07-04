"""T10 stateful CONCEPT SPECS (CP12e) — stateful-structure concepts on the stateful engine. Each is DATA: build
an instance (structure + operation script), apply the i-th operation, render the structure, the answer, and an
independent oracle (replay). Adding a concept = add a `StatefulSpec` to `ALL_SPECS`."""
from __future__ import annotations

import random

from .stateful_engine import StatefulSpec


def _seq(xs: list) -> str:
    return ", ".join(str(x) for x in xs) if xs else "empty"


# --- stack (LIFO): push / pop -------------------------------------------------------------------------
def _stack_setup(rng: random.Random) -> dict:
    ops: list = []
    model: list = []
    for _ in range(rng.randint(5, 7)):
        if model and rng.random() < 0.4:
            ops.append(("pop", 0))
            model.pop()
        else:
            v = rng.randint(1, 20)
            ops.append(("push", v))
            model.append(v)
    return {"ops": ops, "stack": []}


def _stack_apply(s: dict, i: int) -> tuple:
    kind, v = s["ops"][i]
    if kind == "push":
        return {**s, "stack": s["stack"] + [v]}, f"push {v}: place it on top"
    top = s["stack"][-1]
    return {**s, "stack": s["stack"][:-1]}, f"pop: remove the top element {top}"


def _stack_oracle(s0: dict) -> dict:
    stack: list = []
    for kind, v in s0["ops"]:
        stack.append(v) if kind == "push" else stack.pop()
    return {"final_stack": _seq(list(reversed(stack)))}         # top-first, to match the "top -> …" render


STACK_OPERATIONS = StatefulSpec(
    slug="stack_operations", title="a sequence of stack (LIFO) operations", family="structures",
    aliases=["stack operations", "push and pop", "lifo", "stack push pop"], priority=69, op_word="operation",
    problem_template="Apply the given push/pop operations to a stack and give the final stack.",
    setup=_stack_setup, ops_count=lambda s: len(s["ops"]), apply=_stack_apply,
    render=lambda s: f"top -> {_seq(list(reversed(s['stack'])))}",
    answer=lambda s: {"final_stack": _seq(list(reversed(s["stack"])))},
    oracle=_stack_oracle,
    target="every push and pop has been applied")


# --- queue (FIFO): enqueue / dequeue ------------------------------------------------------------------
def _queue_setup(rng: random.Random) -> dict:
    ops: list = []
    model: list = []
    for _ in range(rng.randint(5, 7)):
        if model and rng.random() < 0.4:
            ops.append(("dequeue", 0))
            model.pop(0)
        else:
            v = rng.randint(1, 20)
            ops.append(("enqueue", v))
            model.append(v)
    return {"ops": ops, "queue": []}


def _queue_apply(s: dict, i: int) -> tuple:
    kind, v = s["ops"][i]
    if kind == "enqueue":
        return {**s, "queue": s["queue"] + [v]}, f"enqueue {v}: add it at the back"
    front = s["queue"][0]
    return {**s, "queue": s["queue"][1:]}, f"dequeue: remove the front element {front}"


def _queue_oracle(s0: dict) -> dict:
    queue: list = []
    for kind, v in s0["ops"]:
        queue.append(v) if kind == "enqueue" else queue.pop(0)
    return {"final_queue": _seq(queue)}


QUEUE_OPERATIONS = StatefulSpec(
    slug="queue_operations", title="a sequence of queue (FIFO) operations", family="structures",
    aliases=["queue operations", "enqueue and dequeue", "fifo", "queue enqueue dequeue"], priority=68,
    op_word="operation",
    problem_template="Apply the given enqueue/dequeue operations to a queue and give the final queue.",
    setup=_queue_setup, ops_count=lambda s: len(s["ops"]), apply=_queue_apply,
    render=lambda s: f"front -> {_seq(s['queue'])}",
    answer=lambda s: {"final_queue": _seq(s["queue"])},
    oracle=_queue_oracle,
    target="every enqueue and dequeue has been applied")


# --- hash table with linear probing -------------------------------------------------------------------
def _hash_setup(rng: random.Random) -> dict:
    m = 7
    keys: list = []
    while len(keys) < rng.randint(4, 5):
        k = rng.randint(1, 40)
        if k not in keys:
            keys.append(k)
    return {"m": m, "keys": keys, "table": [None] * m}


def _hash_render(s: dict) -> str:
    return "slots: " + ", ".join(str(x) if x is not None else "-" for x in s["table"])


def _hash_apply(s: dict, i: int) -> tuple:
    key, m = s["keys"][i], s["m"]
    table = list(s["table"])
    h = key % m
    pos, probes = h, 0
    while table[pos] is not None:
        pos = (pos + 1) % m
        probes += 1
    table[pos] = key
    op = (f"insert {key}: hash {key} mod {m} = {h}, place at slot {h}" if probes == 0
          else f"insert {key}: hash {key} mod {m} = {h}; slot {h} full, linear-probe to slot {pos}")
    return {**s, "table": table}, op


def _hash_oracle(s0: dict) -> dict:
    m = s0["m"]
    table: list = [None] * m
    for key in s0["keys"]:
        pos = key % m
        while table[pos] is not None:
            pos = (pos + 1) % m
        table[pos] = key
    return {"final_table": "slots: " + ", ".join(str(x) if x is not None else "-" for x in table)}


HASH_TABLE_INSERT = StatefulSpec(
    slug="hash_table_insert", title="inserting into a hash table with linear probing", family="structures",
    # narrow aliases: a bare "Hash Tables" topic is conceptual (defers); this adapter is the INSERTION trace.
    aliases=["linear probing", "hash table insert", "insert into a hash table", "hash collision"],
    priority=67, op_word="insertion",
    problem_template="Insert the keys into a size-7 hash table using linear probing; give the final table.",
    setup=_hash_setup, ops_count=lambda s: len(s["keys"]), apply=_hash_apply,
    render=_hash_render, answer=lambda s: {"final_table": _hash_render(s)}, oracle=_hash_oracle,
    target="every key has been inserted")


# --- LRU cache: access keys, evicting the least-recently-used on overflow --------------------------
def _lru_setup(rng: random.Random) -> dict:
    return {"cap": 3, "accesses": [rng.randint(1, 5) for _ in range(rng.randint(6, 8))], "cache": []}


def _lru_apply(s: dict, i: int) -> tuple:
    key, cap = s["accesses"][i], s["cap"]
    cache = list(s["cache"])
    if key in cache:
        cache.remove(key); cache.insert(0, key)
        op = f"access {key}: hit, move it to most-recently-used"
    else:
        cache.insert(0, key)
        if len(cache) > cap:
            ev = cache.pop()
            op = f"access {key}: miss, add it; evict least-recently-used {ev}"
        else:
            op = f"access {key}: miss, add it"
    return {**s, "cache": cache}, op


def _lru_oracle(s0: dict) -> dict:
    cache: list = []
    for key in s0["accesses"]:
        if key in cache:
            cache.remove(key)
        elif len(cache) >= s0["cap"]:
            cache.pop()
        cache.insert(0, key)
    return {"final_cache": _seq(cache)}


LRU_CACHE = StatefulSpec(
    slug="lru_cache", title="an LRU cache under a sequence of accesses", family="structures",
    aliases=["lru cache", "least recently used", "cache eviction"], priority=66, op_word="access",
    problem_template="Process the key accesses through a capacity-3 LRU cache; give the final cache.",
    setup=_lru_setup, ops_count=lambda s: len(s["accesses"]), apply=_lru_apply,
    render=lambda s: f"most-recent -> {_seq(s['cache'])}",
    answer=lambda s: {"final_cache": _seq(s["cache"])}, oracle=_lru_oracle,
    target="every access has been processed")


# --- modular counter: add amounts, wrapping mod m -----------------------------------------------------
def _mod_setup(rng: random.Random) -> dict:
    return {"m": rng.randint(5, 9), "incs": [rng.randint(1, 4) for _ in range(rng.randint(4, 6))], "value": 0}


def _mod_apply(s: dict, i: int) -> tuple:
    inc, m = s["incs"][i], s["m"]
    new = (s["value"] + inc) % m
    return {**s, "value": new}, f"add {inc}: ({s['value']} + {inc}) mod {m} = {new}"


def _mod_oracle(s0: dict) -> dict:
    v = 0
    for inc in s0["incs"]:
        v = (v + inc) % s0["m"]
    return {"final_value": str(v)}


MODULAR_COUNTER = StatefulSpec(
    slug="modular_counter", title="a modular counter under a sequence of increments", family="structures",
    aliases=["modular counter", "mod counter", "counter modulo"], priority=65, op_word="increment",
    problem_template="Apply the increments to a counter that wraps modulo m; give the final value.",
    setup=_mod_setup, ops_count=lambda s: len(s["incs"]), apply=_mod_apply,
    render=lambda s: f"counter = {s['value']}",
    answer=lambda s: {"final_value": str(s["value"])}, oracle=_mod_oracle,
    target="every increment has been applied")


ALL_SPECS = [STACK_OPERATIONS, QUEUE_OPERATIONS, HASH_TABLE_INSERT, LRU_CACHE, MODULAR_COUNTER]
