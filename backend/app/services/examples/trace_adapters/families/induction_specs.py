"""T13 induction CONCEPT SPECS — proofs by mathematical induction of polynomial summation identities on the
induction engine. Each is DATA: the term f(i), the closed form g(n), and their display. The base + inductive-step
obligations are machine-checked by the engine gate. Adding one = append an `InductionSpec`."""
from __future__ import annotations

from .induction_engine import InductionSpec

SUM_FIRST_N = InductionSpec(
    slug="induction_sum_first_n",
    title="proof that 1 + 2 + ... + n = n(n+1)/2",
    problem_template="Prove by induction that the sum of the first n positive integers is n(n+1)/2 (check n={N}).",
    f=lambda i: i,
    g=lambda n: n * (n + 1) // 2,
    f_str="i", g_str="n(n+1)/2",
    aliases=["induction sum of first n integers", "prove sum 1 to n", "sum of first n integers by induction",
             "prove n(n+1)/2 by induction", "gauss sum induction"],
    not_aliases=["squares", "cubes", "odd"],
    priority=105,
)

SUM_FIRST_N_SQUARES = InductionSpec(
    slug="induction_sum_of_squares",
    title="proof that 1^2 + 2^2 + ... + n^2 = n(n+1)(2n+1)/6",
    problem_template="Prove by induction that the sum of the first n squares is n(n+1)(2n+1)/6 (check n={N}).",
    f=lambda i: i * i,
    g=lambda n: n * (n + 1) * (2 * n + 1) // 6,
    f_str="i^2", g_str="n(n+1)(2n+1)/6",
    aliases=["induction sum of squares", "prove sum of first n squares", "sum of squares by induction",
             "prove n(n+1)(2n+1)/6 by induction"],
    priority=105,
)

SUM_FIRST_N_CUBES = InductionSpec(
    slug="induction_sum_of_cubes",
    title="proof that 1^3 + 2^3 + ... + n^3 = (n(n+1)/2)^2",
    problem_template="Prove by induction that the sum of the first n cubes is (n(n+1)/2)^2 (check n={N}).",
    f=lambda i: i ** 3,
    g=lambda n: (n * (n + 1) // 2) ** 2,
    f_str="i^3", g_str="(n(n+1)/2)^2",
    aliases=["induction sum of cubes", "prove sum of first n cubes", "sum of cubes by induction"],
    priority=105,
)

SUM_ODD_NUMBERS = InductionSpec(
    slug="induction_sum_of_odds",
    title="proof that 1 + 3 + 5 + ... + (2n-1) = n^2",
    problem_template="Prove by induction that the sum of the first n odd numbers is n^2 (check n={N}).",
    f=lambda i: 2 * i - 1,
    g=lambda n: n * n,
    f_str="(2i-1)", g_str="n^2",
    aliases=["induction sum of odd numbers", "prove sum of first n odd numbers is n squared",
             "sum of odds by induction", "prove 1+3+5 = n^2"],
    not_aliases=["squares", "cubes"],
    priority=105,
)


ALL_SPECS = [SUM_FIRST_N, SUM_FIRST_N_SQUARES, SUM_FIRST_N_CUBES, SUM_ODD_NUMBERS]
