"""T6 formula CONCEPT SPECS (CP12b data rows) — one `FormulaSpec` per concept, across the non-CS domains the
formula engine unlocks. Each is DATA: givens (+units+ranges) or a dataset, the governing equation(s), plus its
own registration metadata (family + routing aliases + priority). Adding a concept = add a `FormulaSpec` here and
list it in `ALL_SPECS`; the manifest entry, routing rule, declaration, and narration flag are all DERIVED from
it (see manifest.py / t6_formula.py). The gate (`test_formula_engine`) re-evaluates every output independently,
so a wrong formula/unit fails rather than ships."""
from __future__ import annotations

from .formula_engine import Case, Dataset, FormulaSpec, Given, Output

# ======================================================================================================
# PHYSICS / MECHANICS (B9) — family "physics"
# ======================================================================================================
KINEMATICS = FormulaSpec(  # register=False: the hand-coded `kinematics` owns this routing; this is the engine's
                           # migration-proof spec, exercised only by the gate.
    slug="kinematics_const_accel", title="kinematics with constant acceleration", register=False,
    problem_template=("An object moving at u = {u} m/s accelerates uniformly at a = {a} m/s^2 for t = {t} s. "
                      "Find its final velocity and displacement."),
    givens=[Given("u", "m/s", 0, 10), Given("a", "m/s^2", 1, 6), Given("t", "s", 1, 6)],
    outputs=[Output("v", "v = u + a*t", "u + a*t", "m/s", "compute_final_velocity", "final velocity"),
             Output("s", "s = u*t + (a*t^2)/2", "u*t + (a*t**2)/2", "m", "compute_displacement", "displacement")],
    conventions={"model": "constant (uniform) acceleration", "units": "SI (m, s, m/s, m/s^2)"},
    cases=[Case("zero_initial_velocity", lambda g: g["u"] == 0),
           Case("nonzero_initial_velocity", lambda g: g["u"] != 0)], must_avoid=["zero_time"])

KINETIC_ENERGY = FormulaSpec(
    slug="kinetic_energy", title="kinetic energy of a moving body", family="physics",
    aliases=["kinetic energy"], priority=96,
    problem_template="A body of mass m = {m} kg moves at v = {v} m/s. Find its kinetic energy.",
    givens=[Given("m", "kg", 1, 20), Given("v", "m/s", 1, 15)],
    outputs=[Output("KE", "KE = (m*v^2)/2", "(m*v**2)/2", "J", "compute_kinetic_energy", "kinetic energy")],
    conventions={"units": "SI (kg, m/s, J)"})

NEWTONS_SECOND_LAW = FormulaSpec(
    slug="newtons_second_law", title="Newton's second law", family="physics",
    aliases=["newton's second law", "newtons second law", "net force", "f = ma"], priority=78,
    problem_template="A mass m = {m} kg accelerates at a = {a} m/s^2. Find the net force on it.",
    givens=[Given("m", "kg", 1, 20), Given("a", "m/s^2", 1, 15)],
    outputs=[Output("F", "F = m*a", "m*a", "N", "compute_force", "net force")],
    conventions={"law": "F = m*a", "units": "SI (kg, m/s^2, N)"})

WEIGHT_FORCE = FormulaSpec(
    slug="weight_force", title="weight from mass", family="physics",
    aliases=["weight of an object", "weight force", "w = mg"], priority=77, constants={"g": 9.8},
    problem_template="An object has mass m = {m} kg. Find its weight (g = 9.8 m/s^2).",
    givens=[Given("m", "kg", 1, 50)],
    outputs=[Output("W", "W = m*g", "m*g", "N", "compute_weight", "weight")],
    conventions={"g": "9.8 m/s^2", "units": "SI (kg, N)"})

MOMENTUM = FormulaSpec(
    slug="momentum", title="linear momentum", family="physics",
    aliases=["momentum"], priority=76,
    problem_template="A body of mass m = {m} kg moves at v = {v} m/s. Find its momentum.",
    givens=[Given("m", "kg", 1, 20), Given("v", "m/s", 1, 25)],
    outputs=[Output("p", "p = m*v", "m*v", "kg*m/s", "compute_momentum", "momentum")],
    conventions={"units": "SI (kg, m/s, kg*m/s)"})

WORK_DONE = FormulaSpec(
    slug="work_done", title="work done by a constant force", family="physics",
    aliases=["work done", "work by a force"], priority=75,
    problem_template="A constant force F = {F} N acts over a distance d = {d} m in its direction. Find the work done.",
    givens=[Given("F", "N", 1, 50), Given("d", "m", 1, 20)],
    # label "work" (not "work done"): the last-card result would otherwise contain the word "done", which the
    # completion detector reads as already-complete and skips appending the verified "Complete: …" clause.
    outputs=[Output("W", "W = F*d", "F*d", "J", "compute_work", "work")],
    conventions={"units": "SI (N, m, J)", "note": "force is along the displacement"})

GRAVITATIONAL_PE = FormulaSpec(
    slug="gravitational_pe", title="gravitational potential energy", family="physics",
    aliases=["potential energy", "gravitational potential"], priority=74, constants={"g": 9.8},
    problem_template="A mass m = {m} kg is raised to height h = {h} m. Find its gravitational potential energy "
                     "(g = 9.8 m/s^2).",
    givens=[Given("m", "kg", 1, 20), Given("h", "m", 1, 30)],
    outputs=[Output("PE", "PE = m*g*h", "m*g*h", "J", "compute_potential_energy", "potential energy")],
    conventions={"g": "9.8 m/s^2", "units": "SI (kg, m, J)"})

# ======================================================================================================
# ELECTRICAL ENGINEERING (B9 circuits) — family "physics"
# ======================================================================================================
OHMS_LAW = FormulaSpec(
    slug="ohms_law", title="Ohm's law with power", family="physics",
    aliases=["ohm's law", "ohms law", "ohm law"], priority=95,
    problem_template="A resistor R = {R} ohm has V = {V} V across it. Find the current and the power dissipated.",
    givens=[Given("V", "V", 2, 24), Given("R", "ohm", 1, 12)],
    outputs=[Output("I", "I = V/R", "V/R", "A", "compute_current", "current"),
             Output("P", "P = V*I", "V*(V/R)", "W", "compute_power", "power dissipated")],
    conventions={"law": "Ohm's law V = I*R", "units": "SI (V, A, ohm, W)"})

# ======================================================================================================
# FINANCE (B11) — family "finance"
# ======================================================================================================
SIMPLE_INTEREST = FormulaSpec(
    slug="simple_interest", title="simple interest", family="finance",
    aliases=["simple interest"], not_aliases=["compound"], priority=93,
    problem_template="A principal P = ${P} earns simple interest at r = {r}% per year for t = {t} years. "
                     "Find the interest and the final amount.",
    givens=[Given("P", "$", 100, 5000), Given("r", "%", 1, 12), Given("t", "yr", 1, 10)],
    outputs=[Output("I", "I = P*r*t/100", "P*r*t/100", "$", "compute_interest", "interest earned"),
             Output("A", "A = P + I", "P + P*r*t/100", "$", "compute_amount", "final amount")],
    conventions={"model": "simple interest (not compounded)", "units": "dollars, percent per year"})

COMPOUND_INTEREST = FormulaSpec(
    slug="compound_interest", title="compound interest (annual)", family="finance",
    aliases=["compound interest"], priority=94,
    problem_template="A principal P = ${P} is invested at r = {r}% compounded annually for t = {t} years. "
                     "Find the final amount.",
    givens=[Given("P", "$", 100, 5000), Given("r", "%", 1, 12), Given("t", "yr", 1, 8)],
    outputs=[Output("A", "A = P*(1 + r/100)^t", "P*(1 + r/100)**t", "$", "compute_amount", "final amount")],
    conventions={"model": "annual compounding", "units": "dollars, percent per year"})

PRESENT_VALUE = FormulaSpec(
    slug="present_value", title="present value (discounting)", family="finance",
    aliases=["present value", "discounted value"], priority=72,
    problem_template="A future amount FV = ${FV} is due in t = {t} years at a discount rate r = {r}%. "
                     "Find its present value.",
    givens=[Given("FV", "$", 100, 5000), Given("r", "%", 1, 12), Given("t", "yr", 1, 8)],
    outputs=[Output("PV", "PV = FV/(1 + r/100)^t", "FV/(1 + r/100)**t", "$", "compute_present_value",
                    "present value")],
    conventions={"model": "annual discounting", "units": "dollars, percent per year"})

PERCENT_CHANGE = FormulaSpec(
    slug="percent_change", title="percent change", family="finance",
    aliases=["percent change", "percentage change"], priority=71,
    problem_template="A quantity changes from old = {old} to new = {new}. Find the percent change.",
    givens=[Given("old", "", 10, 200), Given("new", "", 10, 200)],
    outputs=[Output("pct", "pct = (new - old)/old * 100", "(new - old)/old * 100", "%", "compute_percent_change",
                    "percent change")],
    conventions={"definition": "percent change = (new - old) / old * 100"})

# ======================================================================================================
# GEOMETRY (B2) — family "geometry"
# ======================================================================================================
CIRCLE_AREA = FormulaSpec(
    slug="circle_area", title="area of a circle", family="geometry",
    aliases=["area of a circle", "circle area"], priority=69,
    problem_template="A circle has radius r = {r}. Find its area.",
    givens=[Given("r", "", 1, 20)],
    outputs=[Output("A", "A = pi*r^2", "pi*r**2", "sq units", "compute_area", "area")],
    conventions={"units": "square units", "pi": "3.14159..."})

CIRCLE_CIRCUMFERENCE = FormulaSpec(
    slug="circle_circumference", title="circumference of a circle", family="geometry",
    aliases=["circumference"], priority=68,
    problem_template="A circle has radius r = {r}. Find its circumference.",
    givens=[Given("r", "", 1, 20)],
    outputs=[Output("C", "C = 2*pi*r", "2*pi*r", "units", "compute_circumference", "circumference")],
    conventions={"pi": "3.14159..."})

RECTANGLE_AREA = FormulaSpec(
    slug="rectangle_area", title="area of a rectangle", family="geometry",
    aliases=["area of a rectangle", "rectangle area"], priority=67,
    problem_template="A rectangle is l = {l} by w = {w}. Find its area.",
    givens=[Given("l", "", 1, 30), Given("w", "", 1, 30)],
    outputs=[Output("A", "A = l*w", "l*w", "sq units", "compute_area", "area")],
    conventions={"units": "square units"})

TRIANGLE_AREA = FormulaSpec(
    slug="triangle_area", title="area of a triangle", family="geometry",
    aliases=["area of a triangle", "triangle area"], priority=66,
    problem_template="A triangle has base b = {b} and height h = {h}. Find its area.",
    givens=[Given("b", "", 1, 30), Given("h", "", 1, 30)],
    outputs=[Output("A", "A = (b*h)/2", "(b*h)/2", "sq units", "compute_area", "area")],
    conventions={"units": "square units"})

PYTHAGOREAN = FormulaSpec(
    slug="pythagorean", title="Pythagorean theorem", family="geometry",
    aliases=["pythagorean", "hypotenuse"], priority=65,
    problem_template="A right triangle has legs a = {a} and b = {b}. Find the hypotenuse.",
    givens=[Given("a", "", 1, 20), Given("b", "", 1, 20)],
    outputs=[Output("c", "c = sqrt(a^2 + b^2)", "sqrt(a**2 + b**2)", "", "compute_hypotenuse", "hypotenuse")],
    conventions={"theorem": "a^2 + b^2 = c^2"})

SPHERE_VOLUME = FormulaSpec(
    slug="sphere_volume", title="volume of a sphere", family="geometry",
    aliases=["volume of a sphere", "sphere volume"], priority=64,
    problem_template="A sphere has radius r = {r}. Find its volume.",
    givens=[Given("r", "", 1, 12)],
    outputs=[Output("V", "V = (4/3)*pi*r^3", "(4/3)*pi*r**3", "cubic units", "compute_volume", "volume")],
    conventions={"pi": "3.14159..."})

CYLINDER_VOLUME = FormulaSpec(
    slug="cylinder_volume", title="volume of a cylinder", family="geometry",
    aliases=["volume of a cylinder", "cylinder volume"], priority=63,
    problem_template="A cylinder has radius r = {r} and height h = {h}. Find its volume.",
    givens=[Given("r", "", 1, 12), Given("h", "", 1, 20)],
    outputs=[Output("V", "V = pi*r^2*h", "pi*r**2*h", "cubic units", "compute_volume", "volume")],
    conventions={"pi": "3.14159..."})

# ======================================================================================================
# CHEMISTRY (B10) — family "chemistry"
# ======================================================================================================
MOLARITY = FormulaSpec(
    slug="molarity", title="molarity of a solution", family="chemistry",
    aliases=["molarity", "molar concentration"], priority=92,
    problem_template="A solution contains n = {n} mol of solute in V = {V} L. Find its molarity.",
    givens=[Given("n", "mol", 1, 10), Given("V", "L", 1, 8)],
    outputs=[Output("M", "M = n/V", "n/V", "mol/L", "compute_molarity", "molarity")],
    conventions={"definition": "molarity = moles of solute per litre of solution"})

DENSITY = FormulaSpec(
    slug="density", title="density from mass and volume", family="chemistry",
    aliases=["density"], priority=91,
    problem_template="A sample has mass m = {m} g and volume V = {V} mL. Find its density.",
    givens=[Given("m", "g", 5, 500), Given("V", "mL", 1, 50)],
    outputs=[Output("rho", "rho = m/V", "m/V", "g/mL", "compute_density", "density")],
    conventions={"definition": "density = mass per unit volume"})

IDEAL_GAS_PRESSURE = FormulaSpec(
    slug="ideal_gas_pressure", title="ideal gas law (solve for pressure)", family="chemistry",
    aliases=["ideal gas", "gas law"], priority=62, constants={"R": 0.0821},
    problem_template="n = {n} mol of an ideal gas occupies V = {V} L at T = {T} K. Find the pressure "
                     "(R = 0.0821 L*atm/mol/K).",
    givens=[Given("n", "mol", 1, 10), Given("T", "K", 200, 500), Given("V", "L", 1, 20)],
    outputs=[Output("P", "P = n*R*T/V", "n*R*T/V", "atm", "compute_pressure", "pressure")],
    conventions={"law": "PV = nRT", "R": "0.0821 L*atm/mol/K"})

DILUTION = FormulaSpec(
    slug="dilution", title="dilution (M1V1 = M2V2)", family="chemistry",
    aliases=["dilution", "dilute"], priority=61,
    problem_template="A stock solution M1 = {M1} mol/L, V1 = {V1} mL is diluted to V2 = {V2} mL. "
                     "Find the new concentration.",
    givens=[Given("M1", "mol/L", 1, 10), Given("V1", "mL", 1, 10), Given("V2", "mL", 20, 100)],
    outputs=[Output("M2", "M2 = M1*V1/V2", "M1*V1/V2", "mol/L", "compute_concentration", "diluted concentration")],
    conventions={"law": "M1*V1 = M2*V2"})

PERCENT_YIELD = FormulaSpec(
    slug="percent_yield", title="percent yield", family="chemistry",
    aliases=["percent yield", "percentage yield"], priority=60,
    problem_template="A reaction gives actual = {actual} g of product; the theoretical yield is "
                     "theoretical = {theoretical} g. Find the percent yield.",
    givens=[Given("actual", "g", 5, 80), Given("theoretical", "g", 85, 120)],
    outputs=[Output("yield_pct", "yield = actual/theoretical * 100", "actual/theoretical * 100", "%",
                    "compute_percent_yield", "percent yield")],
    conventions={"definition": "percent yield = actual / theoretical * 100"})

# ======================================================================================================
# STATISTICS (B7) — family "statistics" (list-input via Dataset, except z-score which is scalar)
# ======================================================================================================
DESCRIPTIVE_STATS = FormulaSpec(
    slug="descriptive_stats", title="mean, variance and standard deviation of a dataset", family="statistics",
    aliases=["mean, variance", "mean and variance", "standard deviation", "variance and"], priority=89,
    problem_template="For the dataset {xs}, find the mean, the (population) variance, and the standard deviation.",
    givens=[], dataset=Dataset("xs", size_lo=5, size_hi=8, val_lo=1, val_hi=20),
    outputs=[
        Output("mean", "mean = (sum of the values) / n", "sum(xs)/n", "", "compute_mean", "mean",
               show=[("sum of the values", "sum(xs)"), ("n", "n")]),
        Output("variance", "variance = (sum of squared deviations from the mean) / n",
               "sum((x-mean)**2 for x in xs)/n", "", "compute_variance", "population variance",
               show=[("sum of squared deviations from the mean", "sum((x-mean)**2 for x in xs)"), ("n", "n")]),
        Output("sd", "sd = sqrt(variance)", "sqrt(variance)", "", "compute_std_dev", "standard deviation",
               show=[("variance", "variance")])],
    conventions={"model": "population (divide by n, not n-1)"})

MEDIAN_RANGE = FormulaSpec(
    slug="median_range", title="median and range of a dataset", family="statistics",
    aliases=["median"], priority=88,
    problem_template="For the dataset {xs}, find the median and the range.",
    givens=[], dataset=Dataset("xs", size_lo=5, size_hi=9, val_lo=1, val_hi=30),
    outputs=[
        Output("median", "median = middle value of the sorted data", "median(xs)", "", "compute_median", "median",
               show=[("middle value of the sorted data", "median(xs)")]),
        Output("range", "range = max - min", "max(xs) - min(xs)", "", "compute_range", "range",
               show=[("max", "max(xs)"), ("min", "min(xs)")])],
    conventions={"definition": "median = middle of the sorted values; range = max minus min"})

Z_SCORE = FormulaSpec(
    slug="z_score", title="z-score (standard score)", family="statistics",
    aliases=["z-score", "z score", "standard score"], priority=87,
    problem_template="A value x = {x} comes from a distribution with mean = {mean} and standard deviation "
                     "sd = {sd}. Find its z-score.",
    givens=[Given("x", "", 1, 100), Given("mean", "", 1, 100), Given("sd", "", 1, 20)],
    outputs=[Output("z", "z = (x - mean)/sd", "(x - mean)/sd", "", "compute_z_score", "z-score")],
    conventions={"definition": "z = (x - mean) / standard deviation"})

# --- the full concept set; ALL_SPECS drives the gate, the registry, the manifest, and routing ---------
ALL_SPECS = [
    # physics / EE
    KINEMATICS, KINETIC_ENERGY, NEWTONS_SECOND_LAW, WEIGHT_FORCE, MOMENTUM, WORK_DONE, GRAVITATIONAL_PE, OHMS_LAW,
    # finance
    SIMPLE_INTEREST, COMPOUND_INTEREST, PRESENT_VALUE, PERCENT_CHANGE,
    # geometry
    CIRCLE_AREA, CIRCLE_CIRCUMFERENCE, RECTANGLE_AREA, TRIANGLE_AREA, PYTHAGOREAN, SPHERE_VOLUME, CYLINDER_VOLUME,
    # chemistry
    MOLARITY, DENSITY, IDEAL_GAS_PRESSURE, DILUTION, PERCENT_YIELD,
    # statistics
    DESCRIPTIVE_STATS, MEDIAN_RANGE, Z_SCORE,
]
