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
    aliases=["weight of an object", "weight force", "weight from mass", "w = mg"], priority=77, constants={"g": 9.8},
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
    aliases=["gravitational potential energy", "gravitational potential"], priority=74, constants={"g": 9.8},
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
    aliases=["ideal gas", "gas law"], not_aliases=["combined"], priority=62, constants={"R": 0.0821},
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
    conventions={"model": "population (divide by n, not n-1)"},
    canonical_latex="\\sigma = \\sqrt{\\frac{\\sum (x_i - \\mu)^2}{n}}",
    canonical_notes=[
        "The mean is \\(\\mu = \\frac{\\sum x_i}{n}\\) — the sum of the values divided by how many there are.",
        "The variance is \\(\\sigma^2 = \\frac{\\sum (x_i - \\mu)^2}{n}\\), the mean squared deviation from \\(\\mu\\).",
        "The standard deviation \\(\\sigma\\) is the square root of the variance, back in the data's own units.",
        "This is the POPULATION form (divide by \\(n\\)); the sample form divides by \\(n-1\\).",
    ],
    edge_cases=[
        "Variance and standard deviation are never negative; \\(\\sigma = 0\\) exactly when every value equals "
        "the mean (no spread).",
        "The standard deviation is in the same units as the data; the variance is in those units squared.",
    ])

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

WEIGHTED_MEAN = FormulaSpec(
    slug="weighted_mean", title="weighted mean of values and weights", family="statistics",
    aliases=["weighted mean", "weighted average"], priority=86,
    problem_template="For values xs = {xs} with weights ws = {ws}, find the weighted mean.",
    givens=[], dataset=Dataset("xs", size_lo=3, size_hi=5, val_lo=1, val_hi=20),
    dataset2=Dataset("ws", size_lo=3, size_hi=5, val_lo=1, val_hi=5),
    outputs=[Output("wmean", "wmean = (sum of value x weight)/(sum of weights)",
                    "sum(v*w for v, w in zip(xs, ws))/sum(ws)", "", "compute_weighted_mean", "weighted mean",
                    show=[("sum of value x weight", "sum(v*w for v, w in zip(xs, ws))"),
                          ("sum of weights", "sum(ws)")])],
    conventions={"definition": "weighted mean = sum(value x weight) / sum(weights)"},
    canonical_latex="\\mu_w = \\frac{\\sum w_i x_i}{\\sum w_i}",
    canonical_notes=[
        "\\(x_i\\): each value.  \\(w_i\\): its weight (how much that value counts).",
        "Each value is scaled by its weight, then divided by the total weight — heavier weights pull the mean "
        "toward their values.",
    ],
    edge_cases=[
        "Requires \\(\\sum w_i > 0\\); if every weight is 0 the weighted mean is undefined.",
        "With equal weights, the weighted mean reduces to the ordinary (unweighted) mean.",
    ])

COVARIANCE = FormulaSpec(
    slug="covariance", title="covariance of two datasets", family="statistics",
    aliases=["covariance"], priority=85,
    problem_template="For paired data xs = {xs} and ys = {ys}, find the (population) covariance.",
    givens=[], dataset=Dataset("xs", size_lo=4, size_hi=6, val_lo=1, val_hi=15),
    dataset2=Dataset("ys", size_lo=4, size_hi=6, val_lo=1, val_hi=15),
    outputs=[
        Output("mean_x", "mean_x = (sum of xs)/n", "sum(xs)/n", "", "compute_mean_x", "mean of xs",
               show=[("sum of xs", "sum(xs)"), ("n", "n")]),
        Output("mean_y", "mean_y = (sum of ys)/n", "sum(ys)/n", "", "compute_mean_y", "mean of ys",
               show=[("sum of ys", "sum(ys)"), ("n", "n")]),
        Output("cov", "cov = (sum of (x - mean_x)(y - mean_y))/n",
               "sum((x-mean_x)*(y-mean_y) for x, y in zip(xs, ys))/n", "", "compute_covariance", "covariance",
               show=[("sum of (x - mean_x)(y - mean_y)", "sum((x-mean_x)*(y-mean_y) for x, y in zip(xs, ys))"),
                     ("n", "n")])],
    conventions={"model": "population covariance (divide by n)"})

Z_SCORE = FormulaSpec(
    slug="z_score", title="z-score (standard score)", family="statistics",
    aliases=["z-score", "z score", "standard score"], priority=87,
    problem_template="A value x = {x} comes from a distribution with mean = {mean} and standard deviation "
                     "sd = {sd}. Find its z-score.",
    givens=[Given("x", "", 1, 100), Given("mean", "", 1, 100), Given("sd", "", 1, 20)],
    outputs=[Output("z", "z = (x - mean)/sd", "(x - mean)/sd", "", "compute_z_score", "z-score")],
    conventions={"definition": "z = (x - mean) / standard deviation"},
    canonical_latex="z = \\frac{x - \\mu}{\\sigma}",
    canonical_notes=[
        "\\(x\\): the value.  \\(\\mu\\): the distribution's mean.  \\(\\sigma\\): its standard deviation.",
        "A z-score is how many standard deviations \\(x\\) lies above (\\(z>0\\)) or below (\\(z<0\\)) the mean.",
    ],
    edge_cases=[
        "The z-score is undefined when \\(\\sigma = 0\\) (no spread — every value equals the mean).",
        "\\(z = 0\\) exactly when \\(x = \\mu\\); the sign of \\(z\\) shows which side of the mean \\(x\\) falls on.",
    ])

# ======================================================================================================
# PHYSICS — second wave — family "physics"
# ======================================================================================================
PROJECTILE_RANGE = FormulaSpec(
    slug="projectile_range", title="projectile range", family="physics",
    aliases=["projectile range", "range of a projectile"], priority=59, constants={"g": 9.8},
    problem_template="A projectile is launched at v = {v} m/s at angle theta = {theta} degrees. Find its range "
                     "on level ground (g = 9.8 m/s^2).",
    givens=[Given("v", "m/s", 5, 40), Given("theta", "deg", 15, 75)],
    outputs=[Output("R", "R = v^2 * sin(2*theta) / g", "v**2 * sin(radians(2*theta)) / g", "m",
                    "compute_range", "range")],
    conventions={"model": "level-ground projectile", "g": "9.8 m/s^2"})

CENTRIPETAL_ACCEL = FormulaSpec(
    slug="centripetal_acceleration", title="centripetal acceleration", family="physics",
    aliases=["centripetal acceleration", "centripetal"], priority=58,
    problem_template="An object moves at v = {v} m/s in a circle of radius r = {r} m. Find its centripetal "
                     "acceleration.",
    givens=[Given("v", "m/s", 1, 30), Given("r", "m", 1, 20)],
    outputs=[Output("a", "a = v^2/r", "v**2/r", "m/s^2", "compute_acceleration", "centripetal acceleration")],
    conventions={"units": "SI"})

WAVE_SPEED = FormulaSpec(
    slug="wave_speed", title="wave speed", family="physics",
    aliases=["wave speed", "wave velocity"], priority=57,
    problem_template="A wave has frequency f = {f} Hz and wavelength lambda = {lam} m. Find its speed.",
    givens=[Given("f", "Hz", 1, 50), Given("lam", "m", 1, 20)],
    outputs=[Output("v", "v = f*lambda", "f*lam", "m/s", "compute_wave_speed", "wave speed")],
    conventions={"relation": "v = f * lambda"})

PRESSURE = FormulaSpec(
    slug="pressure", title="pressure from force and area", family="physics",
    aliases=["pressure from force", "pressure force area"], priority=56,
    problem_template="A force F = {F} N is applied over an area A = {A} m^2. Find the pressure.",
    givens=[Given("F", "N", 1, 100), Given("A", "m^2", 1, 20)],
    outputs=[Output("P", "P = F/A", "F/A", "Pa", "compute_pressure", "pressure")],
    conventions={"units": "SI (N, m^2, Pa)"})

MECHANICAL_POWER = FormulaSpec(
    slug="mechanical_power", title="mechanical power", family="physics",
    aliases=["mechanical power", "power from work", "average power"], priority=55,
    problem_template="Work W = {W} J is done in time t = {t} s. Find the average power.",
    givens=[Given("W", "J", 1, 500), Given("t", "s", 1, 20)],
    outputs=[Output("P", "P = W/t", "W/t", "W", "compute_power", "power")],
    conventions={"units": "SI (J, s, W)"})

SPRING_PE = FormulaSpec(
    slug="spring_pe", title="elastic potential energy of a spring", family="physics",
    aliases=["elastic potential energy", "spring potential energy"], priority=54,
    problem_template="A spring of stiffness k = {k} N/m is stretched by x = {x} m. Find its elastic potential "
                     "energy.",
    givens=[Given("k", "N/m", 1, 50), Given("x", "m", 1, 10)],
    outputs=[Output("PE", "PE = (k*x^2)/2", "(k*x**2)/2", "J", "compute_elastic_energy", "elastic potential energy")],
    conventions={"law": "Hooke's law spring energy"})

# ======================================================================================================
# GEOMETRY — second wave — family "geometry"
# ======================================================================================================
COORDINATE_DISTANCE = FormulaSpec(
    slug="coordinate_distance", title="distance between two points", family="geometry",
    aliases=["distance between two points", "coordinate distance", "distance formula"], priority=53,
    problem_template="Find the distance between the points ({x1}, {y1}) and ({x2}, {y2}).",
    givens=[Given("x1", "", 0, 10), Given("y1", "", 0, 10), Given("x2", "", 0, 10), Given("y2", "", 0, 10)],
    outputs=[Output("d", "d = sqrt((x2-x1)^2 + (y2-y1)^2)", "sqrt((x2-x1)**2 + (y2-y1)**2)", "units",
                    "compute_distance", "distance")],
    conventions={"formula": "distance formula"})

MIDPOINT = FormulaSpec(
    slug="midpoint", title="midpoint of a segment", family="geometry",
    aliases=["midpoint"], priority=52,
    problem_template="Find the midpoint of the segment from ({x1}, {y1}) to ({x2}, {y2}).",
    givens=[Given("x1", "", 0, 20), Given("y1", "", 0, 20), Given("x2", "", 0, 20), Given("y2", "", 0, 20)],
    outputs=[Output("mx", "mx = (x1 + x2)/2", "(x1 + x2)/2", "", "compute_midpoint_x", "midpoint x"),
             Output("my", "my = (y1 + y2)/2", "(y1 + y2)/2", "", "compute_midpoint_y", "midpoint y")],
    conventions={"formula": "midpoint = average of the endpoints"})

SLOPE = FormulaSpec(
    slug="slope", title="slope of a line through two points", family="geometry",
    aliases=["slope of a line", "slope between"], priority=51,
    problem_template="Find the slope of the line through ({x1}, {y1}) and ({x2}, {y2}).",
    givens=[Given("x1", "", 0, 5), Given("y1", "", 0, 20), Given("x2", "", 6, 15), Given("y2", "", 0, 20)],
    outputs=[Output("m", "m = (y2 - y1)/(x2 - x1)", "(y2 - y1)/(x2 - x1)", "", "compute_slope", "slope")],
    conventions={"formula": "rise over run"})

TRAPEZOID_AREA = FormulaSpec(
    slug="trapezoid_area", title="area of a trapezoid", family="geometry",
    aliases=["area of a trapezoid", "trapezoid area"], priority=50,
    problem_template="A trapezoid has parallel sides a = {a} and b = {b} and height h = {h}. Find its area.",
    givens=[Given("a", "", 1, 20), Given("b", "", 1, 20), Given("h", "", 1, 20)],
    outputs=[Output("A", "A = (a + b)/2 * h", "(a + b)/2 * h", "sq units", "compute_area", "area")],
    conventions={"units": "square units"})

PARALLELOGRAM_AREA = FormulaSpec(
    slug="parallelogram_area", title="area of a parallelogram", family="geometry",
    aliases=["area of a parallelogram", "parallelogram area"], priority=49,
    problem_template="A parallelogram has base b = {b} and height h = {h}. Find its area.",
    givens=[Given("b", "", 1, 30), Given("h", "", 1, 30)],
    outputs=[Output("A", "A = b*h", "b*h", "sq units", "compute_area", "area")],
    conventions={"units": "square units"})

CONE_VOLUME = FormulaSpec(
    slug="cone_volume", title="volume of a cone", family="geometry",
    aliases=["volume of a cone", "cone volume"], priority=48,
    problem_template="A cone has radius r = {r} and height h = {h}. Find its volume.",
    givens=[Given("r", "", 1, 12), Given("h", "", 1, 20)],
    outputs=[Output("V", "V = (1/3)*pi*r^2*h", "(1/3)*pi*r**2*h", "cubic units", "compute_volume", "volume")],
    conventions={"pi": "3.14159..."})

RECTANGLE_PERIMETER = FormulaSpec(
    slug="rectangle_perimeter", title="perimeter of a rectangle", family="geometry",
    aliases=["perimeter of a rectangle", "rectangle perimeter"], priority=47,
    problem_template="A rectangle is l = {l} by w = {w}. Find its perimeter.",
    givens=[Given("l", "", 1, 30), Given("w", "", 1, 30)],
    outputs=[Output("P", "P = 2*(l + w)", "2*(l + w)", "units", "compute_perimeter", "perimeter")],
    conventions={"units": "linear units"})

# ======================================================================================================
# FINANCE — second wave — family "finance"
# ======================================================================================================
FUTURE_VALUE = FormulaSpec(
    slug="future_value", title="future value (compound growth)", family="finance",
    aliases=["future value"], priority=46,
    problem_template="A present amount PV = ${PV} grows at r = {r}% per year for t = {t} years. Find its future "
                     "value.",
    givens=[Given("PV", "$", 100, 5000), Given("r", "%", 1, 12), Given("t", "yr", 1, 8)],
    outputs=[Output("FV", "FV = PV*(1 + r/100)^t", "PV*(1 + r/100)**t", "$", "compute_future_value",
                    "future value")],
    conventions={"model": "annual compounding"})

BREAK_EVEN = FormulaSpec(
    slug="break_even", title="break-even quantity", family="finance",
    aliases=["break-even", "break even"], priority=45,
    problem_template="Fixed costs are F = ${F}, the price per unit is p = ${p}, and the variable cost per unit "
                     "is c = ${c}. Find the break-even quantity.",
    givens=[Given("F", "$", 100, 2000), Given("p", "$", 10, 50), Given("c", "$", 1, 9)],
    outputs=[Output("q", "q = F/(p - c)", "F/(p - c)", "units", "compute_break_even", "break-even quantity")],
    conventions={"definition": "break-even = fixed cost / contribution margin"})

PROFIT_MARGIN = FormulaSpec(
    slug="profit_margin", title="profit margin", family="finance",
    aliases=["profit margin"], priority=44,
    problem_template="A product sells for revenue = ${revenue} and costs cost = ${cost}. Find the profit margin.",
    givens=[Given("revenue", "$", 50, 500), Given("cost", "$", 10, 45)],
    outputs=[Output("margin", "margin = (revenue - cost)/revenue * 100", "(revenue - cost)/revenue * 100", "%",
                    "compute_margin", "profit margin")],
    conventions={"definition": "margin = (revenue - cost) / revenue * 100"})

# ======================================================================================================
# CHEMISTRY — second wave — family "chemistry"
# ======================================================================================================
MOLES_FROM_MASS = FormulaSpec(
    slug="moles_from_mass", title="moles from mass", family="chemistry",
    aliases=["moles from mass", "mole conversion", "number of moles"], priority=43,
    problem_template="A sample has mass m = {m} g and molar mass M = {M} g/mol. Find the number of moles.",
    givens=[Given("m", "g", 5, 200), Given("M", "g/mol", 10, 100)],
    outputs=[Output("n", "n = m/M", "m/M", "mol", "compute_moles", "moles")],
    conventions={"definition": "moles = mass / molar mass"})

COMBINED_GAS_LAW = FormulaSpec(
    slug="combined_gas_law", title="combined gas law (solve for V2)", family="chemistry",
    aliases=["combined gas law"], priority=42,
    problem_template="A gas at P1 = {P1} atm, V1 = {V1} L, T1 = {T1} K changes to P2 = {P2} atm, T2 = {T2} K. "
                     "Find the new volume V2.",
    givens=[Given("P1", "atm", 1, 5), Given("V1", "L", 1, 10), Given("T1", "K", 200, 400),
            Given("P2", "atm", 1, 5), Given("T2", "K", 200, 400)],
    outputs=[Output("V2", "V2 = P1*V1*T2/(T1*P2)", "P1*V1*T2/(T1*P2)", "L", "compute_volume", "new volume")],
    conventions={"law": "P1*V1/T1 = P2*V2/T2"})

PH_POH = FormulaSpec(
    slug="ph_poh", title="pH and pOH", family="chemistry",
    aliases=["ph and poh", "poh", "ph of"], priority=41,
    problem_template="A solution has pH = {pH}. Find its pOH.",
    givens=[Given("pH", "", 1, 13)],
    outputs=[Output("pOH", "pOH = 14 - pH", "14 - pH", "", "compute_poh", "pOH")],
    conventions={"relation": "pH + pOH = 14 at 25 C"})

PERCENT_COMPOSITION = FormulaSpec(
    slug="percent_composition", title="percent composition by mass", family="chemistry",
    aliases=["percent composition", "mass percent"], priority=40,
    problem_template="An element contributes element_mass = {element_mass} g of a compound with total mass "
                     "total = {total} g. Find the percent composition.",
    givens=[Given("element_mass", "g", 1, 80), Given("total", "g", 90, 200)],
    outputs=[Output("pct", "pct = element_mass/total * 100", "element_mass/total * 100", "%",
                    "compute_percent", "percent composition")],
    conventions={"definition": "mass percent = part / whole * 100"})

# ======================================================================================================
# DISCRETE / COMBINATORICS (B6) — family "discrete"
# ======================================================================================================
FACTORIAL = FormulaSpec(
    slug="factorial", title="factorial", family="discrete",
    aliases=["factorial"], priority=39,
    problem_template="Compute n! for n = {n}.",
    givens=[Given("n", "", 3, 9)],
    outputs=[Output("result", "n! = product of 1..n", "factorial(n)", "", "compute_factorial", "factorial")],
    conventions={"definition": "n! = 1*2*...*n"})

PERMUTATIONS = FormulaSpec(
    slug="permutations", title="permutations P(n, r)", family="discrete",
    aliases=["permutations", "number of permutations", "arrangements"], priority=38,
    problem_template="Find the number of ordered arrangements of r = {r} items chosen from n = {n}.",
    givens=[Given("n", "", 5, 10), Given("r", "", 1, 4)],
    outputs=[Output("P", "P(n,r) = n!/(n-r)!", "factorial(n)/factorial(n-r)", "", "compute_permutations",
                    "permutations")],
    conventions={"formula": "P(n,r) = n! / (n-r)!"})

COMBINATIONS = FormulaSpec(
    slug="combinations", title="combinations C(n, r)", family="discrete",
    aliases=["combinations", "number of combinations", "binomial coefficient", "n choose"], priority=37,
    problem_template="Find the number of unordered selections of r = {r} items chosen from n = {n}.",
    givens=[Given("n", "", 5, 10), Given("r", "", 1, 4)],
    outputs=[Output("C", "C(n,r) = n!/(r!*(n-r)!)", "factorial(n)/(factorial(r)*factorial(n-r))", "",
                    "compute_combinations", "combinations")],
    conventions={"formula": "C(n,r) = n! / (r! (n-r)!)"})

# ======================================================================================================
# LINEAR ALGEBRA (B5) — family "linear_algebra"
# ======================================================================================================
DETERMINANT_2X2 = FormulaSpec(
    slug="determinant_2x2", title="determinant of a 2x2 matrix", family="linear_algebra",
    aliases=["determinant", "2x2 determinant"], priority=36,
    problem_template="Find the determinant of the 2x2 matrix with first row ({a}, {b}) and second row ({c}, {d}).",
    givens=[Given("a", "", 1, 12), Given("b", "", 1, 12), Given("c", "", 1, 12), Given("d", "", 1, 12)],
    outputs=[Output("det", "det = a*d - b*c", "a*d - b*c", "", "compute_determinant", "determinant")],
    conventions={"formula": "det([[a,b],[c,d]]) = ad - bc"})

VECTOR_MAGNITUDE = FormulaSpec(
    slug="vector_magnitude", title="magnitude of a 3D vector", family="linear_algebra",
    aliases=["vector magnitude", "magnitude of a vector", "magnitude of a 3d vector", "length of a vector"],
    priority=35,
    problem_template="Find the magnitude of the vector ({x}, {y}, {z}).",
    givens=[Given("x", "", 0, 10), Given("y", "", 0, 10), Given("z", "", 0, 10)],
    outputs=[Output("mag", "|v| = sqrt(x^2 + y^2 + z^2)", "sqrt(x**2 + y**2 + z**2)", "", "compute_magnitude",
                    "magnitude")],
    conventions={"formula": "Euclidean norm"})

DOT_PRODUCT_3D = FormulaSpec(
    slug="dot_product_3d", title="dot product of two 3D vectors", family="linear_algebra",
    aliases=["dot product", "scalar product"], priority=34,
    problem_template="Find the dot product of ({ax}, {ay}, {az}) and ({bx}, {by}, {bz}).",
    givens=[Given("ax", "", 0, 8), Given("ay", "", 0, 8), Given("az", "", 0, 8),
            Given("bx", "", 0, 8), Given("by", "", 0, 8), Given("bz", "", 0, 8)],
    outputs=[Output("dot", "a.b = ax*bx + ay*by + az*bz", "ax*bx + ay*by + az*bz", "", "compute_dot_product",
                    "dot product")],
    conventions={"formula": "component-wise product summed"})

# ======================================================================================================
# STATISTICS — second wave — dataset (list-input) — family "statistics"
# ======================================================================================================
COEFF_OF_VARIATION = FormulaSpec(
    slug="coefficient_of_variation", title="coefficient of variation of a dataset", family="statistics",
    aliases=["coefficient of variation"], priority=33,
    problem_template="For the dataset {xs}, find the coefficient of variation (population).",
    givens=[], dataset=Dataset("xs", size_lo=5, size_hi=8, val_lo=2, val_hi=20),
    outputs=[
        Output("mean", "mean = (sum of the values) / n", "sum(xs)/n", "", "compute_mean", "mean",
               show=[("sum of the values", "sum(xs)"), ("n", "n")]),
        Output("sd", "sd = sqrt((sum of squared deviations)/n)", "sqrt(sum((x-mean)**2 for x in xs)/n)", "",
               "compute_std_dev", "standard deviation",
               show=[("sum of squared deviations", "sum((x-mean)**2 for x in xs)"), ("n", "n")]),
        Output("cv", "cv = sd/mean * 100", "sd/mean * 100", "%", "compute_cv", "coefficient of variation",
               show=[("sd", "sd"), ("mean", "mean")])],
    conventions={"model": "population; cv = sd/mean * 100"})

MEAN_ABS_DEVIATION = FormulaSpec(
    slug="mean_absolute_deviation", title="mean absolute deviation of a dataset", family="statistics",
    aliases=["mean absolute deviation"], priority=32,
    problem_template="For the dataset {xs}, find the mean absolute deviation.",
    givens=[], dataset=Dataset("xs", size_lo=5, size_hi=8, val_lo=1, val_hi=20),
    outputs=[
        Output("mean", "mean = (sum of the values) / n", "sum(xs)/n", "", "compute_mean", "mean",
               show=[("sum of the values", "sum(xs)"), ("n", "n")]),
        Output("mad", "mad = (sum of |x - mean|) / n", "sum(abs(x-mean) for x in xs)/n", "",
               "compute_mad", "mean absolute deviation",
               show=[("sum of |x - mean|", "sum(abs(x-mean) for x in xs)"), ("n", "n")])],
    conventions={"definition": "average absolute distance from the mean"})

# ======================================================================================================
# RATES / SEQUENCES / CONVERSIONS — algebra & everyday math
# ======================================================================================================
DISTANCE_RATE_TIME = FormulaSpec(
    slug="distance_rate_time", title="distance from rate and time", family="algebra",
    aliases=["distance rate time", "distance from rate", "distance traveled", "d = rt"], priority=31,
    problem_template="An object travels at rate r = {r} for time t = {t}. Find the distance.",
    givens=[Given("r", "units/hr", 1, 60), Given("t", "hr", 1, 10)],
    outputs=[Output("d", "d = r*t", "r*t", "units", "compute_distance", "distance")],
    conventions={"relation": "distance = rate x time"})

AVERAGE_SPEED = FormulaSpec(
    slug="average_speed", title="average speed", family="physics",
    aliases=["average speed", "speed formula"], priority=30,
    problem_template="An object covers distance d = {d} in time t = {t}. Find the average speed.",
    givens=[Given("d", "m", 10, 300), Given("t", "s", 1, 10)],
    outputs=[Output("v", "v = d/t", "d/t", "m/s", "compute_speed", "average speed")],
    conventions={"relation": "speed = distance / time"})

CELSIUS_TO_FAHRENHEIT = FormulaSpec(
    slug="celsius_to_fahrenheit", title="Celsius to Fahrenheit conversion", family="physics",
    aliases=["celsius to fahrenheit"], priority=29,
    problem_template="Convert C = {C} degrees Celsius to Fahrenheit.",
    givens=[Given("C", "deg C", 0, 40)],
    outputs=[Output("F", "F = (9*C)/5 + 32", "(9*C)/5 + 32", "deg F", "compute_fahrenheit", "temperature")],
    conventions={"relation": "F = 9C/5 + 32"})

ARITHMETIC_SEQUENCE_TERM = FormulaSpec(
    slug="arithmetic_sequence_term", title="nth term of an arithmetic sequence", family="algebra",
    aliases=["arithmetic sequence", "arithmetic progression", "nth term of an arithmetic"], priority=28,
    problem_template="An arithmetic sequence has first term a1 = {a1} and common difference d = {d}. "
                     "Find the term at position n = {n}.",
    givens=[Given("a1", "", 1, 10), Given("d", "", 1, 8), Given("n", "", 2, 10)],
    outputs=[Output("a_n", "a_n = a1 + (n-1)*d", "a1 + (n-1)*d", "", "compute_term", "nth term")],
    conventions={"formula": "a_n = a1 + (n-1)d"})

GEOMETRIC_SEQUENCE_TERM = FormulaSpec(
    slug="geometric_sequence_term", title="nth term of a geometric sequence", family="algebra",
    aliases=["geometric sequence", "geometric progression", "nth term of a geometric"], priority=27,
    problem_template="A geometric sequence has first term a1 = {a1} and common ratio r = {r}. "
                     "Find the term at position n = {n}.",
    givens=[Given("a1", "", 1, 6), Given("r", "", 2, 3), Given("n", "", 2, 5)],
    outputs=[Output("a_n", "a_n = a1 * r^(n-1)", "a1 * r**(n-1)", "", "compute_term", "nth term")],
    conventions={"formula": "a_n = a1 * r^(n-1)"})

# ======================================================================================================
# TRIGONOMETRY / BUSINESS MATH / MORE PHYSICS
# ======================================================================================================
TANGENT_RATIO = FormulaSpec(
    slug="tangent_ratio", title="tangent ratio in a right triangle", family="geometry",
    aliases=["tangent ratio", "tangent of the angle", "opposite over adjacent"], priority=26,
    problem_template="In a right triangle the side opposite the angle is opp = {opp} and the adjacent side is "
                     "adj = {adj}. Find the tangent of the angle.",
    givens=[Given("opp", "", 1, 20), Given("adj", "", 1, 20)],
    outputs=[Output("tan", "tan = opp/adj", "opp/adj", "", "compute_tangent", "tangent")],
    conventions={"definition": "tangent = opposite / adjacent"})

PERCENT_OF = FormulaSpec(
    slug="percent_of", title="percent of a number", family="algebra",
    aliases=["percent of", "percentage of a number"], not_aliases=["change", "yield", "composition"], priority=25,
    problem_template="What is percent = {percent}% of whole = {whole}?",
    givens=[Given("percent", "%", 5, 95), Given("whole", "", 20, 200)],
    outputs=[Output("result", "result = (percent*whole)/100", "(percent*whole)/100", "", "compute_result",
                    "the amount")],
    conventions={"definition": "percent of a whole = percent/100 x whole"})

DISCOUNT_PRICE = FormulaSpec(
    slug="discount_price", title="discounted sale price", family="finance",
    aliases=["discount", "sale price", "discounted price"], priority=24,
    problem_template="An item priced price = ${price} is discounted disc = {disc}%. Find the sale price.",
    givens=[Given("price", "$", 20, 200), Given("disc", "%", 5, 50)],
    outputs=[Output("sale", "sale = price*(1 - disc/100)", "price*(1 - disc/100)", "$", "compute_sale_price",
                    "sale price")],
    conventions={"definition": "sale price = price x (1 - discount)"})

SALES_TAX_TOTAL = FormulaSpec(
    slug="sales_tax_total", title="total price with sales tax", family="finance",
    aliases=["sales tax", "total with tax", "price with tax"], priority=23,
    problem_template="An item priced price = ${price} has sales tax tax = {tax}%. Find the total price.",
    givens=[Given("price", "$", 10, 200), Given("tax", "%", 4, 15)],
    outputs=[Output("total", "total = price*(1 + tax/100)", "price*(1 + tax/100)", "$", "compute_total",
                    "total price")],
    conventions={"definition": "total = price x (1 + tax rate)"})

POWER_FROM_CURRENT = FormulaSpec(
    slug="power_from_current", title="power dissipated from current and resistance", family="physics",
    aliases=["power from current", "i squared r", "power dissipated"], priority=22,
    problem_template="A current I = {I} A flows through a resistor R = {R} ohm. Find the power dissipated.",
    givens=[Given("I", "A", 1, 10), Given("R", "ohm", 1, 20)],
    outputs=[Output("P", "P = I^2 * R", "I**2 * R", "W", "compute_power", "power dissipated")],
    conventions={"law": "P = I^2 R", "units": "SI"})

PENDULUM_PERIOD = FormulaSpec(
    slug="pendulum_period", title="period of a simple pendulum", family="physics",
    aliases=["pendulum", "period of a pendulum"], priority=21, constants={"g": 9.8},
    problem_template="A simple pendulum has length L = {L} m. Find its period (g = 9.8 m/s^2).",
    givens=[Given("L", "m", 1, 10)],
    outputs=[Output("T", "T = 2*pi*sqrt(L/g)", "2*pi*sqrt(L/g)", "s", "compute_period", "period")],
    conventions={"g": "9.8 m/s^2", "formula": "T = 2*pi*sqrt(L/g)"})

SECTOR_AREA = FormulaSpec(
    slug="sector_area", title="area of a circular sector", family="geometry",
    aliases=["sector area", "area of a sector"], priority=20,
    problem_template="A circular sector has radius r = {r} and central angle theta = {theta} degrees. "
                     "Find its area.",
    givens=[Given("r", "", 1, 15), Given("theta", "deg", 30, 300)],
    outputs=[Output("A", "A = (theta/360)*pi*r^2", "(theta/360)*pi*r**2", "sq units", "compute_area", "sector area")],
    conventions={"pi": "3.14159..."})

ARC_LENGTH = FormulaSpec(
    slug="arc_length", title="arc length of a circular sector", family="geometry",
    aliases=["arc length"], priority=19,
    problem_template="A circular arc has radius r = {r} and central angle theta = {theta} degrees. "
                     "Find its length.",
    givens=[Given("r", "", 1, 15), Given("theta", "deg", 30, 300)],
    outputs=[Output("L", "L = (theta/360)*2*pi*r", "(theta/360)*2*pi*r", "units", "compute_length", "arc length")],
    conventions={"pi": "3.14159..."})

SIMPLE_ROI = FormulaSpec(
    slug="simple_roi", title="return on investment", family="finance",
    aliases=["return on investment", "roi"], priority=18,
    problem_template="An investment costing cost = ${cost} returns gain = ${gain}. Find the return on "
                     "investment (ROI).",
    givens=[Given("cost", "$", 50, 500), Given("gain", "$", 60, 800)],
    outputs=[Output("roi", "roi = (gain - cost)/cost * 100", "(gain - cost)/cost * 100", "%", "compute_roi",
                    "ROI")],
    conventions={"definition": "ROI = (gain - cost) / cost * 100"})

PROBABILITY_SIMPLE = FormulaSpec(
    slug="probability_simple", title="probability of a simple event", family="statistics",
    aliases=["simple probability", "probability of an event", "theoretical probability"], priority=17,
    problem_template="An event has favorable = {favorable} favorable outcomes and unfavorable = {unfavorable} "
                     "unfavorable outcomes. Find its probability.",
    givens=[Given("favorable", "", 1, 12), Given("unfavorable", "", 1, 12)],
    outputs=[Output("P", "P = favorable/(favorable + unfavorable)", "favorable/(favorable + unfavorable)", "",
                    "compute_probability", "probability")],
    conventions={"definition": "P = favorable outcomes / total outcomes"})

LAW_OF_TOTAL_PROBABILITY = FormulaSpec(
    slug="law_of_total_probability", title="the law of total probability", family="statistics",
    aliases=["law of total probability", "total probability"], priority=40,
    problem_template=(
        "Events B1 and B2 partition the sample space with P(B1) = {P_B1} (so P(B2) = 1 - P(B1)). "
        "Event A has conditional probabilities P(A|B1) = {P_A_given_B1} and P(A|B2) = {P_A_given_B2}. "
        "Find the total probability P(A)."),
    givens=[Given("P_B1", "", 0.2, 0.8, integer=False),
            Given("P_A_given_B1", "", 0.1, 0.9, integer=False),
            Given("P_A_given_B2", "", 0.1, 0.9, integer=False)],
    outputs=[
        Output("P_B2", "P_B2 = 1 - P_B1", "1 - P_B1", "", "compute_partition_complement",
               "the remaining partition probability"),
        Output("P_A", "P_A = P_A_given_B1*P_B1 + P_A_given_B2*P_B2",
               "P_A_given_B1*P_B1 + P_A_given_B2*P_B2", "", "compute_total_probability", "total probability")],
    conventions={"law": "P(A) = P(A|B1)P(B1) + P(A|B2)P(B2), where the partition satisfies P(B1) + P(B2) = 1"},
    # Reject a degenerate instance: with P(A|B1)==P(A|B2) the total trivially equals the common conditional and
    # the partition weighting looks irrelevant — a poor first illustration of the law. Also keep the partition
    # off a 50/50 split so the weighting is visibly doing work.
    instance_ok=lambda r: abs(r["P_A_given_B1"] - r["P_A_given_B2"]) >= 0.2 and abs(r["P_B1"] - 0.5) >= 0.1,
    # General n-partition form as isolated math; the worked example uses the concrete 2-partition instance.
    canonical_latex="P(A) = \\sum_{i} P(A|B_i)P(B_i)",
    # Symbols are wrapped in inline math \(...\) so B_i renders as a subscript in the prose too — matching the
    # equation (otherwise the prose shows a literal "B_i" while the equation shows B-subscript-i).
    canonical_notes=[
        "A is the event; the partitions \\(B_i\\) are disjoint and together cover the whole sample space, so "
        "their probabilities sum to 1.",
        "\\(P(A|B_i)\\): probability of A within partition \\(B_i\\).",
        "\\(P(B_i)\\): probability of partition \\(B_i\\).",
    ],
    edge_cases=[
        "If a partition has \\(P(B_i) = 0\\), that term contributes 0 to \\(P(A)\\) — an impossible condition "
        "simply drops out of the sum.",
        "The partitions must be disjoint and together cover the whole sample space; if they overlap or leave "
        "gaps, the sum is not a valid total probability.",
    ],
    display_names={"P_A_given_B1": "P(A|B1)", "P_A_given_B2": "P(A|B2)",
                   "P_B1": "P(B1)", "P_B2": "P(B2)", "P_A": "P(A)"})

BAYES_THEOREM = FormulaSpec(
    slug="bayes_theorem", title="Bayes' theorem", family="statistics",
    aliases=["bayes theorem", "bayes' theorem", "bayes rule", "bayes' rule"],
    not_aliases=["naive bayes"], priority=42,
    problem_template=(
        "A condition D has prior probability P(D) = {P_D}. A test is positive with probability "
        "P(pos|D) = {P_pos_given_D} when D is present and P(pos|not D) = {P_pos_given_notD} when it is absent. "
        "Given a positive test result, find the posterior P(D|pos) using Bayes' theorem."),
    givens=[Given("P_D", "", 0.1, 0.3, integer=False),
            Given("P_pos_given_D", "", 0.7, 0.9, integer=False),
            Given("P_pos_given_notD", "", 0.1, 0.3, integer=False)],
    outputs=[
        Output("P_not_D", "P_not_D = 1 - P_D", "1 - P_D", "", "compute_complement_prior",
               "prior probability of the complement"),
        Output("P_pos", "P_pos = P_pos_given_D*P_D + P_pos_given_notD*P_not_D",
               "P_pos_given_D*P_D + P_pos_given_notD*P_not_D", "", "compute_evidence_probability",
               "total probability of a positive test"),
        Output("P_D_given_pos", "P_D_given_pos = P_pos_given_D*P_D / P_pos",
               "P_pos_given_D*P_D / P_pos", "", "apply_bayes_theorem", "posterior probability")],
    conventions={"theorem": "P(D|pos) = P(pos|D)P(D) / P(pos); the evidence P(pos) itself comes from the law "
                            "of total probability: P(pos) = P(pos|D)P(D) + P(pos|not D)P(not D)"},
    # Canonical A|B form as isolated math — the most common textbook intro notation, so it matches the
    # LLM-authored definition/background cards (which use P(A|B) = P(B|A)P(A)/P(B)); the worked example keeps
    # the concrete disease/test symbols.
    canonical_latex="P(A|B) = \\frac{P(B|A)P(A)}{P(B)}",
    canonical_notes=[
        "A is the hypothesis (the event whose probability you are updating); B is the observed evidence.",
        "\\(P(A)\\): prior probability.  \\(P(B|A)\\): likelihood.  \\(P(A|B)\\): posterior probability.",
        "The denominator is the total probability of the evidence: "
        "$$P(B) = P(B|A)P(A) + P(B|A^c)P(A^c)$$",
    ],
    edge_cases=[
        "If the evidence is impossible (\\(P(B) = 0\\)), the posterior \\(P(A|B)\\) is undefined — the formula "
        "divides by zero.",
        "If the prior \\(P(A) = 0\\), then \\(P(A|B) = 0\\): an impossible hypothesis stays impossible no "
        "matter what evidence appears.",
    ],
    display_names={"P_pos_given_D": "P(pos|D)", "P_pos_given_notD": "P(pos|not D)", "P_not_D": "P(not D)",
                   "P_D_given_pos": "P(D|pos)", "P_pos": "P(pos)", "P_D": "P(D)"})

CONDITIONAL_PROBABILITY = FormulaSpec(
    slug="conditional_probability", title="conditional probability", family="statistics",
    aliases=["conditional probability"], priority=38,
    problem_template=(
        "In a sample, {n_A_and_B} outcomes satisfy both A and B, and {n_B_not_A} satisfy B but not A. "
        "Find the conditional probability P(A|B) = P(A and B) / P(B)."),
    givens=[Given("n_A_and_B", "", 1, 9), Given("n_B_not_A", "", 1, 9)],
    outputs=[
        Output("n_B", "n_B = n_A_and_B + n_B_not_A", "n_A_and_B + n_B_not_A", "", "compute_condition_total",
               "outcomes satisfying B"),
        Output("P_A_given_B", "P_A_given_B = n_A_and_B / n_B", "n_A_and_B / n_B", "",
               "compute_conditional_probability", "conditional probability")],
    conventions={"definition": "P(A|B) = P(A and B) / P(B) = (outcomes with A and B) / (outcomes with B)"},
    canonical_latex="P(A|B) = \\frac{P(A∩B)}{P(B)}",
    canonical_notes=[
        "\\(P(A∩B)\\): probability that A and B both occur.",
        "\\(P(B)\\): probability of the condition B (must be greater than 0).",
    ],
    edge_cases=[
        "\\(P(A|B)\\) is only defined when \\(P(B) > 0\\); conditioning on an impossible event is undefined.",
    ],
    display_names={"n_A_and_B": "n(A and B)", "n_B_not_A": "n(B but not A)", "n_B": "n(B)",
                   "P_A_given_B": "P(A|B)"})

MOLE_FRACTION = FormulaSpec(
    slug="mole_fraction", title="mole fraction", family="chemistry",
    aliases=["mole fraction"], priority=16,
    problem_template="A mixture has na = {na} mol of component A and nb = {nb} mol of component B. "
                     "Find the mole fraction of A.",
    givens=[Given("na", "mol", 1, 10), Given("nb", "mol", 1, 10)],
    outputs=[Output("x_A", "x_A = na/(na + nb)", "na/(na + nb)", "", "compute_mole_fraction", "mole fraction")],
    conventions={"definition": "mole fraction = moles of component / total moles"})

OHMS_POWER = FormulaSpec(
    slug="ohms_power", title="power from voltage and resistance", family="physics",
    aliases=["power from voltage", "v squared over r"], priority=15,
    problem_template="A voltage V = {V} V is across a resistor R = {R} ohm. Find the power dissipated.",
    givens=[Given("V", "V", 2, 24), Given("R", "ohm", 1, 12)],
    outputs=[Output("P", "P = V^2/R", "V**2/R", "W", "compute_power", "power")],
    conventions={"law": "P = V^2 / R"})

KELVIN_CONVERSION = FormulaSpec(
    slug="kelvin_conversion", title="Celsius to Kelvin conversion", family="physics",
    aliases=["celsius to kelvin", "kelvin conversion"], priority=14,
    problem_template="Convert C = {C} degrees Celsius to Kelvin.",
    givens=[Given("C", "deg C", 0, 100)],
    outputs=[Output("K", "K = C + 273", "C + 273", "K", "compute_kelvin", "temperature")],
    conventions={"relation": "K = C + 273"})

FAHRENHEIT_TO_CELSIUS = FormulaSpec(
    slug="fahrenheit_to_celsius", title="Fahrenheit to Celsius conversion", family="physics",
    aliases=["fahrenheit to celsius"], priority=13,
    problem_template="Convert F = {F} degrees Fahrenheit to Celsius.",
    givens=[Given("F", "deg F", 32, 212)],
    outputs=[Output("C", "C = 5*(F - 32)/9", "5*(F - 32)/9", "deg C", "compute_celsius", "temperature")],
    conventions={"relation": "C = 5(F - 32)/9"})

SPRING_PERIOD = FormulaSpec(
    slug="spring_period", title="period of a mass-spring oscillator", family="physics",
    aliases=["period of a spring", "mass-spring period", "spring oscillation"], priority=12,
    problem_template="A mass m = {m} kg hangs from a spring of stiffness k = {k} N/m. Find the period of "
                     "oscillation.",
    givens=[Given("m", "kg", 1, 10), Given("k", "N/m", 1, 20)],
    outputs=[Output("T", "T = 2*pi*sqrt(m/k)", "2*pi*sqrt(m/k)", "s", "compute_period", "period")],
    conventions={"formula": "T = 2*pi*sqrt(m/k)"})

MOLES_IDEAL_GAS = FormulaSpec(
    slug="moles_ideal_gas", title="moles of gas from the ideal gas law", family="chemistry",
    aliases=["moles of gas", "moles from pv"], priority=11, constants={"R": 0.0821},
    problem_template="A gas at P = {P} atm occupies V = {V} L at T = {T} K. Find the number of moles "
                     "(R = 0.0821).",
    givens=[Given("P", "atm", 1, 5), Given("V", "L", 1, 20), Given("T", "K", 200, 400)],
    outputs=[Output("n", "n = (P*V)/(R*T)", "(P*V)/(R*T)", "mol", "compute_moles", "moles")],
    conventions={"law": "PV = nRT"})

FREQUENCY_FROM_PERIOD = FormulaSpec(
    slug="frequency_from_period", title="frequency from period", family="physics",
    aliases=["frequency from period", "frequency and period"], priority=9,
    problem_template="A wave has period T = {T} s. Find its frequency.",
    givens=[Given("T", "s", 1, 10)],
    outputs=[Output("f", "f = 1/T", "1/T", "Hz", "compute_frequency", "frequency")],
    conventions={"relation": "f = 1/T"})

BOYLES_LAW = FormulaSpec(
    slug="boyles_law", title="Boyle's law (solve for the new volume)", family="chemistry",
    aliases=["boyle's law", "boyles law"], priority=8,
    problem_template="A gas at P1 = {P1} atm, V1 = {V1} L is compressed to P2 = {P2} atm at constant "
                     "temperature. Find the new volume V2.",
    givens=[Given("P1", "atm", 1, 5), Given("V1", "L", 1, 10), Given("P2", "atm", 1, 5)],
    outputs=[Output("V2", "V2 = (P1*V1)/P2", "(P1*V1)/P2", "L", "compute_volume", "new volume")],
    conventions={"law": "P1*V1 = P2*V2"})

CHARLES_LAW = FormulaSpec(
    slug="charles_law", title="Charles's law (solve for the new volume)", family="chemistry",
    aliases=["charles's law", "charles law"], priority=7,
    problem_template="A gas at V1 = {V1} L, T1 = {T1} K is heated to T2 = {T2} K at constant pressure. "
                     "Find the new volume V2.",
    givens=[Given("V1", "L", 1, 10), Given("T1", "K", 200, 400), Given("T2", "K", 200, 400)],
    outputs=[Output("V2", "V2 = (V1*T2)/T1", "(V1*T2)/T1", "L", "compute_volume", "new volume")],
    conventions={"law": "V1/T1 = V2/T2"})

OHMS_RESISTANCE = FormulaSpec(
    slug="ohms_resistance", title="resistance from voltage and current", family="physics",
    aliases=["find the resistance", "resistance from voltage"], priority=6,
    problem_template="A resistor carries current I = {I} A under voltage V = {V} V. Find its resistance.",
    givens=[Given("V", "V", 2, 24), Given("I", "A", 1, 12)],
    outputs=[Output("R", "R = V/I", "V/I", "ohm", "compute_resistance", "resistance")],
    conventions={"law": "Ohm's law R = V/I"})

HEAT_ENERGY = FormulaSpec(
    slug="heat_energy", title="heat energy from specific heat", family="physics",
    aliases=["heat energy", "specific heat", "q = mc"], priority=5,
    problem_template="A mass m = {m} g of a substance with specific heat c = {c} is heated by dT = {dT} "
                     "degrees. Find the heat energy.",
    givens=[Given("m", "g", 1, 50), Given("c", "J/g/deg", 1, 5), Given("dT", "deg", 1, 50)],
    outputs=[Output("Q", "Q = m*c*dT", "m*c*dT", "J", "compute_heat", "heat energy")],
    conventions={"formula": "Q = m*c*dT"})

FLUID_PRESSURE = FormulaSpec(
    slug="fluid_pressure", title="hydrostatic pressure at depth", family="physics",
    aliases=["fluid pressure", "pressure at depth", "hydrostatic pressure"], priority=4, constants={"g": 9.8},
    problem_template="Find the pressure at depth h = {h} m in a fluid of density rho = {rho} kg/m^3 "
                     "(g = 9.8 m/s^2).",
    givens=[Given("rho", "kg/m^3", 800, 1200), Given("h", "m", 1, 20)],
    outputs=[Output("P", "P = rho*g*h", "rho*g*h", "Pa", "compute_pressure", "pressure")],
    conventions={"formula": "P = rho*g*h"})

CUBE_VOLUME = FormulaSpec(
    slug="cube_volume", title="volume of a cube", family="geometry",
    aliases=["volume of a cube", "cube volume"], priority=3,
    problem_template="A cube has side s = {s}. Find its volume.",
    givens=[Given("s", "", 1, 12)],
    outputs=[Output("V", "V = s^3", "s**3", "cubic units", "compute_volume", "volume")],
    conventions={"formula": "V = s^3"})

CUBE_SURFACE_AREA = FormulaSpec(
    slug="cube_surface_area", title="surface area of a cube", family="geometry",
    aliases=["surface area of a cube", "cube surface area"], priority=2,
    problem_template="A cube has side s = {s}. Find its surface area.",
    givens=[Given("s", "", 1, 12)],
    outputs=[Output("A", "A = 6*s^2", "6*s**2", "sq units", "compute_area", "surface area")],
    conventions={"formula": "A = 6*s^2"})

HOOKES_FORCE = FormulaSpec(
    slug="hookes_force", title="spring force (Hooke's law)", family="physics",
    aliases=["hooke's law", "hookes law", "spring force"], priority=1,
    problem_template="A spring of stiffness k = {k} N/m is stretched by x = {x} m. Find the restoring force.",
    givens=[Given("k", "N/m", 1, 50), Given("x", "m", 1, 10)],
    outputs=[Output("F", "F = k*x", "k*x", "N", "compute_force", "spring force")],
    conventions={"law": "F = kx"})

ROOT_MEAN_SQUARE = FormulaSpec(
    slug="root_mean_square", title="root mean square of a dataset", family="statistics",
    aliases=["root mean square", "rms"], priority=31,
    problem_template="For the dataset {xs}, find the root mean square (RMS).",
    givens=[], dataset=Dataset("xs", size_lo=4, size_hi=6, val_lo=1, val_hi=12),
    outputs=[Output("rms", "rms = sqrt((sum of the squares)/n)", "sqrt(sum(x**2 for x in xs)/n)", "",
                    "compute_rms", "root mean square",
                    show=[("sum of the squares", "sum(x**2 for x in xs)"), ("n", "n")])],
    conventions={"definition": "RMS = sqrt(mean of the squares)"})

POLYGON_INTERIOR_ANGLE = FormulaSpec(
    slug="polygon_interior_angle", title="interior angle of a regular polygon", family="geometry",
    aliases=["interior angle of a polygon", "interior angle", "polygon interior angle"], priority=30,
    problem_template="Find the measure of each interior angle of a regular polygon with n = {n} sides.",
    givens=[Given("n", "sides", 3, 12)],
    outputs=[Output("angle", "angle = (n - 2)*180/n", "(n - 2)*180/n", "deg", "compute_angle",
                    "interior angle")],
    conventions={"formula": "interior angle = (n-2)*180/n"})

POLYGON_EXTERIOR_ANGLE = FormulaSpec(
    slug="polygon_exterior_angle", title="exterior angle of a regular polygon", family="geometry",
    aliases=["exterior angle of a polygon", "exterior angle", "polygon exterior angle"], priority=28,
    problem_template="Find the measure of each exterior angle of a regular polygon with n = {n} sides.",
    givens=[Given("n", "sides", 3, 12)],
    outputs=[Output("angle", "angle = 360/n", "360/n", "deg", "compute_angle", "exterior angle")],
    conventions={"formula": "exterior angle = 360/n"})

EFFICIENCY = FormulaSpec(
    slug="efficiency", title="energy efficiency", family="physics",
    aliases=["efficiency", "energy efficiency"], priority=43,
    problem_template="A machine delivers useful = {useful} J of useful energy and wastes wasted = {wasted} J. "
                     "Find its efficiency.",
    givens=[Given("useful", "J", 10, 100), Given("wasted", "J", 1, 50)],
    outputs=[Output("eff", "eff = useful/(useful + wasted) * 100", "useful/(useful + wasted) * 100", "%",
                    "compute_efficiency", "efficiency")],
    conventions={"definition": "efficiency = useful / total energy * 100"})

PERCENT_ERROR = FormulaSpec(
    slug="percent_error", title="percent error", family="statistics",
    aliases=["percent error", "percentage error"], priority=42,
    problem_template="A measurement is measured = {measured} against a true value actual = {actual}. "
                     "Find the percent error.",
    givens=[Given("measured", "", 1, 100), Given("actual", "", 1, 100)],
    outputs=[Output("error", "error = abs(measured - actual)/actual * 100", "abs(measured - actual)/actual * 100",
                    "%", "compute_error", "percent error")],
    conventions={"definition": "percent error = |measured - actual| / actual * 100"})

UNIT_PRICE = FormulaSpec(
    slug="unit_price", title="unit price", family="finance",
    aliases=["unit price", "price per unit"], priority=41,
    problem_template="A package of quantity = {quantity} units costs price = ${price}. Find the unit price.",
    givens=[Given("price", "$", 2, 100), Given("quantity", "", 2, 20)],
    outputs=[Output("unit", "unit = price/quantity", "price/quantity", "$/unit", "compute_unit_price",
                    "unit price")],
    conventions={"definition": "unit price = total price / quantity"})

IMPULSE = FormulaSpec(
    slug="impulse", title="impulse of a force", family="physics",
    aliases=["impulse"], priority=39,
    problem_template="A force F = {F} N acts for time t = {t} s. Find the impulse.",
    givens=[Given("F", "N", 1, 50), Given("t", "s", 1, 10)],
    outputs=[Output("J", "J = F*t", "F*t", "N*s", "compute_impulse", "impulse")],
    conventions={"formula": "impulse = force x time"})

FREE_FALL_VELOCITY = FormulaSpec(
    slug="free_fall_velocity", title="velocity of a freely falling object", family="physics",
    aliases=["free fall velocity", "velocity in free fall", "falling object velocity"], priority=44,
    constants={"g": 9.8},
    problem_template="An object is dropped and falls for t = {t} s. Find its velocity (g = 9.8 m/s^2).",
    givens=[Given("t", "s", 1, 10)],
    outputs=[Output("v", "v = g*t", "g*t", "m/s", "compute_velocity", "velocity")],
    conventions={"g": "9.8 m/s^2"})

FREE_FALL_DISTANCE = FormulaSpec(
    slug="free_fall_distance", title="distance a freely falling object drops", family="physics",
    aliases=["free fall distance", "distance fallen", "falling object distance"], priority=38,
    constants={"g": 9.8},
    problem_template="An object is dropped and falls for t = {t} s. Find the distance fallen (g = 9.8 m/s^2).",
    givens=[Given("t", "s", 1, 10)],
    outputs=[Output("d", "d = (g*t^2)/2", "(g*t**2)/2", "m", "compute_distance", "distance")],
    conventions={"g": "9.8 m/s^2"})

POTENTIAL_TO_KINETIC = FormulaSpec(
    slug="potential_to_kinetic", title="speed from a height drop (energy conservation)", family="physics",
    aliases=["speed from height", "velocity from height", "energy conservation speed"], priority=37,
    constants={"g": 9.8},
    problem_template="An object falls from rest through height h = {h} m. Find its speed at the bottom "
                     "(g = 9.8 m/s^2).",
    givens=[Given("h", "m", 1, 30)],
    outputs=[Output("v", "v = sqrt(2*g*h)", "sqrt(2*g*h)", "m/s", "compute_speed", "speed")],
    conventions={"principle": "1/2 m v^2 = m g h"})

SPHERE_SURFACE_AREA = FormulaSpec(
    slug="sphere_surface_area", title="surface area of a sphere", family="geometry",
    aliases=["surface area of a sphere", "sphere surface area"], priority=36,
    problem_template="A sphere has radius r = {r}. Find its surface area.",
    givens=[Given("r", "", 1, 15)],
    outputs=[Output("A", "A = 4*pi*r^2", "4*pi*r**2", "sq units", "compute_area", "surface area")],
    conventions={"pi": "3.14159..."})

DENSITY_MASS = FormulaSpec(
    slug="mass_from_density", title="mass from density and volume", family="chemistry",
    aliases=["mass from density", "mass = density x volume"], priority=93,  # > density (91): "mass from …" wins
    problem_template="A material has density rho = {rho} g/mL and volume V = {V} mL. Find its mass.",
    givens=[Given("rho", "g/mL", 1, 20), Given("V", "mL", 1, 50)],
    outputs=[Output("m", "m = rho*V", "rho*V", "g", "compute_mass", "mass")],
    conventions={"relation": "mass = density x volume"})

PERCENT_INCREASE = FormulaSpec(
    slug="percent_increase", title="new value after a percent increase", family="finance",
    aliases=["percent increase", "increase by a percent"], priority=34,
    problem_template="A value original = {original} increases by pct = {pct}%. Find the new value.",
    givens=[Given("original", "", 10, 200), Given("pct", "%", 1, 50)],
    outputs=[Output("new_value", "new = original*(1 + pct/100)", "original*(1 + pct/100)", "",
                    "compute_new_value", "new value")],
    conventions={"definition": "new = original x (1 + percent)"})

# --- the full concept set; ALL_SPECS drives the gate, the registry, the manifest, and routing ---------
ALL_SPECS = [
    # physics / EE
    KINEMATICS, KINETIC_ENERGY, NEWTONS_SECOND_LAW, WEIGHT_FORCE, MOMENTUM, WORK_DONE, GRAVITATIONAL_PE, OHMS_LAW,
    PROJECTILE_RANGE, CENTRIPETAL_ACCEL, WAVE_SPEED, PRESSURE, MECHANICAL_POWER, SPRING_PE,
    # finance
    SIMPLE_INTEREST, COMPOUND_INTEREST, PRESENT_VALUE, PERCENT_CHANGE, FUTURE_VALUE, BREAK_EVEN, PROFIT_MARGIN,
    # geometry
    CIRCLE_AREA, CIRCLE_CIRCUMFERENCE, RECTANGLE_AREA, TRIANGLE_AREA, PYTHAGOREAN, SPHERE_VOLUME, CYLINDER_VOLUME,
    COORDINATE_DISTANCE, MIDPOINT, SLOPE, TRAPEZOID_AREA, PARALLELOGRAM_AREA, CONE_VOLUME, RECTANGLE_PERIMETER,
    # chemistry
    MOLARITY, DENSITY, IDEAL_GAS_PRESSURE, DILUTION, PERCENT_YIELD,
    MOLES_FROM_MASS, COMBINED_GAS_LAW, PH_POH, PERCENT_COMPOSITION,
    # discrete / combinatorics
    FACTORIAL, PERMUTATIONS, COMBINATIONS,
    # linear algebra
    DETERMINANT_2X2, VECTOR_MAGNITUDE, DOT_PRODUCT_3D,
    # statistics
    DESCRIPTIVE_STATS, MEDIAN_RANGE, Z_SCORE, COEFF_OF_VARIATION, MEAN_ABS_DEVIATION,
    WEIGHTED_MEAN, COVARIANCE,
    # rates / sequences / conversions
    DISTANCE_RATE_TIME, AVERAGE_SPEED, CELSIUS_TO_FAHRENHEIT, ARITHMETIC_SEQUENCE_TERM, GEOMETRIC_SEQUENCE_TERM,
    # trig / business math / more physics
    TANGENT_RATIO, PERCENT_OF, DISCOUNT_PRICE, SALES_TAX_TOTAL, POWER_FROM_CURRENT, PENDULUM_PERIOD,
    # more geometry / finance
    SECTOR_AREA, ARC_LENGTH, SIMPLE_ROI,
    # probability / chemistry / EE
    PROBABILITY_SIMPLE, LAW_OF_TOTAL_PROBABILITY, BAYES_THEOREM, CONDITIONAL_PROBABILITY,
    MOLE_FRACTION, OHMS_POWER,
    # conversions / oscillation / gas
    KELVIN_CONVERSION, FAHRENHEIT_TO_CELSIUS, SPRING_PERIOD, MOLES_IDEAL_GAS, FREQUENCY_FROM_PERIOD,
    # gas laws / circuits / thermo
    BOYLES_LAW, CHARLES_LAW, OHMS_RESISTANCE, HEAT_ENERGY, FLUID_PRESSURE,
    # solids / hooke / rms
    CUBE_VOLUME, CUBE_SURFACE_AREA, HOOKES_FORCE, ROOT_MEAN_SQUARE,
    # polygon angles
    POLYGON_INTERIOR_ANGLE, POLYGON_EXTERIOR_ANGLE,
    # efficiency / error / pricing / impulse
    EFFICIENCY, PERCENT_ERROR, UNIT_PRICE, IMPULSE,
    # free fall / energy
    FREE_FALL_VELOCITY, FREE_FALL_DISTANCE, POTENTIAL_TO_KINETIC,
    # more solids / density / percent
    SPHERE_SURFACE_AREA, DENSITY_MASS, PERCENT_INCREASE,
]
