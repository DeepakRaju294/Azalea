"""Canonical displayed solutions for adapter-supported coding topics.

ONE verified source of truth per algorithm: the **Python** implementation. It is execution-tested (see
test_canonical_solutions), and it is what the learner sees on a Python path. For a C++ / Java (or any future)
path the Python is **adapted on demand** by a focused LLM translation and cached per (algorithm, language), so
each translation happens once and is reused everywhere. Design rules (ADAPTER_AND_GENERATION_SYSTEM_SPEC
`canonical_code`):

  * Simplest solution a good engineer / solution guide would write FIRST — favour clarity at equal efficiency
    (recursive DFS over an explicit stack, iterative binary search, etc.).
  * Stored WITH imports so the Python is genuinely runnable / verifiable; imports are STRIPPED for display.
  * No hardcoded example values — general implementations, parameterised by their inputs.

Keyed by adapter slug (the slug `route_adapter` returns)."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Callable, Optional

# --- the ONE verified source per algorithm: Python (with imports) -------------------------------------
CANONICAL_SOLUTIONS: dict[str, str] = {
    "bfs": """from collections import deque


def bfs(graph, start):
    visited = {start}
    order = []
    queue = deque([start])
    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbor in graph[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return order
""",
    # DFS recursive — simpler than an explicit stack, equally efficient.
    "dfs_iter": """def dfs(graph, start, visited=None):
    if visited is None:
        visited = set()
    visited.add(start)
    order = [start]
    for neighbor in graph[start]:
        if neighbor not in visited:
            order += dfs(graph, neighbor, visited)
    return order
""",
    "kruskal": """def find(parent, u):
    while parent[u] != u:
        parent[u] = parent[parent[u]]
        u = parent[u]
    return u


def kruskal(n, edges):
    edges.sort(key=lambda e: e[2])
    parent = list(range(n))
    mst = []
    for u, v, w in edges:
        ru, rv = find(parent, u), find(parent, v)
        if ru != rv:
            parent[ru] = rv
            mst.append([u, v, w])
    return mst
""",
    "prim": """import heapq


def prim(graph, start):
    visited = {start}
    mst = []
    heap = [(w, start, v) for v, w in graph[start]]
    heapq.heapify(heap)
    while heap:
        w, u, v = heapq.heappop(heap)
        if v in visited:
            continue
        visited.add(v)
        mst.append([u, v, w])
        for nv, nw in graph[v]:
            if nv not in visited:
                heapq.heappush(heap, (nw, v, nv))
    return mst
""",
    "dijkstra": """import heapq


def dijkstra(graph, start):
    dist = {start: 0}
    heap = [(0, start)]
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist.get(u, float("inf")):
            continue
        for v, w in graph[u]:
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    return dist
""",
    "merge_sort": """def merge_sort(arr):
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])
    merged = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            merged.append(left[i])
            i += 1
        else:
            merged.append(right[j])
            j += 1
    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged
""",
    "binary_search": """def binary_search(arr, target):
    lo, hi = 0, len(arr) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
""",
    # ---- inorder traversal of a binary tree (recursion: left, node, right) ----
    # ---- tree traversals (ITERATIVE stack/queue forms — a step-by-step trace maps to the pop/visit/push loop,
    #      and the base case is visible, unlike a one-line recursion that repeats confusingly per visit) ----
    "tree_inorder": """def inorder(root):
    result = []
    stack = []
    node = root
    while stack or node:
        while node:
            stack.append(node)
            node = node.left
        node = stack.pop()
        result.append(node.val)
        node = node.right
    return result
""",
    "tree_preorder": """def preorder(root):
    result = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node is None:
            continue
        result.append(node.val)
        stack.append(node.right)
        stack.append(node.left)
    return result
""",
    "tree_postorder": """def postorder(root):
    result = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node is None:
            continue
        result.append(node.val)
        stack.append(node.left)
        stack.append(node.right)
    return result[::-1]
""",
    "tree_levelorder": """from collections import deque

def level_order(root):
    if root is None:
        return []
    out = []
    queue = deque([root])
    while queue:
        node = queue.popleft()
        out.append(node.val)
        if node.left:
            queue.append(node.left)
        if node.right:
            queue.append(node.right)
    return out
""",
    # ---- BST search (descend by comparison until found or a null child) ----
    "bst_search": """def search(node, target):
    if node is None:
        return None
    if target == node.val:
        return node
    if target < node.val:
        return search(node.left, target)
    return search(node.right, target)
""",
    "insertion_sort": """def insertion_sort(arr):
    for i in range(1, len(arr)):
        key = arr[i]
        j = i - 1
        while j >= 0 and arr[j] > key:
            arr[j + 1] = arr[j]
            j -= 1
        arr[j + 1] = key
    return arr
""",
    "selection_sort": """def selection_sort(arr):
    n = len(arr)
    for i in range(n - 1):
        min_idx = i
        for j in range(i + 1, n):
            if arr[j] < arr[min_idx]:
                min_idx = j
        arr[i], arr[min_idx] = arr[min_idx], arr[i]
    return arr
""",
    "bubble_sort": """def bubble_sort(arr):
    n = len(arr)
    for i in range(n - 1):
        swapped = False
        for j in range(n - 1 - i):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped = True
        if not swapped:
            break
    return arr
""",
    "quick_sort": """def quick_sort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[-1]
    smaller = [x for x in arr[:-1] if x < pivot]
    larger = [x for x in arr[:-1] if x >= pivot]
    return quick_sort(smaller) + [pivot] + quick_sort(larger)
""",
    "heap_sort": """def heap_sort(arr):
    n = len(arr)

    def sift_down(root, size):
        while 2 * root + 1 < size:
            child = 2 * root + 1
            if child + 1 < size and arr[child + 1] > arr[child]:
                child += 1
            if arr[root] >= arr[child]:
                break
            arr[root], arr[child] = arr[child], arr[root]
            root = child

    for i in range(n // 2 - 1, -1, -1):
        sift_down(i, n)
    for end in range(n - 1, 0, -1):
        arr[0], arr[end] = arr[end], arr[0]
        sift_down(0, end)
    return arr
""",
    "longest_increasing_subsequence": """def longest_increasing_subsequence(nums):
    if not nums:
        return 0
    dp = [1] * len(nums)
    for i in range(len(nums)):
        for j in range(i):
            if nums[j] < nums[i]:
                dp[i] = max(dp[i], dp[j] + 1)
    return max(dp)
""",
    "arithmetic_eval": """def evaluate(tokens):
    stack = [tokens[0]]
    i = 1
    while i < len(tokens):
        op, num = tokens[i], tokens[i + 1]
        if op == "*":
            stack[-1] *= num
        elif op == "+":
            stack.append(num)
        else:  # "-"
            stack.append(-num)
        i += 2
    return sum(stack)
""",
}

LANGUAGES = ("python", "cpp", "java")
_LANG_NAME = {"cpp": "C++", "java": "Java", "python": "Python"}

# import / boilerplate lines dropped for DISPLAY (the code still uses the facility; we hide the ceremony).
_IMPORT_LINE = {
    "python": re.compile(r"^\s*(?:import\s|from\s)"),
    "cpp": re.compile(r"^\s*(?:#include\b|using\s+namespace\b)"),
    "java": re.compile(r"^\s*import\s"),
}


def _strip_imports(code: str, lang: str) -> str:
    pat = _IMPORT_LINE.get(lang)
    if pat is None:
        return code.strip("\n")
    kept = [ln for ln in code.splitlines() if not pat.match(ln)]
    while kept and not kept[0].strip():
        kept.pop(0)
    return "\n".join(kept).strip("\n")


# --- translation cache (translate Python -> other language ONCE, reuse everywhere) --------------------
_CACHE_FILE = Path(__file__).with_name("canonical_translations.json")
_cache: dict[str, str] = {}
_cache_loaded = False


def _ensure_cache_loaded() -> None:
    global _cache_loaded
    if _cache_loaded:
        return
    try:
        if _CACHE_FILE.exists():
            _cache.update(json.loads(_CACHE_FILE.read_text(encoding="utf-8")))
    except Exception:  # noqa: BLE001 — a corrupt cache must never break generation
        pass
    _cache_loaded = True


def _persist_cache() -> None:
    try:
        _CACHE_FILE.write_text(json.dumps(_cache, ensure_ascii=False, indent=0), encoding="utf-8")
    except Exception:  # noqa: BLE001 — read-only deploys just keep the in-memory cache
        pass


# Translator is injectable so tests can supply a deterministic stand-in. (python_code, lang) -> code|None.
TranslatorFn = Callable[[str, str], Optional[str]]


def _default_translator(python_code: str, lang: str) -> Optional[str]:
    """Translate the verified Python to a COMPLETE, idiomatic implementation in `lang`. RETRIES a few times so
    a transient LLM hiccup doesn't silently downgrade a whole path to Python; returns None only when offline or
    after every attempt fails (caller then keeps the Python)."""
    key = os.getenv("OPENAI_API_KEY")
    if not key or key.strip().lower() == "dummy":
        return None
    name = _LANG_NAME.get(lang, lang)
    system = (
        f"You translate a VERIFIED Python reference implementation into {name}. Produce a COMPLETE, "
        f"CORRECT, idiomatic {name} implementation of the SAME algorithm: same function name and "
        f"input/output shape, same logic. Include any imports/includes needed to compile. Do not add "
        f'example calls or I/O. Return ONLY JSON: {{"code": "<the {name} implementation>"}}.'
    )
    attempts = max(1, int(os.getenv("AZALEA_CANONICAL_TRANSLATE_ATTEMPTS", "3")))
    for _ in range(attempts):
        try:
            from app.services.llm_client import OPENAI_MODEL, client, llm_call

            with llm_call("canonical_translate"):
                resp = client.with_options(timeout=60, max_retries=2).responses.create(
                    model=OPENAI_MODEL,
                    input=[{"role": "system", "content": system},
                           {"role": "user", "content": f"Translate this Python to {name}:\n\n{python_code}"}],
                    text={"format": {"type": "json_object"}},
                )
            code = str((json.loads(resp.output_text) or {}).get("code") or "").strip()
            if code and len(code) > 20:        # a real translation, not an empty / truncated reply
                return code
        except Exception:  # noqa: BLE001 — retry transient failures before giving up
            continue
    return None


_translator: TranslatorFn = _default_translator


def set_translator(fn: TranslatorFn) -> None:
    """Override the Python->language translator (tests)."""
    global _translator
    _translator = fn


def canonical_python(slug: str) -> Optional[str]:
    """The complete (imports intact) verified Python solution — source of truth + execution check."""
    return CANONICAL_SOLUTIONS.get(slug)


def display_solution(slug: str, lang: str = "python") -> Optional[str]:
    """The learner-facing code for `slug` in `lang` (imports stripped). Python is returned directly; other
    languages are translated from the Python once and cached. None when the slug has no canonical, or when a
    non-Python translation is unavailable (offline / failure) — the caller then leaves the existing code."""
    src = CANONICAL_SOLUTIONS.get(slug)
    if not src:
        return None
    lang = (lang or "python").lower()
    if lang == "python":
        return _strip_imports(src, "python")
    _ensure_cache_loaded()
    key = f"{slug}::{lang}"
    code = _cache.get(key)
    if not code:
        code = _translator(src, lang)
        if code:
            _cache[key] = code
            _persist_cache()
    if not code:
        return None
    return _strip_imports(code, lang)
