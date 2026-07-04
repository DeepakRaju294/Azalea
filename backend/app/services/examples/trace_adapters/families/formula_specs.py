"""T6 formula CONCEPT SPECS (CP12b data rows) — one `FormulaSpec` per concept, spanning the non-CS domains the
formula engine unlocks (finance, physics, EE, chemistry). Each is DATA: givens (+units+ranges), the governing
equation(s), coverage cases. The engine (`formula_engine.py`) turns each into a verified-trace adapter; the gate
(`test_formula_engine.py`) re-evaluates every output independently, so a wrong formula/unit fails, not ships.

Adding a concept = add a `FormulaSpec` here. Wiring it live = add its `formula_decl(...)` to `t6_formula.py`
DECLARATIONS + a manifest/routing entry (mechanical, gated by `manifest_gaps()`)."""
from __future__ import annotations

from .formula_engine import Case, FormulaSpec, Given, Output

# --- physics / mechanics (B9) --------------------------------------------------------------------------
KINEMATICS = FormulaSpec(
    slug="kinematics_const_accel", title="kinematics with constant acceleration",
    problem_template=("An object moving at u = {u} m/s accelerates uniformly at a = {a} m/s^2 for t = {t} s. "
                      "Find its final velocity and displacement."),
    givens=[Given("u", "m/s", 0, 10), Given("a", "m/s^2", 1, 6), Given("t", "s", 1, 6)],
    outputs=[Output("v", "v = u + a*t", "u + a*t", "m/s", "compute_final_velocity", "final velocity"),
             Output("s", "s = u*t + (a*t^2)/2", "u*t + (a*t**2)/2", "m", "compute_displacement", "displacement")],
    conventions={"model": "constant (uniform) acceleration", "units": "SI (m, s, m/s, m/s^2)"},
    cases=[Case("zero_initial_velocity", lambda g: g["u"] == 0),
           Case("nonzero_initial_velocity", lambda g: g["u"] != 0)],
    must_avoid=["zero_time"])

KINETIC_ENERGY = FormulaSpec(
    slug="kinetic_energy", title="kinetic energy of a moving body",
    problem_template="A body of mass m = {m} kg moves at v = {v} m/s. Find its kinetic energy.",
    givens=[Given("m", "kg", 1, 20), Given("v", "m/s", 1, 15)],
    outputs=[Output("KE", "KE = (m*v^2)/2", "(m*v**2)/2", "J", "compute_kinetic_energy", "kinetic energy")],
    conventions={"units": "SI (kg, m/s, J)"})

# --- electrical engineering (B9 circuits) --------------------------------------------------------------
OHMS_LAW = FormulaSpec(
    slug="ohms_law", title="Ohm's law with power",
    problem_template="A resistor R = {R} ohm has V = {V} V across it. Find the current and the power dissipated.",
    givens=[Given("V", "V", 2, 24), Given("R", "ohm", 1, 12)],
    outputs=[Output("I", "I = V/R", "V/R", "A", "compute_current", "current"),
             Output("P", "P = V*I", "V*(V/R)", "W", "compute_power", "power dissipated")],
    conventions={"law": "Ohm's law V = I*R", "units": "SI (V, A, ohm, W)"})

# --- finance (B11) -------------------------------------------------------------------------------------
SIMPLE_INTEREST = FormulaSpec(
    slug="simple_interest", title="simple interest",
    problem_template="A principal P = ${P} earns simple interest at r = {r}% per year for t = {t} years. "
                     "Find the interest and the final amount.",
    givens=[Given("P", "$", 100, 5000), Given("r", "%", 1, 12), Given("t", "yr", 1, 10)],
    outputs=[Output("I", "I = P*r*t/100", "P*r*t/100", "$", "compute_interest", "interest earned"),
             Output("A", "A = P + I", "P + P*r*t/100", "$", "compute_amount", "final amount")],
    conventions={"model": "simple interest (not compounded)", "units": "dollars, percent per year"})

COMPOUND_INTEREST = FormulaSpec(
    slug="compound_interest", title="compound interest (annual)",
    problem_template="A principal P = ${P} is invested at r = {r}% compounded annually for t = {t} years. "
                     "Find the final amount.",
    givens=[Given("P", "$", 100, 5000), Given("r", "%", 1, 12), Given("t", "yr", 1, 8)],
    outputs=[Output("A", "A = P*(1 + r/100)^t", "P*(1 + r/100)**t", "$", "compute_amount", "final amount")],
    conventions={"model": "annual compounding", "units": "dollars, percent per year"})

# --- chemistry (B10) -----------------------------------------------------------------------------------
MOLARITY = FormulaSpec(
    slug="molarity", title="molarity of a solution",
    problem_template="A solution contains n = {n} mol of solute in V = {V} L. Find its molarity.",
    givens=[Given("n", "mol", 1, 10), Given("V", "L", 1, 8)],
    outputs=[Output("M", "M = n/V", "n/V", "mol/L", "compute_molarity", "molarity")],
    conventions={"definition": "molarity = moles of solute per litre of solution"})

DENSITY = FormulaSpec(
    slug="density", title="density from mass and volume",
    problem_template="A sample has mass m = {m} g and volume V = {V} mL. Find its density.",
    givens=[Given("m", "g", 5, 500), Given("V", "mL", 1, 50)],
    outputs=[Output("rho", "rho = m/V", "m/V", "g/mL", "compute_density", "density")],
    conventions={"definition": "density = mass per unit volume"})

ALL_SPECS = [KINEMATICS, KINETIC_ENERGY, OHMS_LAW, SIMPLE_INTEREST, COMPOUND_INTEREST, MOLARITY, DENSITY]
