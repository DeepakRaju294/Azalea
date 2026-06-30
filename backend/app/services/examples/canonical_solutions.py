"""Canonical displayed solutions for adapter-supported coding topics.

For a topic that routes to an adapter, the code the learner READS is no longer an LLM improvisation — it is the
verified, simplest-idiomatic reference solution kept here, offered in Python / C++ / Java so the learner can
toggle to the language they know. Design rules (ADAPTER_AND_GENERATION_SYSTEM_SPEC `canonical_code`):

  * Simplest solution a good engineer / solution guide would write FIRST — favour clarity at equal efficiency
    (recursive DFS over an explicit stack, iterative binary search, etc.).
  * Stored WITH imports so the Python form is genuinely runnable and build-time verifiable; the imports are
    STRIPPED for display (`display_solutions`) — the learner sees the algorithm, not boilerplate.
  * No hardcoded example values — these are general implementations, parameterised by their inputs.

The registry is keyed by adapter slug (the same slug `route_adapter` returns)."""
from __future__ import annotations

import re

# --- the solutions (stored complete, with imports) ----------------------------------------------------
CANONICAL_SOLUTIONS: dict[str, dict[str, str]] = {
    # ---- graph BFS (queue) ----
    "bfs": {
        "python": """from collections import deque


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
        "cpp": """#include <vector>
#include <queue>
#include <unordered_set>
using namespace std;

vector<int> bfs(vector<vector<int>>& graph, int start) {
    unordered_set<int> visited{start};
    vector<int> order;
    queue<int> q;
    q.push(start);
    while (!q.empty()) {
        int node = q.front();
        q.pop();
        order.push_back(node);
        for (int neighbor : graph[node]) {
            if (!visited.count(neighbor)) {
                visited.insert(neighbor);
                q.push(neighbor);
            }
        }
    }
    return order;
}
""",
        "java": """import java.util.*;

List<Integer> bfs(List<List<Integer>> graph, int start) {
    Set<Integer> visited = new HashSet<>(List.of(start));
    List<Integer> order = new ArrayList<>();
    Queue<Integer> queue = new ArrayDeque<>(List.of(start));
    while (!queue.isEmpty()) {
        int node = queue.poll();
        order.add(node);
        for (int neighbor : graph.get(node)) {
            if (!visited.contains(neighbor)) {
                visited.add(neighbor);
                queue.add(neighbor);
            }
        }
    }
    return order;
}
""",
    },
    # ---- graph DFS (recursive — simpler than an explicit stack, equally efficient) ----
    "dfs_iter": {
        "python": """def dfs(graph, start, visited=None):
    if visited is None:
        visited = set()
    visited.add(start)
    order = [start]
    for neighbor in graph[start]:
        if neighbor not in visited:
            order += dfs(graph, neighbor, visited)
    return order
""",
        "cpp": """#include <vector>
#include <unordered_set>
using namespace std;

void dfs(vector<vector<int>>& graph, int node,
         unordered_set<int>& visited, vector<int>& order) {
    visited.insert(node);
    order.push_back(node);
    for (int neighbor : graph[node]) {
        if (!visited.count(neighbor)) {
            dfs(graph, neighbor, visited, order);
        }
    }
}
""",
        "java": """import java.util.*;

void dfs(List<List<Integer>> graph, int node,
         Set<Integer> visited, List<Integer> order) {
    visited.add(node);
    order.add(node);
    for (int neighbor : graph.get(node)) {
        if (!visited.contains(neighbor)) {
            dfs(graph, neighbor, visited, order);
        }
    }
}
""",
    },
    # ---- Kruskal MST (sort edges + union-find) ----
    "kruskal": {
        "python": """def find(parent, u):
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
        "cpp": """#include <vector>
#include <algorithm>
using namespace std;

int find(vector<int>& parent, int u) {
    while (parent[u] != u) {
        parent[u] = parent[parent[u]];
        u = parent[u];
    }
    return u;
}

vector<vector<int>> kruskal(int n, vector<vector<int>>& edges) {
    sort(edges.begin(), edges.end(),
         [](auto& a, auto& b) { return a[2] < b[2]; });
    vector<int> parent(n);
    for (int i = 0; i < n; i++) parent[i] = i;
    vector<vector<int>> mst;
    for (auto& e : edges) {
        int ru = find(parent, e[0]), rv = find(parent, e[1]);
        if (ru != rv) {
            parent[ru] = rv;
            mst.push_back(e);
        }
    }
    return mst;
}
""",
        "java": """import java.util.*;

int find(int[] parent, int u) {
    while (parent[u] != u) {
        parent[u] = parent[parent[u]];
        u = parent[u];
    }
    return u;
}

int[][] kruskal(int n, int[][] edges) {
    Arrays.sort(edges, (a, b) -> a[2] - b[2]);
    int[] parent = new int[n];
    for (int i = 0; i < n; i++) parent[i] = i;
    List<int[]> mst = new ArrayList<>();
    for (int[] e : edges) {
        int ru = find(parent, e[0]), rv = find(parent, e[1]);
        if (ru != rv) {
            parent[ru] = rv;
            mst.add(e);
        }
    }
    return mst.toArray(new int[0][]);
}
""",
    },
    # ---- Prim MST (grow a tree with a min-heap) ----
    "prim": {
        "python": """import heapq


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
        "cpp": """#include <vector>
#include <queue>
#include <unordered_set>
using namespace std;

vector<vector<int>> prim(vector<vector<pair<int,int>>>& graph, int start) {
    unordered_set<int> visited{start};
    vector<vector<int>> mst;
    priority_queue<vector<int>, vector<vector<int>>, greater<>> heap;
    for (auto& [v, w] : graph[start]) heap.push({w, start, v});
    while (!heap.empty()) {
        auto top = heap.top(); heap.pop();
        int w = top[0], u = top[1], v = top[2];
        if (visited.count(v)) continue;
        visited.insert(v);
        mst.push_back({u, v, w});
        for (auto& [nv, nw] : graph[v])
            if (!visited.count(nv)) heap.push({nw, v, nv});
    }
    return mst;
}
""",
        "java": """import java.util.*;

int[][] prim(List<List<int[]>> graph, int start) {
    Set<Integer> visited = new HashSet<>(List.of(start));
    List<int[]> mst = new ArrayList<>();
    PriorityQueue<int[]> heap = new PriorityQueue<>((a, b) -> a[0] - b[0]);
    for (int[] e : graph.get(start)) heap.add(new int[]{e[1], start, e[0]});
    while (!heap.isEmpty()) {
        int[] top = heap.poll();
        int w = top[0], u = top[1], v = top[2];
        if (visited.contains(v)) continue;
        visited.add(v);
        mst.add(new int[]{u, v, w});
        for (int[] e : graph.get(v))
            if (!visited.contains(e[0])) heap.add(new int[]{e[1], v, e[0]});
    }
    return mst.toArray(new int[0][]);
}
""",
    },
    # ---- Dijkstra shortest paths (min-heap) ----
    "dijkstra": {
        "python": """import heapq


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
        "cpp": """#include <vector>
#include <queue>
#include <unordered_map>
#include <climits>
using namespace std;

unordered_map<int,int> dijkstra(vector<vector<pair<int,int>>>& graph, int start) {
    unordered_map<int,int> dist{{start, 0}};
    priority_queue<pair<int,int>, vector<pair<int,int>>, greater<>> heap;
    heap.push({0, start});
    while (!heap.empty()) {
        auto [d, u] = heap.top(); heap.pop();
        if (dist.count(u) && d > dist[u]) continue;
        for (auto& [v, w] : graph[u]) {
            int nd = d + w;
            if (!dist.count(v) || nd < dist[v]) {
                dist[v] = nd;
                heap.push({nd, v});
            }
        }
    }
    return dist;
}
""",
        "java": """import java.util.*;

Map<Integer,Integer> dijkstra(List<List<int[]>> graph, int start) {
    Map<Integer,Integer> dist = new HashMap<>(Map.of(start, 0));
    PriorityQueue<int[]> heap = new PriorityQueue<>((a, b) -> a[0] - b[0]);
    heap.add(new int[]{0, start});
    while (!heap.isEmpty()) {
        int[] top = heap.poll();
        int d = top[0], u = top[1];
        if (d > dist.getOrDefault(u, Integer.MAX_VALUE)) continue;
        for (int[] e : graph.get(u)) {
            int v = e[0], nd = d + e[1];
            if (nd < dist.getOrDefault(v, Integer.MAX_VALUE)) {
                dist.put(v, nd);
                heap.add(new int[]{nd, v});
            }
        }
    }
    return dist;
}
""",
    },
    # ---- merge sort (divide and conquer) ----
    "merge_sort": {
        "python": """def merge_sort(arr):
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
        "cpp": """#include <vector>
using namespace std;

vector<int> merge_sort(vector<int> arr) {
    if (arr.size() <= 1) return arr;
    int mid = arr.size() / 2;
    vector<int> left = merge_sort({arr.begin(), arr.begin() + mid});
    vector<int> right = merge_sort({arr.begin() + mid, arr.end()});
    vector<int> merged;
    int i = 0, j = 0;
    while (i < left.size() && j < right.size())
        merged.push_back(left[i] <= right[j] ? left[i++] : right[j++]);
    while (i < left.size()) merged.push_back(left[i++]);
    while (j < right.size()) merged.push_back(right[j++]);
    return merged;
}
""",
        "java": """import java.util.*;

int[] mergeSort(int[] arr) {
    if (arr.length <= 1) return arr;
    int mid = arr.length / 2;
    int[] left = mergeSort(Arrays.copyOfRange(arr, 0, mid));
    int[] right = mergeSort(Arrays.copyOfRange(arr, mid, arr.length));
    int[] merged = new int[arr.length];
    int i = 0, j = 0, k = 0;
    while (i < left.length && j < right.length)
        merged[k++] = left[i] <= right[j] ? left[i++] : right[j++];
    while (i < left.length) merged[k++] = left[i++];
    while (j < right.length) merged[k++] = right[j++];
    return merged;
}
""",
    },
    # ---- binary search (iterative) ----
    "binary_search": {
        "python": """def binary_search(arr, target):
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
        "cpp": """#include <vector>
using namespace std;

int binary_search(vector<int>& arr, int target) {
    int lo = 0, hi = arr.size() - 1;
    while (lo <= hi) {
        int mid = (lo + hi) / 2;
        if (arr[mid] == target) return mid;
        else if (arr[mid] < target) lo = mid + 1;
        else hi = mid - 1;
    }
    return -1;
}
""",
        "java": """int binarySearch(int[] arr, int target) {
    int lo = 0, hi = arr.length - 1;
    while (lo <= hi) {
        int mid = (lo + hi) / 2;
        if (arr[mid] == target) return mid;
        else if (arr[mid] < target) lo = mid + 1;
        else hi = mid - 1;
    }
    return -1;
}
""",
    },
    # ---- arithmetic evaluation with +,-,* precedence (single stack) ----
    "arithmetic_eval": {
        "python": """def evaluate(tokens):
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
        "cpp": """#include <vector>
#include <string>
#include <numeric>
using namespace std;

int evaluate(vector<string>& tokens) {
    vector<int> stack{stoi(tokens[0])};
    for (size_t i = 1; i < tokens.size(); i += 2) {
        string op = tokens[i];
        int num = stoi(tokens[i + 1]);
        if (op == "*") stack.back() *= num;
        else if (op == "+") stack.push_back(num);
        else stack.push_back(-num);
    }
    return accumulate(stack.begin(), stack.end(), 0);
}
""",
        "java": """import java.util.*;

int evaluate(String[] tokens) {
    Deque<Integer> stack = new ArrayDeque<>();
    stack.push(Integer.parseInt(tokens[0]));
    for (int i = 1; i < tokens.length; i += 2) {
        String op = tokens[i];
        int num = Integer.parseInt(tokens[i + 1]);
        if (op.equals("*")) stack.push(stack.pop() * num);
        else if (op.equals("+")) stack.push(num);
        else stack.push(-num);
    }
    int total = 0;
    while (!stack.isEmpty()) total += stack.pop();
    return total;
}
""",
    },
}

LANGUAGES = ("python", "cpp", "java")

# import / boilerplate lines to drop for DISPLAY (the solution still uses these facilities; we just don't
# show the ceremony). The implementation stays correct — imports are restored for execution/verification.
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
    while kept and not kept[0].strip():       # drop the blank line left where the imports were
        kept.pop(0)
    return "\n".join(kept).strip("\n")


def display_solutions(slug: str) -> dict[str, str] | None:
    """The learner-facing code for an adapter slug: {python, cpp, java} with import/boilerplate lines
    removed. None if this slug has no canonical solution."""
    sols = CANONICAL_SOLUTIONS.get(slug)
    if not sols:
        return None
    return {lang: _strip_imports(sols[lang], lang) for lang in LANGUAGES if lang in sols}


def python_executable(slug: str) -> str | None:
    """The complete (imports intact) Python solution — for build-time verification, never displayed."""
    sols = CANONICAL_SOLUTIONS.get(slug)
    return sols.get("python") if sols else None
