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
    canonical_latex="v = u + at",
    canonical_notes=[
        "\\(u\\): initial velocity.  \\(a\\): the (constant) acceleration.  \\(t\\): elapsed time.",
        "Displacement over the same time: \\(s = ut + \\frac{1}{2}at^2\\).",
    ],
    edge_cases=[
        "These hold ONLY for constant acceleration; if \\(a\\) varies over time they do not apply.",
        "With \\(a = 0\\) the motion is uniform: \\(v = u\\) and \\(s = ut\\).",
    ],
    cases=[Case("zero_initial_velocity", lambda g: g["u"] == 0),
           Case("nonzero_initial_velocity", lambda g: g["u"] != 0)], must_avoid=["zero_time"])

KINETIC_ENERGY = FormulaSpec(
    slug="kinetic_energy", title="kinetic energy of a moving body", family="physics",
    # 'turbulent' guard: "Turbulent Kinetic Energy" is a DIFFERENT quantity (fluctuation energy, the k in
    # k-epsilon) with its own adapter — a ½mv² example on a TKE topic would be verified-but-irrelevant.
    aliases=["kinetic energy"], not_aliases=["turbulent", "turbulence", "tke"], priority=96,
    problem_template="A body of mass m = {m} kg moves at v = {v} m/s. Find its kinetic energy.",
    givens=[Given("m", "kg", 1, 20), Given("v", "m/s", 1, 15)],
    outputs=[Output("KE", "KE = (m*v^2)/2", "(m*v**2)/2", "J", "compute_kinetic_energy", "kinetic energy")],
    conventions={"units": "SI (kg, m/s, J)"},
    canonical_latex="KE = \\frac{1}{2}mv^2",
    canonical_notes=[
        "\\(m\\): mass (kg).  \\(v\\): speed (m/s).  Kinetic energy is measured in joules (J).",
        "Energy grows with the SQUARE of speed — doubling \\(v\\) quadruples \\(KE\\).",
    ],
    edge_cases=[
        "Kinetic energy is never negative; it is 0 only when the body is at rest (\\(v = 0\\)).",
        "It depends on speed, not direction — the sign of the velocity does not matter.",
    ])

NEWTONS_SECOND_LAW = FormulaSpec(
    slug="newtons_second_law", title="Newton's second law", family="physics",
    aliases=["newton's second law", "newtons second law", "net force", "f = ma"], priority=78,
    problem_template="A mass m = {m} kg accelerates at a = {a} m/s^2. Find the net force on it.",
    givens=[Given("m", "kg", 1, 20), Given("a", "m/s^2", 1, 15)],
    outputs=[Output("F", "F = m*a", "m*a", "N", "compute_force", "net force")],
    conventions={"law": "F = m*a", "units": "SI (kg, m/s^2, N)"},
    canonical_latex="F = ma",
    canonical_notes=[
        "\\(F\\): net force (N).  \\(m\\): mass (kg).  \\(a\\): acceleration (m/s²).",
        "Force and acceleration point in the SAME direction; a larger mass needs more force for the same "
        "acceleration.",
    ],
    edge_cases=[
        "Zero net force → zero acceleration: the body keeps a constant velocity (Newton's first law).",
        "\\(F\\) is the NET force — add all the forces (as vectors) first.",
    ])

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
    conventions={"units": "SI (kg, m/s, kg*m/s)"},
    canonical_latex="p = mv",
    canonical_notes=[
        "\\(p\\): momentum.  \\(m\\): mass.  \\(v\\): velocity.  Momentum is a VECTOR — direction matters.",
        "Units: kg·m/s.",
    ],
    edge_cases=[
        "Momentum is 0 at rest (\\(v = 0\\)).",
        "In an isolated system the TOTAL momentum is conserved — internal forces cannot change it.",
    ])

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
# Live gap: a "fluid turbulence" science_mechanism path shipped an essay-shaped LLM "worked example" (steps
# = "identify conditions… provide examples… summarize key points") — no problem, no values, nothing computed.
def _reynolds_interpretation(env: dict) -> str | None:
    """What the computed Re MEANS (science plan §8): the regime classification the number exists to make.
    Thresholds are the conventional internal-pipe-flow values; instance_ok keeps generated examples away from
    the 2000-4500 boundary band, so the transitional wording is a defensive fallback only."""
    try:
        re_v = float(env.get("Re"))
    except (TypeError, ValueError):
        return None
    if re_v < 2300:
        band = "below the ~2300 threshold, so this pipe flow is in the laminar regime"
    elif re_v <= 4000:
        band = "in the ~2300-4000 transitional band, so the regime is uncertain"
    else:
        band = "above the ~4000 threshold, so this pipe flow is in the turbulent regime"
    return (f"Re ≈ {re_v:g} is {band} (conventional thresholds for fully developed internal pipe "
            "flow; they are approximate and depend on disturbances and geometry).")


# The quantitative core of turbulence onset IS the Reynolds number; routing turbulence-titled topics here gives
# them a real, verified calculation. Oil framing keeps every value a clean 1-dp SI number (water's mu=0.001
# doesn't fit the 1-dp float sampler), and the ranges genuinely span laminar -> turbulent.
REYNOLDS_NUMBER = FormulaSpec(
    slug="reynolds_number", title="Reynolds number and flow regime", family="physics",
    # Keep routing narrower than the parent subject. Bare "turbulence" aliases caused energy-cascade and
    # real-world-application topics to receive this pipe-flow calculation and canonical identity.
    aliases=["reynolds number", "reynolds", "laminar and turbulent", "laminar or turbulent",
             "laminar vs turbulent",
             "flow regime", "flow regimes", "flow classification"],
    # TURBULENCE MODELING topics (k-epsilon, LES, RANS closures) must NOT route here: a 'Turbulence Models'
    # topic (scope: k-epsilon, LES) shipped a VERIFIED-but-IRRELEVANT Re calculation — worse than unverified,
    # because the verification badge lends trust to an example that does not teach the topic's declared scope.
    # Blocked, the topic stamps withhold_fabricated and ships honestly qualitative. (This also fixes canonical
    # identity: _canonical_concept_key consults routing first, so these topics were being IDENTIFIED as
    # reynolds_number.)
    not_aliases=["turbulence model", "turbulence models", "turbulence modeling", "turbulence modelling",
                 "models of turbulence", "modeling of turbulence", "modelling of turbulence",
                 "k-epsilon", "k epsilon", "large eddy", "les", "rans", "reynolds stress", "closure"],
    priority=95,
    problem_template=("Oil of density {rho} kg/m^3 and viscosity {mu} Pa*s flows at {v} m/s through a pipe "
                      "of diameter {D} m. Compute the Reynolds number for the flow."),
    givens=[Given("rho", "kg/m^3", 850, 950),
            Given("v", "m/s", 1, 6, integer=False),
            Given("D", "m", 0, 1, integer=False),
            Given("mu", "Pa*s", 0, 1, integer=False)],
    outputs=[Output("Re", "Re = rho*v*D/mu", "rho*v*D/mu", "", "compute_reynolds_number", "Reynolds number")],
    conventions={"formula": "Re = rho*v*D/mu", "units": "SI (kg/m^3, m/s, m, Pa*s); Re is dimensionless",
                 "regimes": "pipe flow: Re < 2300 laminar, 2300-4000 transitional, > 4000 turbulent"},
    canonical_latex="Re = \\frac{\\rho v D}{\\mu}",
    canonical_notes=[
        "\\(\\rho\\): fluid density.  \\(v\\): flow speed.  \\(D\\): pipe diameter.  \\(\\mu\\): dynamic "
        "viscosity.  \\(Re\\) is dimensionless.",
        # WHY the ratio means something (reviewer gap: the lesson taught substitution, not meaning) —
        # the numerator scales the inertial effects, the denominator the viscous ones.
        "What it compares: \\(\\rho v D\\) scales the INERTIAL effects (a fast, dense flow keeps pushing "
        "ahead) and \\(\\mu\\) the VISCOUS effects (internal friction that smooths disturbances out). A "
        "large \\(Re\\) means inertia dominates, so small disturbances can grow instead of being damped — "
        "which is why high \\(Re\\) favors turbulence, all else equal.",
        "\\(D\\) is the CHARACTERISTIC LENGTH of the geometry — the pipe diameter here; other geometries "
        "use their own length scale, so thresholds are geometry-specific.",
        "Pipe-flow regimes: \\(Re < 2300\\) laminar, \\(2300\\)–\\(4000\\) transitional, \\(Re > 4000\\) "
        "turbulent — high speed, large diameter, or low viscosity push the flow toward turbulence.",
    ],
    edge_cases=[
        "As \\(\\mu\\) grows (thicker fluid), \\(Re\\) falls — a very viscous flow tends to stay laminar at "
        "speeds that would make a thin fluid turbulent (all else equal; geometry and the other scales still "
        "matter).",
        "\\(Re\\) scales linearly with each of \\(\\rho\\), \\(v\\), \\(D\\): doubling the pipe diameter "
        "doubles \\(Re\\), all else held equal.",
    ],
    # Reject degenerate instances: a zero-ish diameter/viscosity from the 1-dp sampler, or a Reynolds number
    # so close to a regime boundary that the classification reads ambiguous to a learner.
    instance_ok=lambda g: (g["D"] >= 0.2 and g["mu"] >= 0.2
                           and not (2000 <= g["rho"] * g["v"] * g["D"] / g["mu"] <= 4500)),
    interpret=_reynolds_interpretation,
)

# Live gap: a 'Navier-Stokes Equations' science_mechanism topic shipped an unverified essay-WE opening with
# raw PDE notation (∂u/∂t + u·∇u = −∇P/ρ + ν∇²u) — "Demonstrate the implications…", nothing computable. The
# N-S equations' SIMPLEST EXACT SOLUTION is computable: laminar pipe pressure drop ΔP = 32 μ L v / D²
# (Hagen–Poiseuille form). Routing N-S titles here replaces the essay with a real, verified calculation the
# notes honestly frame as "N-S solved in its simplest case".
LAMINAR_PRESSURE_DROP = FormulaSpec(
    slug="laminar_pressure_drop", title="Laminar pipe pressure drop (Navier-Stokes exact solution)",
    family="physics",
    aliases=["navier-stokes", "navier stokes", "hagen-poiseuille", "hagen poiseuille", "poiseuille",
             "laminar pipe flow", "pipe pressure drop"],
    priority=95,
    problem_template=("Oil of viscosity {mu} Pa*s flows at an average speed of {v} m/s through a straight "
                      "pipe {L} m long with diameter {D} m. Compute the pressure drop across the pipe for "
                      "laminar flow."),
    givens=[Given("mu", "Pa*s", 0, 1, integer=False),
            Given("L", "m", 2, 9),
            Given("v", "m/s", 1, 3, integer=False),
            Given("D", "m", 0, 1, integer=False)],
    outputs=[Output("dP", "dP = 32*mu*L*v/D^2", "32*mu*L*v/(D*D)", "Pa", "compute_pressure_drop",
                    "pressure drop")],
    conventions={"formula": "dP = 32*mu*L*v/D^2 (laminar pipe flow)",
                 "units": "SI (Pa*s, m, m/s, Pa)",
                 "origin": "the Navier-Stokes equations solved exactly for steady laminar flow in a pipe"},
    canonical_latex="\\Delta P = \\frac{32\\,\\mu L v}{D^2}",
    canonical_notes=[
        "\\(\\mu\\): dynamic viscosity.  \\(L\\): pipe length.  \\(v\\): average flow speed.  \\(D\\): pipe "
        "diameter.  \\(\\Delta P\\): pressure lost to viscous friction.",
        "This is the Navier–Stokes equations solved EXACTLY in their simplest case — steady, laminar flow in "
        "a straight pipe (the Hagen–Poiseuille result). Turbulent flow has no such closed solution.",
        "Assumptions (all required): steady, incompressible, Newtonian fluid, fully developed laminar flow, "
        "straight circular pipe.",
    ],
    edge_cases=[
        "At FIXED average speed \\(v\\), halving the diameter QUADRUPLES the pressure drop "
        "(\\(\\Delta P \\propto 1/D^2\\)); at fixed volumetric FLOW RATE the dependence is even steeper "
        "(\\(\\Delta P \\propto 1/D^4\\)) — narrow pipes are expensive to pump through.",
        "The formula holds only for LAMINAR flow; past the turbulent transition the drop grows faster than "
        "linearly with speed.",
    ],
    instance_ok=lambda g: g["D"] >= 0.2 and g["mu"] >= 0.2,
)

# Turbulence-MODELING topics (k-epsilon, RANS) get a RELEVANT verified example: turbulent kinetic energy
# k = ½(u'² + v'² + w'²) is literally the "k" the k-epsilon model transports, computed from the velocity
# fluctuations — the exact fluctuations→energy connection an external review flagged as missing. (These
# topics are not_aliased away from reynolds_number, whose calculation was verified-but-irrelevant for them;
# LES/DNS-specific topics stay unrouted → withhold, since a TKE calc doesn't demonstrate filtering/resolution.)
TURBULENT_KINETIC_ENERGY = FormulaSpec(
    slug="turbulent_kinetic_energy", title="Turbulent kinetic energy (the k in k-epsilon)", family="physics",
    aliases=["turbulent kinetic energy", "tke", "turbulence model", "turbulence models",
             "turbulence modeling", "turbulence modelling", "k-epsilon", "k epsilon",
             "turbulence energy", "models of turbulence", "modeling of turbulence",
             "modelling of turbulence"],
    priority=96,
    problem_template=("At a point in a turbulent flow, the measured velocity FLUCTUATIONS about the mean are "
                      "u' = {up} m/s, v' = {vp} m/s and w' = {wp} m/s. Compute the turbulent kinetic energy "
                      "per unit mass."),
    givens=[Given("up", "m/s", 0, 3, integer=False),
            Given("vp", "m/s", 0, 3, integer=False),
            Given("wp", "m/s", 0, 3, integer=False)],
    outputs=[Output("k", "k = (up^2 + vp^2 + wp^2)/2", "(up*up + vp*vp + wp*wp)/2", "m^2/s^2",
                    "compute_turbulent_kinetic_energy", "turbulent kinetic energy")],
    conventions={"formula": "k = (u'^2 + v'^2 + w'^2)/2",
                 "units": "SI (m/s for fluctuations; k in m^2/s^2 = J/kg)",
                 "meaning": "k measures the energy carried by the velocity fluctuations about the mean flow"},
    canonical_latex="k = \\tfrac{1}{2}\\left(\\overline{u'^2} + \\overline{v'^2} + \\overline{w'^2}\\right)",
    canonical_notes=[
        "\\(u', v', w'\\): velocity FLUCTUATIONS about the mean flow (Reynolds decomposition: instantaneous "
        "velocity = mean + fluctuation).  \\(k\\): turbulent kinetic energy per unit mass (J/kg).",
        "This \\(k\\) is one of the two variables the \\(k\\)-\\(\\epsilon\\) model transports — the model "
        "solves equations for \\(k\\) (how much fluctuation energy exists) and \\(\\epsilon\\) (how fast it "
        "dissipates to heat).",
    ],
    edge_cases=[
        "In laminar flow the fluctuations vanish, so \\(k = 0\\) — turbulence models have nothing to model.",
        "\\(k\\) weighs each direction's fluctuation by its SQUARE: one strong fluctuating component "
        "dominates two weak ones.",
    ],
    instance_ok=lambda g: (g["up"] + g["vp"] + g["wp"]) >= 1.0 and len({g["up"], g["vp"], g["wp"]}) >= 2,
)

OHMS_LAW = FormulaSpec(
    slug="ohms_law", title="Ohm's law with power", family="physics",
    aliases=["ohm's law", "ohms law", "ohm law"], priority=95,
    problem_template="A resistor R = {R} ohm has V = {V} V across it. Find the current and the power dissipated.",
    givens=[Given("V", "V", 2, 24), Given("R", "ohm", 1, 12)],
    outputs=[Output("I", "I = V/R", "V/R", "A", "compute_current", "current"),
             Output("P", "P = V*I", "V*(V/R)", "W", "compute_power", "power dissipated")],
    conventions={"law": "Ohm's law V = I*R", "units": "SI (V, A, ohm, W)"},
    canonical_latex="I = \\frac{V}{R}",
    canonical_notes=[
        "\\(V\\): voltage across the resistor.  \\(R\\): resistance.  \\(I\\): current through it.",
        "Power dissipated: \\(P = VI\\).",
    ],
    edge_cases=[
        "As \\(R \\to 0\\) (a short circuit) the current grows without bound; \\(I\\) is undefined at \\(R = 0\\).",
        "Zero voltage → zero current.",
    ])

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
    conventions={"model": "simple interest (not compounded)", "units": "dollars, percent per year"},
    canonical_latex="I = \\frac{P r t}{100}",
    canonical_notes=[
        "\\(P\\): principal.  \\(r\\): annual rate (percent).  \\(t\\): time in years.",
        "Interest is charged on the ORIGINAL principal only; the final amount is \\(A = P + I\\).",
    ],
    edge_cases=[
        "Simple interest grows LINEARLY with time — unlike compound interest, earlier interest never itself "
        "earns interest.",
    ])

COMPOUND_INTEREST = FormulaSpec(
    slug="compound_interest", title="compound interest (annual)", family="finance",
    aliases=["compound interest"], priority=94,
    problem_template="A principal P = ${P} is invested at r = {r}% compounded annually for t = {t} years. "
                     "Find the final amount.",
    givens=[Given("P", "$", 100, 5000), Given("r", "%", 1, 12), Given("t", "yr", 1, 8)],
    outputs=[Output("A", "A = P*(1 + r/100)^t", "P*(1 + r/100)**t", "$", "compute_amount", "final amount")],
    conventions={"model": "annual compounding", "units": "dollars, percent per year"},
    canonical_latex="A = P(1 + \\frac{r}{100})^t",
    canonical_notes=[
        "\\(P\\): principal.  \\(r\\): annual rate (percent).  \\(t\\): number of years.  Compounds once per year.",
        "Each year's interest is added to the balance and then itself earns interest.",
    ],
    edge_cases=[
        "Compound interest grows FASTER than simple interest (exponential vs linear); at \\(r = 0\\) the amount "
        "stays at \\(P\\).",
    ])

PRESENT_VALUE = FormulaSpec(
    slug="present_value", title="present value (discounting)", family="finance",
    aliases=["present value", "discounted value"], priority=72,
    problem_template="A future amount FV = ${FV} is due in t = {t} years at a discount rate r = {r}%. "
                     "Find its present value.",
    givens=[Given("FV", "$", 100, 5000), Given("r", "%", 1, 12), Given("t", "yr", 1, 8)],
    outputs=[Output("PV", "PV = FV/(1 + r/100)^t", "FV/(1 + r/100)**t", "$", "compute_present_value",
                    "present value")],
    conventions={"model": "annual discounting", "units": "dollars, percent per year"})

NPV_THREE_PERIOD = FormulaSpec(
    slug="net_present_value", title="net present value of a 3-year cash flow", family="finance",
    # priority must beat present_value (72): "net present value" contains "present value" as a substring, so
    # both rules match that phrase — the higher-priority rule wins, and NPV (the more specific match) must.
    aliases=["net present value", "npv", "npv of a project"], priority=73,
    problem_template="A project costs an initial investment of ${initial} and returns cash flows of "
                     "${cf1}, ${cf2}, ${cf3} at the end of years 1, 2, and 3. At a discount rate of "
                     "r = {r}%, find the net present value (NPV).",
    givens=[Given("initial", "$", 100, 1000), Given("cf1", "$", 50, 500), Given("cf2", "$", 50, 500),
            Given("cf3", "$", 50, 500), Given("r", "%", 1, 15)],
    outputs=[Output(
        "npv", "NPV = cf1/(1+r/100) + cf2/(1+r/100)^2 + cf3/(1+r/100)^3 - initial",
        "cf1/(1+r/100) + cf2/(1+r/100)**2 + cf3/(1+r/100)**3 - initial",
        "$", "compute_npv", "net present value")],
    conventions={"model": "each cash flow discounted back to year 0 individually, then summed"},
    canonical_latex="NPV = \\sum_{t=1}^{3} \\frac{CF_t}{(1+r)^t} - C_0",
    canonical_notes=[
        "Each future cash flow is discounted separately by how many years away it is (year-1 cash flow "
        "divided once, year-3 cash flow divided three times), then the initial investment is subtracted.",
    ],
    edge_cases=[
        "NPV = 0 means the project's discounted returns exactly cover the initial investment — the break-even "
        "case. NPV < 0 means the project destroys value at that discount rate.",
    ])

DISCOUNT_FACTOR = FormulaSpec(
    slug="discount_factor", title="discount factor for a future cash flow", family="finance",
    aliases=["discount factor", "compute the discount factor"], priority=51,
    problem_template="Find the discount factor for a cash flow t = {t} years from now at discount rate "
                     "r = {r}%.",
    givens=[Given("r", "%", 1, 15), Given("t", "yr", 1, 10)],
    outputs=[Output("df", "DF = 1/(1 + r/100)^t", "1/(1 + r/100)**t", "", "compute_discount_factor",
                    "discount factor")],
    conventions={"definition": "the multiplier that converts a future cash flow into today's dollars"},
    canonical_latex="DF = \\frac{1}{(1+r)^t}",
    canonical_notes=[
        "Multiplying any future cash flow by this discount factor converts it to its present value — this is "
        "exactly the factor present_value applies to a single cash flow.",
    ],
    edge_cases=[
        "The discount factor is always between 0 and 1 for a positive rate — money in the future is always "
        "worth LESS than the same amount today.",
    ])

CAPM_EXPECTED_RETURN = FormulaSpec(
    slug="capm_expected_return", title="expected return via the Capital Asset Pricing Model (CAPM)",
    family="finance",
    aliases=["capm", "capital asset pricing model", "capm expected return"], priority=52,
    problem_template="A stock has beta = {beta}, the risk-free rate is rf = {rf}%, and the expected market "
                     "return is rm = {rm}%. Find the expected return using CAPM.",
    givens=[Given("beta", "", 0.5, 2.0, integer=False), Given("rf", "%", 1, 5, integer=False),
            Given("rm", "%", 6, 14, integer=False)],
    outputs=[Output("re", "re = rf + beta*(rm - rf)", "rf + beta*(rm - rf)", "%", "compute_capm",
                    "expected return")],
    conventions={"definition": "expected return = risk-free rate + beta x (market return - risk-free rate)"},
    canonical_latex="E[R] = R_f + \\beta(R_m - R_f)",
    canonical_notes=[
        "\\(\\beta\\) measures how much the stock moves relative to the market: \\(\\beta = 1\\) means it "
        "moves with the market, \\(\\beta > 1\\) means it amplifies market moves, \\(\\beta < 1\\) means it "
        "dampens them.",
    ],
    edge_cases=[
        "If \\(\\beta = 0\\), CAPM gives expected return = risk-free rate — a beta-zero asset is (by this "
        "model) uncorrelated with the market and earns no risk premium.",
    ])

PORTFOLIO_RETURN_TWO_ASSET = FormulaSpec(
    slug="portfolio_return_two_asset", title="expected return of a two-asset portfolio", family="finance",
    aliases=["portfolio return", "two asset portfolio return", "expected portfolio return"], priority=51,
    problem_template="A portfolio puts w1 = {w1}% of its value in an asset with expected return r1 = {r1}%, "
                     "and the rest in an asset with expected return r2 = {r2}%. Find the portfolio's "
                     "expected return.",
    givens=[Given("w1", "%", 10, 90), Given("r1", "%", 1, 15, integer=False),
            Given("r2", "%", 1, 15, integer=False)],
    outputs=[Output("rp", "rp = (w1/100)*r1 + (1 - w1/100)*r2", "(w1/100)*r1 + (1 - w1/100)*r2", "%",
                    "compute_portfolio_return", "portfolio expected return")],
    conventions={"definition": "portfolio return = weight-1 x return-1 + weight-2 x return-2"},
    canonical_latex="R_p = w_1 R_1 + w_2 R_2,\\quad w_2 = 1-w_1",
    canonical_notes=[
        "The two weights must sum to 100% of the portfolio — the second asset automatically gets whatever "
        "share the first one doesn't.",
    ],
    edge_cases=[
        "At \\(w_1 = 100\\%\\), the portfolio return equals \\(r_1\\) exactly — the second asset is not held "
        "at all.",
    ])

FORWARD_PRICE = FormulaSpec(
    slug="forward_price", title="forward price under continuous compounding", family="finance",
    aliases=["forward price", "forward contract price", "forward price continuous compounding"],
    priority=52,
    problem_template="A non-dividend-paying asset has spot price S = ${S}, the continuously compounded "
                     "risk-free rate is r = {r}%, and the forward contract matures in T = {T} years. Find "
                     "the forward price.",
    givens=[Given("S", "$", 20, 500), Given("r", "%", 1, 10, integer=False), Given("T", "yr", 1, 5)],
    outputs=[Output("F", "F = S * e^(r/100 * T)", "S * exp(r/100 * T)", "$", "compute_forward_price",
                    "forward price")],
    conventions={"model": "no-arbitrage pricing under continuous compounding, no dividends or storage costs"},
    canonical_latex="F = S_0 e^{rT}",
    canonical_notes=[
        "This is the NO-ARBITRAGE price: if the actual forward price differed, a trader could lock in a "
        "riskless profit by borrowing/lending at rate r and trading the spot asset against the forward.",
    ],
    edge_cases=[
        "As T approaches 0 (the contract is about to expire), the forward price converges to the spot price "
        "S — there is no time left for the interest-rate effect to matter.",
    ])

OPTION_PAYOFF_CALL = FormulaSpec(
    slug="option_payoff_call", title="payoff of a European call option at expiration", family="finance",
    aliases=["option payoff", "call option payoff", "payoff of a call option"],
    not_aliases=["put option"],
    priority=52,
    problem_template="At expiration, the underlying stock price is S = ${S} and the call option's strike "
                     "price is K = ${K}. Find the option's payoff.",
    givens=[Given("S", "$", 10, 200), Given("K", "$", 10, 200)],
    outputs=[Output("payoff", "payoff = max(S - K, 0)", "max(S - K, 0)", "$", "compute_call_payoff",
                    "call option payoff")],
    conventions={"definition": "a call option is exercised only if it is profitable to do so"},
    canonical_latex="\\text{Payoff} = \\max(S - K,\\ 0)",
    canonical_notes=[
        "If \\(S > K\\), exercising the call and immediately selling at the market price nets \\(S - K\\); "
        "if \\(S \\le K\\), the holder simply lets the option expire worthless rather than buy above market "
        "price — the payoff can never be negative.",
    ],
    edge_cases=[
        "At \\(S = K\\) exactly (\"at the money\"), the payoff is 0 — exercising is not profitable, but it "
        "isn't a loss either.",
    ])

SHARPE_RATIO = FormulaSpec(
    slug="sharpe_ratio", title="Sharpe ratio of a portfolio", family="finance",
    aliases=["sharpe ratio", "compute the sharpe ratio"], priority=52,
    problem_template="A portfolio has an expected return of rp = {rp}%, the risk-free rate is rf = {rf}%, "
                     "and the portfolio's standard deviation of returns is sigma = {sigma}%. Find the "
                     "Sharpe ratio.",
    givens=[Given("rp", "%", 2, 20, integer=False), Given("rf", "%", 1, 5, integer=False),
            Given("sigma", "%", 2, 25, integer=False)],
    outputs=[Output("sharpe", "sharpe = (rp - rf) / sigma", "(rp - rf) / sigma", "", "compute_sharpe_ratio",
                    "Sharpe ratio")],
    conventions={"definition": "excess return per unit of risk (standard deviation)"},
    canonical_latex="S = \\frac{R_p - R_f}{\\sigma_p}",
    canonical_notes=[
        "The numerator is the EXCESS return — how much the portfolio earned above the risk-free rate — "
        "divided by how volatile that return was. A higher Sharpe ratio means more return per unit of risk "
        "taken.",
    ],
    edge_cases=[
        "If the portfolio's expected return equals the risk-free rate exactly, the Sharpe ratio is 0 — no "
        "reward is being earned for the risk taken.",
    ])

PERCENT_CHANGE = FormulaSpec(
    slug="percent_change", title="percent change", family="finance",
    aliases=["percent change", "percentage change"], priority=71,
    problem_template="A quantity changes from old = {old} to new = {new}. Find the percent change.",
    givens=[Given("old", "", 10, 200), Given("new", "", 10, 200)],
    outputs=[Output("pct", "pct = (new - old)/old * 100", "(new - old)/old * 100", "%", "compute_percent_change",
                    "percent change")],
    conventions={"definition": "percent change = (new - old) / old * 100"},
    canonical_latex="\\frac{new - old}{old} \\times 100",
    canonical_notes=[
        "\\(old\\): the starting value.  \\(new\\): the ending value.",
        "A positive result is an increase; a negative result is a decrease.",
    ],
    edge_cases=[
        "Undefined when \\(old = 0\\) (division by zero — there is no baseline to compare against).",
    ])

# ======================================================================================================
# GEOMETRY (B2) — family "geometry"
# ======================================================================================================
CIRCLE_AREA = FormulaSpec(
    slug="circle_area", title="area of a circle", family="geometry",
    aliases=["area of a circle", "circle area"], priority=69,
    problem_template="A circle has radius r = {r}. Find its area.",
    givens=[Given("r", "", 1, 20)],
    outputs=[Output("A", "A = pi*r^2", "pi*r**2", "sq units", "compute_area", "area")],
    conventions={"units": "square units", "pi": "3.14159..."},
    canonical_latex="A = \\pi r^2",
    canonical_notes=["\\(r\\): the radius.  Area is in square units."],
    edge_cases=["Doubling the radius QUADRUPLES the area (it scales with \\(r^2\\))."])

CIRCLE_CIRCUMFERENCE = FormulaSpec(
    slug="circle_circumference", title="circumference of a circle", family="geometry",
    aliases=["circumference"], priority=68,
    problem_template="A circle has radius r = {r}. Find its circumference.",
    givens=[Given("r", "", 1, 20)],
    outputs=[Output("C", "C = 2*pi*r", "2*pi*r", "units", "compute_circumference", "circumference")],
    conventions={"pi": "3.14159..."},
    canonical_latex="C = 2\\pi r",
    canonical_notes=["\\(r\\): the radius.  Since the diameter is \\(d = 2r\\), this is equivalently \\(C = \\pi d\\)."],
    edge_cases=["Circumference grows LINEARLY with the radius — doubling \\(r\\) doubles \\(C\\)."])

RECTANGLE_AREA = FormulaSpec(
    slug="rectangle_area", title="area of a rectangle", family="geometry",
    aliases=["area of a rectangle", "rectangle area"], priority=67,
    problem_template="A rectangle is l = {l} by w = {w}. Find its area.",
    givens=[Given("l", "", 1, 30), Given("w", "", 1, 30)],
    outputs=[Output("A", "A = l*w", "l*w", "sq units", "compute_area", "area")],
    conventions={"units": "square units"},
    canonical_latex="A = lw",
    canonical_notes=["\\(l\\): length.  \\(w\\): width."],
    edge_cases=["A square is the special case \\(l = w\\), giving \\(A = l^2\\)."])

TRIANGLE_AREA = FormulaSpec(
    slug="triangle_area", title="area of a triangle", family="geometry",
    aliases=["area of a triangle", "triangle area"], priority=66,
    problem_template="A triangle has base b = {b} and height h = {h}. Find its area.",
    givens=[Given("b", "", 1, 30), Given("h", "", 1, 30)],
    outputs=[Output("A", "A = (b*h)/2", "(b*h)/2", "sq units", "compute_area", "area")],
    conventions={"units": "square units"},
    canonical_latex="A = \\frac{1}{2}bh",
    canonical_notes=["\\(b\\): the base.  \\(h\\): the height PERPENDICULAR to that base."],
    edge_cases=["\\(h\\) must be the perpendicular height, not a slanted side."])

PYTHAGOREAN = FormulaSpec(
    slug="pythagorean", title="Pythagorean theorem", family="geometry",
    aliases=["pythagorean", "hypotenuse"], priority=65,
    problem_template="A right triangle has legs a = {a} and b = {b}. Find the hypotenuse.",
    givens=[Given("a", "", 1, 20), Given("b", "", 1, 20)],
    outputs=[Output("c", "c = sqrt(a^2 + b^2)", "sqrt(a**2 + b**2)", "", "compute_hypotenuse", "hypotenuse")],
    conventions={"theorem": "a^2 + b^2 = c^2"},
    canonical_latex="c = \\sqrt{a^2 + b^2}",
    canonical_notes=[
        "\\(a\\), \\(b\\): the two legs (the sides meeting at the right angle).  \\(c\\): the hypotenuse.",
        "Equivalently, \\(a^2 + b^2 = c^2\\).",
    ],
    edge_cases=[
        "Applies ONLY to right triangles.",
        "The hypotenuse is always the longest side, so \\(c > a\\) and \\(c > b\\).",
    ])

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
    conventions={"definition": "molarity = moles of solute per litre of solution"},
    canonical_latex="M = \\frac{n}{V}",
    canonical_notes=["\\(n\\): moles of solute.  \\(V\\): volume of SOLUTION in litres.  \\(M\\): molarity (mol/L)."],
    edge_cases=["Use the total solution volume, not just the volume of solvent."])

DENSITY = FormulaSpec(
    slug="density", title="density from mass and volume", family="chemistry",
    aliases=["density"], priority=91,
    problem_template="A sample has mass m = {m} g and volume V = {V} mL. Find its density.",
    givens=[Given("m", "g", 5, 500), Given("V", "mL", 1, 50)],
    outputs=[Output("rho", "rho = m/V", "m/V", "g/mL", "compute_density", "density")],
    conventions={"definition": "density = mass per unit volume"},
    canonical_latex="\\rho = \\frac{m}{V}",
    canonical_notes=["\\(m\\): mass.  \\(V\\): volume.  \\(\\rho\\): density (e.g. g/mL)."],
    edge_cases=["Density is an INTENSIVE property — it does not change with the amount of material."])

IDEAL_GAS_PRESSURE = FormulaSpec(
    slug="ideal_gas_pressure", title="ideal gas law (solve for pressure)", family="chemistry",
    aliases=["ideal gas", "gas law"], not_aliases=["combined"], priority=62, constants={"R": 0.0821},
    problem_template="n = {n} mol of an ideal gas occupies V = {V} L at T = {T} K. Find the pressure "
                     "(R = 0.0821 L*atm/mol/K).",
    givens=[Given("n", "mol", 1, 10), Given("T", "K", 200, 500), Given("V", "L", 1, 20)],
    outputs=[Output("P", "P = n*R*T/V", "n*R*T/V", "atm", "compute_pressure", "pressure")],
    conventions={"law": "PV = nRT", "R": "0.0821 L*atm/mol/K"},
    canonical_latex="P = \\frac{nRT}{V}",
    canonical_notes=[
        "\\(n\\): moles.  \\(R\\): gas constant (0.0821 L·atm/mol/K).  \\(T\\): temperature in KELVIN.  \\(V\\): volume.",
        "This is \\(PV = nRT\\) solved for pressure.",
    ],
    edge_cases=[
        "\\(T\\) must be in KELVIN, not Celsius.",
        "The IDEAL gas law is an approximation — best at low pressure and high temperature.",
    ])

DILUTION = FormulaSpec(
    slug="dilution", title="dilution (M1V1 = M2V2)", family="chemistry",
    aliases=["dilution", "dilute"], priority=61,
    problem_template="A stock solution M1 = {M1} mol/L, V1 = {V1} mL is diluted to V2 = {V2} mL. "
                     "Find the new concentration.",
    givens=[Given("M1", "mol/L", 1, 10), Given("V1", "mL", 1, 10), Given("V2", "mL", 20, 100)],
    outputs=[Output("M2", "M2 = M1*V1/V2", "M1*V1/V2", "mol/L", "compute_concentration", "diluted concentration")],
    conventions={"law": "M1*V1 = M2*V2"},
    canonical_latex="M_2 = \\frac{M_1 V_1}{V_2}",
    canonical_notes=[
        "\\(M_1, V_1\\): the stock concentration and volume.  \\(V_2\\): the final (diluted) volume.",
        "Comes from \\(M_1 V_1 = M_2 V_2\\) — the moles of solute do not change on dilution.",
    ],
    edge_cases=["Diluting means \\(V_2 > V_1\\), so the concentration drops (\\(M_2 < M_1\\))."])

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

CORRELATION = FormulaSpec(
    slug="correlation_coefficient", title="Pearson correlation coefficient of two datasets",
    family="statistics",
    aliases=["correlation coefficient", "pearson correlation", "correlation of two datasets",
             "find the correlation"],
    priority=85,
    problem_template="For paired data xs = {xs} and ys = {ys}, find the (population) Pearson correlation "
                     "coefficient.",
    givens=[], dataset=Dataset("xs", size_lo=4, size_hi=6, val_lo=1, val_hi=15),
    dataset2=Dataset("ys", size_lo=4, size_hi=6, val_lo=1, val_hi=15),
    outputs=[
        Output("mean_x", "mean_x = (sum of xs)/n", "sum(xs)/n", "", "compute_mean_x", "mean of xs",
               show=[("sum of xs", "sum(xs)"), ("n", "n")]),
        Output("mean_y", "mean_y = (sum of ys)/n", "sum(ys)/n", "", "compute_mean_y", "mean of ys",
               show=[("sum of ys", "sum(ys)"), ("n", "n")]),
        Output("std_x", "std_x = sqrt((sum of squared deviations of xs)/n)",
               "sqrt(sum((x-mean_x)**2 for x in xs)/n)", "", "compute_std_x", "standard deviation of xs"),
        Output("std_y", "std_y = sqrt((sum of squared deviations of ys)/n)",
               "sqrt(sum((y-mean_y)**2 for y in ys)/n)", "", "compute_std_y", "standard deviation of ys"),
        Output("r", "r = (covariance of xs, ys) / (std_x * std_y)",
               "(sum((x-mean_x)*(y-mean_y) for x, y in zip(xs, ys))/n) / (std_x * std_y)",
               "", "compute_correlation", "correlation coefficient",
               show=[("covariance of xs, ys", "sum((x-mean_x)*(y-mean_y) for x, y in zip(xs, ys))/n")])],
    conventions={"model": "population correlation (divide by n, not n-1)",
                 "definition": "r = covariance(x,y) / (std_dev(x) * std_dev(y))"},
    canonical_latex="r = \\frac{\\text{cov}(x,y)}{\\sigma_x \\sigma_y}",
    canonical_notes=[
        "The correlation coefficient normalizes the covariance by both standard deviations, so \\(r\\) is "
        "always between \\(-1\\) and \\(1\\) regardless of the data's original units.",
        "\\(r = 1\\) means a perfect increasing linear relationship; \\(r = -1\\) means a perfect decreasing "
        "one; \\(r = 0\\) means no linear relationship (there could still be a nonlinear one).",
    ],
    edge_cases=[
        "If either dataset has zero variance (every value is identical), \\(r\\) is undefined — there is "
        "nothing to correlate against a constant.",
    ])

BINOMIAL_PROBABILITY = FormulaSpec(
    slug="binomial_probability", title="binomial probability P(X = k)", family="statistics",
    aliases=["binomial probability", "binomial distribution probability", "probability of exactly k successes"],
    priority=54,
    problem_template="A binomial experiment has n = {n} independent trials, each with success probability "
                     "p = {p}. Find the probability of exactly k = {k} successes.",
    givens=[Given("n", "", 5, 12), Given("k", "", 1, 5), Given("p", "", 0.1, 0.9, integer=False)],
    outputs=[Output(
        "prob", "P(X=k) = (n! / (k!(n-k)!)) * p^k * (1-p)^(n-k)",
        "(factorial(n) / (factorial(k) * factorial(n-k))) * p**k * (1-p)**(n-k)",
        "", "compute_binomial_probability", "probability of exactly k successes")],
    conventions={"formula": "P(X=k) = C(n,k) * p^k * (1-p)^(n-k)",
                 "assumptions": "n independent trials, each with the SAME success probability p"},
    canonical_latex="P(X=k) = \\binom{n}{k} p^k (1-p)^{n-k}",
    canonical_notes=[
        "\\(\\binom{n}{k} = \\frac{n!}{k!(n-k)!}\\) counts how many different orderings of k successes among "
        "n trials are possible; each such ordering has the same probability \\(p^k(1-p)^{n-k}\\).",
    ],
    edge_cases=[
        "Requires \\(k \\le n\\) — you cannot have more successes than trials.",
        "If \\(p = 0\\), the only possible outcome is k = 0 successes; if \\(p = 1\\), the only possible "
        "outcome is k = n successes.",
    ])

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

# Standardizing a value USING a dataset (vs Z_SCORE, which is handed mean+sd). Teaches the full pipeline
# end-to-end from raw data — mean, then population sd, then the z-score of a concrete value (its largest) —
# so the "Applying Standardization" topic gets an oracle-VERIFIED worked example instead of an LLM guess. Every
# output is a scalar the formula engine re-evaluates independently (mean -> sd -> z), so it is trace-verified.
STANDARDIZE_DATASET = FormulaSpec(
    slug="standardize_dataset",
    title="standardizing a value using a dataset's mean and standard deviation", family="statistics",
    aliases=["standardiz", "standardize", "standardization", "standard-score a value"],
    not_aliases=["batch normalization", "database", "normalize a vector"], priority=90,
    problem_template="For the dataset {xs}, standardize its largest value: find the z-score of that value — "
                     "how many standard deviations it lies from the mean.",
    givens=[], dataset=Dataset("xs", size_lo=5, size_hi=8, val_lo=1, val_hi=20),
    instance_ok=lambda row: len(set(row["xs"])) > 1,          # need spread so sd > 0 (standardization defined)
    outputs=[
        Output("mean", "mean = (sum of the values) / n", "sum(xs)/n", "", "compute_mean", "mean",
               show=[("sum of the values", "sum(xs)"), ("n", "n")]),
        Output("sd", "sd = sqrt( (sum of squared deviations from the mean) / n )",
               "sqrt(sum((x-mean)**2 for x in xs)/n)", "", "compute_std_dev", "standard deviation",
               show=[("sum of squared deviations from the mean", "sum((x-mean)**2 for x in xs)"), ("n", "n")]),
        Output("z", "z = (x - mean)/sd, with x = the largest value", "(max(xs) - mean)/sd", "",
               "compute_z_score", "z-score of the largest value",
               show=[("x = largest value", "max(xs)"), ("mean", "mean"), ("sd", "sd")])],
    conventions={"model": "population standard deviation (divide by n, not n-1)"},
    canonical_latex="z = \\frac{x - \\mu}{\\sigma}",
    canonical_notes=[
        "Standardizing rescales a value to how many standard deviations it sits from the mean.",
        "First the mean \\(\\mu = \\frac{\\sum x_i}{n}\\), then \\(\\sigma = \\sqrt{\\frac{\\sum (x_i-\\mu)^2}{n}}\\), "
        "then \\(z = \\frac{x - \\mu}{\\sigma}\\).",
        "A positive \\(z\\) means the value is above the mean; its magnitude is the distance in standard deviations.",
    ],
    edge_cases=[
        "Standardization needs \\(\\sigma > 0\\); if every value is identical there is no spread and \\(z\\) is undefined.",
        "Standardizing EVERY value of a dataset produces a new dataset with mean \\(0\\) and standard deviation \\(1\\).",
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

CROSS_PRODUCT_3D = FormulaSpec(
    slug="cross_product_3d", title="cross product of two 3D vectors", family="linear_algebra",
    aliases=["cross product", "vector product", "cross product of two vectors"],
    not_aliases=["dot product", "scalar product"],
    priority=54,
    problem_template="Find the cross product a x b of a = ({ax}, {ay}, {az}) and b = ({bx}, {by}, {bz}).",
    givens=[Given("ax", "", 1, 8), Given("ay", "", 1, 8), Given("az", "", 1, 8),
            Given("bx", "", 1, 8), Given("by", "", 1, 8), Given("bz", "", 1, 8)],
    outputs=[
        Output("cx", "(a x b)_x = ay*bz - az*by", "ay*bz - az*by", "", "compute_cross_x", "x-component"),
        Output("cy", "(a x b)_y = az*bx - ax*bz", "az*bx - ax*bz", "", "compute_cross_y", "y-component"),
        Output("cz", "(a x b)_z = ax*by - ay*bx", "ax*by - ay*bx", "", "compute_cross_z", "z-component"),
    ],
    conventions={"formula": "a x b = (ay*bz - az*by, az*bx - ax*bz, ax*by - ay*bx)"},
    canonical_latex="\\mathbf{a} \\times \\mathbf{b} = (a_yb_z - a_zb_y,\\ a_zb_x - a_xb_z,\\ a_xb_y - a_yb_x)",
    canonical_notes=[
        "The result is a VECTOR perpendicular to both \\(\\mathbf{a}\\) and \\(\\mathbf{b}\\) — unlike the "
        "dot product, which returns a scalar.",
    ],
    edge_cases=[
        "If \\(\\mathbf{a}\\) and \\(\\mathbf{b}\\) point in the same direction (one is a scalar multiple of "
        "the other), the cross product is the zero vector — there is no perpendicular direction to pick.",
    ])

ANGLE_BETWEEN_VECTORS = FormulaSpec(
    slug="angle_between_vectors", title="angle between two 3D vectors", family="linear_algebra",
    aliases=["angle between two vectors", "find the angle between vectors", "angle between vectors"],
    priority=53,
    problem_template="Find the angle (in degrees) between a = ({ax}, {ay}, {az}) and b = ({bx}, {by}, {bz}).",
    givens=[Given("ax", "", 1, 8), Given("ay", "", 1, 8), Given("az", "", 1, 8),
            Given("bx", "", 1, 8), Given("by", "", 1, 8), Given("bz", "", 1, 8)],
    outputs=[Output(
        "theta",
        "theta = acos((a.b) / (|a||b|))",
        "degrees(acos(max(-1, min(1, (ax*bx+ay*by+az*bz) / "
        "(sqrt(ax**2+ay**2+az**2) * sqrt(bx**2+by**2+bz**2))))))",
        "deg", "compute_angle", "angle between the vectors")],
    conventions={"formula": "cos(theta) = (a.b) / (|a||b|)"},
    canonical_latex="\\theta = \\arccos\\!\\left(\\frac{\\mathbf{a}\\cdot\\mathbf{b}}"
                    "{|\\mathbf{a}|\\,|\\mathbf{b}|}\\right)",
    canonical_notes=[
        "The dot product formula \\(\\mathbf{a}\\cdot\\mathbf{b} = |\\mathbf{a}||\\mathbf{b}|\\cos\\theta\\) "
        "is solved for \\(\\theta\\) directly.",
    ],
    edge_cases=[
        "If \\(\\mathbf{a}\\cdot\\mathbf{b} = 0\\), the angle is exactly 90 degrees — the vectors are "
        "orthogonal.",
    ])

COSINE_SIMILARITY = FormulaSpec(
    slug="cosine_similarity", title="cosine similarity of two vectors", family="linear_algebra",
    aliases=["cosine similarity", "cosine similarity of two vectors"],
    not_aliases=["angle between"],
    priority=52,
    problem_template="Find the cosine similarity of a = ({ax}, {ay}, {az}) and b = ({bx}, {by}, {bz}).",
    givens=[Given("ax", "", 1, 8), Given("ay", "", 1, 8), Given("az", "", 1, 8),
            Given("bx", "", 1, 8), Given("by", "", 1, 8), Given("bz", "", 1, 8)],
    outputs=[Output(
        "cos_sim", "cos_sim(a,b) = (a.b) / (|a||b|)",
        "(ax*bx+ay*by+az*bz) / (sqrt(ax**2+ay**2+az**2) * sqrt(bx**2+by**2+bz**2))",
        "", "compute_cosine_similarity", "cosine similarity")],
    conventions={"formula": "cosine of the angle between the two vectors",
                 "range": "always between -1 and 1"},
    canonical_latex="\\cos\\text{-sim}(\\mathbf{a},\\mathbf{b}) = \\frac{\\mathbf{a}\\cdot\\mathbf{b}}"
                    "{|\\mathbf{a}|\\,|\\mathbf{b}|}",
    canonical_notes=[
        "Cosine similarity is exactly \\(\\cos\\theta\\) from the angle-between-vectors formula — it measures "
        "DIRECTION similarity, not magnitude, so scaling either vector never changes the result.",
    ],
    edge_cases=[
        "Cosine similarity equals 1 exactly when the vectors point in the same direction, regardless of how "
        "different their magnitudes are.",
    ])

DETERMINANT_3X3 = FormulaSpec(
    slug="determinant_3x3", title="determinant of a 3x3 matrix", family="linear_algebra",
    aliases=["3x3 determinant", "determinant of a 3x3 matrix", "cofactor expansion"],
    not_aliases=["2x2"],
    priority=37,
    problem_template="Find the determinant of the 3x3 matrix with rows ({a11}, {a12}, {a13}), "
                     "({a21}, {a22}, {a23}), ({a31}, {a32}, {a33}).",
    givens=[Given("a11", "", 1, 6), Given("a12", "", 1, 6), Given("a13", "", 1, 6),
            Given("a21", "", 1, 6), Given("a22", "", 1, 6), Given("a23", "", 1, 6),
            Given("a31", "", 1, 6), Given("a32", "", 1, 6), Given("a33", "", 1, 6)],
    outputs=[Output(
        "det", "det = a11*(a22*a33 - a23*a32) - a12*(a21*a33 - a23*a31) + a13*(a21*a32 - a22*a31)",
        "a11*(a22*a33 - a23*a32) - a12*(a21*a33 - a23*a31) + a13*(a21*a32 - a22*a31)",
        "", "compute_determinant", "determinant")],
    conventions={"method": "cofactor expansion along the first row"},
    canonical_latex="\\det(M) = a_{11}(a_{22}a_{33}-a_{23}a_{32}) - a_{12}(a_{21}a_{33}-a_{23}a_{31}) "
                    "+ a_{13}(a_{21}a_{32}-a_{22}a_{31})",
    canonical_notes=[
        "Each term multiplies an entry of the first row by the determinant of the 2x2 matrix left after "
        "deleting that entry's row and column — the middle term is SUBTRACTED (alternating sign).",
    ],
    edge_cases=[
        "A determinant of 0 means the matrix is singular (not invertible) — its rows are linearly dependent.",
    ])

MATRIX_TRACE = FormulaSpec(
    slug="matrix_trace", title="trace of a 3x3 matrix", family="linear_algebra",
    aliases=["trace of a matrix", "matrix trace", "sum of the diagonal"],
    priority=36,
    problem_template="Find the trace of the 3x3 matrix with rows ({a11}, {a12}, {a13}), "
                     "({a21}, {a22}, {a23}), ({a31}, {a32}, {a33}).",
    givens=[Given("a11", "", 1, 12), Given("a12", "", 1, 12), Given("a13", "", 1, 12),
            Given("a21", "", 1, 12), Given("a22", "", 1, 12), Given("a23", "", 1, 12),
            Given("a31", "", 1, 12), Given("a32", "", 1, 12), Given("a33", "", 1, 12)],
    outputs=[Output("tr", "tr(M) = a11 + a22 + a33", "a11 + a22 + a33", "", "compute_trace", "trace")],
    conventions={"formula": "sum of the entries on the main diagonal"},
    canonical_latex="\\text{tr}(M) = a_{11} + a_{22} + a_{33}",
    canonical_notes=[
        "Only the diagonal entries matter — every off-diagonal entry (a12, a21, a13, a31, a23, a32) is "
        "ignored entirely.",
    ],
    edge_cases=[
        "The trace is defined only for SQUARE matrices — a non-square matrix has no diagonal to sum.",
    ])

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

SERIES_RESISTANCE = FormulaSpec(
    slug="series_resistance", title="equivalent resistance of resistors in series", family="physics",
    aliases=["series resistance", "resistors in series", "equivalent resistance in series"],
    not_aliases=["parallel"], priority=53,
    problem_template="Three resistors R1 = {R1} ohm, R2 = {R2} ohm, and R3 = {R3} ohm are connected in "
                     "series. Find the equivalent resistance.",
    givens=[Given("R1", "ohm", 1, 100), Given("R2", "ohm", 1, 100), Given("R3", "ohm", 1, 100)],
    outputs=[Output("Req", "Req = R1 + R2 + R3", "R1 + R2 + R3", "ohm", "compute_series_resistance",
                    "equivalent resistance")],
    conventions={"rule": "resistances in series simply add"},
    canonical_latex="R_{eq} = R_1 + R_2 + R_3",
    canonical_notes=[
        "In series, the SAME current flows through every resistor, so their voltage drops add up — this is "
        "why the resistances themselves add directly.",
    ],
    edge_cases=[
        "The equivalent series resistance is always GREATER than any single resistor in the chain.",
    ])

PARALLEL_RESISTANCE = FormulaSpec(
    slug="parallel_resistance", title="equivalent resistance of two resistors in parallel", family="physics",
    aliases=["parallel resistance", "resistors in parallel", "equivalent resistance in parallel"],
    not_aliases=["series"], priority=53,
    problem_template="Two resistors R1 = {R1} ohm and R2 = {R2} ohm are connected in parallel. Find the "
                     "equivalent resistance.",
    givens=[Given("R1", "ohm", 1, 100), Given("R2", "ohm", 1, 100)],
    outputs=[Output("Req", "Req = (R1*R2)/(R1+R2)", "(R1*R2)/(R1+R2)", "ohm", "compute_parallel_resistance",
                    "equivalent resistance")],
    conventions={"rule": "reciprocal of the sum of reciprocals; for two resistors this simplifies to "
                         "product over sum"},
    canonical_latex="R_{eq} = \\frac{R_1 R_2}{R_1 + R_2}",
    canonical_notes=[
        "In parallel, both resistors share the SAME voltage, and the currents through them add — this "
        "always makes the equivalent resistance SMALLER than either individual resistor.",
    ],
    edge_cases=[
        "The equivalent parallel resistance is always LESS than the smaller of the two individual "
        "resistors — adding a second path can only make it easier for current to flow.",
    ])

VOLTAGE_DIVIDER = FormulaSpec(
    slug="voltage_divider", title="output voltage of a resistive voltage divider", family="physics",
    aliases=["voltage divider", "voltage divider circuit", "voltage divider rule"], priority=54,
    problem_template="A voltage divider has input voltage Vin = {Vin} V across two series resistors "
                     "R1 = {R1} ohm and R2 = {R2} ohm. Find the output voltage Vout measured across R2.",
    givens=[Given("Vin", "V", 3, 24), Given("R1", "ohm", 1, 50), Given("R2", "ohm", 1, 50)],
    outputs=[Output("Vout", "Vout = Vin * R2/(R1+R2)", "Vin * R2/(R1+R2)", "V", "compute_voltage_divider",
                    "output voltage")],
    conventions={"rule": "the output voltage is the fraction of Vin dropped across R2"},
    canonical_latex="V_{out} = V_{in}\\,\\frac{R_2}{R_1+R_2}",
    canonical_notes=[
        "The SAME current flows through both series resistors, so each resistor's share of the total "
        "voltage is proportional to its own resistance out of the total.",
    ],
    edge_cases=[
        "If R2 = 0, Vout = 0 — a resistor of zero resistance drops no voltage at all, so the output is "
        "shorted to ground.",
    ])

CURRENT_DIVIDER = FormulaSpec(
    slug="current_divider", title="branch current of a resistive current divider", family="physics",
    aliases=["current divider", "current divider circuit", "current divider rule"], priority=54,
    problem_template="A current divider splits an input current Iin = {Iin} A between two parallel "
                     "resistors R1 = {R1} ohm and R2 = {R2} ohm. Find the current through R2.",
    givens=[Given("Iin", "A", 1, 20), Given("R1", "ohm", 1, 50), Given("R2", "ohm", 1, 50)],
    outputs=[Output("I2", "I2 = Iin * R1/(R1+R2)", "Iin * R1/(R1+R2)", "A", "compute_current_divider",
                    "current through R2")],
    conventions={"rule": "current divides INVERSELY to resistance — the branch current formula uses the "
                         "OTHER resistor in the numerator"},
    canonical_latex="I_2 = I_{in}\\,\\frac{R_1}{R_1+R_2}",
    canonical_notes=[
        "Unlike the voltage divider, the current-divider formula for I2 uses R1 (the OTHER resistor) in "
        "the numerator — more current takes the path of LESS resistance, so R2's own share shrinks as R2 "
        "grows.",
    ],
    edge_cases=[
        "If R2 is much larger than R1, nearly all the current flows through R1 instead — a very large "
        "resistance is close to an open circuit for that branch.",
    ])

IMPEDANCE_MAGNITUDE = FormulaSpec(
    slug="impedance_magnitude", title="magnitude of impedance from resistance and reactance", family="physics",
    aliases=["impedance magnitude", "magnitude of impedance", "compute the impedance"], priority=53,
    problem_template="A circuit has resistance R = {R} ohm and reactance X = {X} ohm. Find the magnitude "
                     "of its impedance.",
    givens=[Given("R", "ohm", 1, 40), Given("X", "ohm", 1, 40)],
    outputs=[Output("Z", "|Z| = sqrt(R^2 + X^2)", "sqrt(R**2 + X**2)", "ohm", "compute_impedance_magnitude",
                    "impedance magnitude")],
    conventions={"model": "impedance = resistance + j*reactance; magnitude via the Pythagorean-style formula"},
    canonical_latex="|Z| = \\sqrt{R^2 + X^2}",
    canonical_notes=[
        "Impedance combines resistance (energy dissipated) and reactance (energy stored/returned by "
        "capacitors and inductors) into one complex number; its magnitude behaves like a Pythagorean "
        "hypotenuse because resistance and reactance are 90 degrees out of phase.",
    ],
    edge_cases=[
        "If X = 0 (a purely resistive circuit), \\(|Z| = R\\) exactly — impedance reduces to plain "
        "resistance.",
    ])

POWER_FACTOR = FormulaSpec(
    slug="power_factor", title="power factor from resistance and reactance", family="physics",
    aliases=["power factor", "compute the power factor", "power factor of a circuit"], priority=53,
    problem_template="A circuit has resistance R = {R} ohm and reactance X = {X} ohm. Find the power "
                     "factor.",
    givens=[Given("R", "ohm", 1, 40), Given("X", "ohm", 1, 40)],
    outputs=[Output("pf", "pf = R / sqrt(R^2 + X^2)", "R / sqrt(R**2 + X**2)", "", "compute_power_factor",
                    "power factor")],
    conventions={"definition": "power factor = resistance / impedance magnitude = cos(phase angle)"},
    canonical_latex="\\text{pf} = \\frac{R}{|Z|} = \\frac{R}{\\sqrt{R^2+X^2}}",
    canonical_notes=[
        "The power factor is always between 0 and 1 — it measures what fraction of the apparent power "
        "actually does useful work, rather than sloshing back and forth in the reactive components.",
    ],
    edge_cases=[
        "If X = 0, pf = 1 (unity power factor) — a purely resistive circuit converts all its power to work, "
        "none of it is reactive.",
    ])

THREE_PHASE_POWER = FormulaSpec(
    slug="three_phase_power", title="real power in a balanced three-phase system", family="physics",
    aliases=["three phase power", "three-phase power", "balanced three phase power"], priority=53,
    problem_template="A balanced three-phase system has line voltage VL = {VL} V, line current IL = "
                     "{IL} A, and power factor pf = {pf}. Find the total real power.",
    givens=[Given("VL", "V", 100, 480), Given("IL", "A", 1, 50), Given("pf", "", 0.6, 1.0, integer=False)],
    outputs=[Output("P", "P = sqrt(3) * VL * IL * pf", "sqrt(3) * VL * IL * pf", "W",
                    "compute_three_phase_power", "total real power")],
    conventions={"model": "balanced three-phase system (all three phases carry equal load)"},
    canonical_latex="P = \\sqrt{3}\\,V_L I_L \\cos\\varphi",
    canonical_notes=[
        "The \\(\\sqrt{3}\\) factor comes from the 120-degree phase relationship between the three lines in "
        "a balanced system — it is NOT simply 3x the single-phase formula.",
    ],
    edge_cases=[
        "At pf = 1 (unity power factor), the formula reduces to \\(P = \\sqrt{3}\\,V_L I_L\\) exactly — all "
        "of the apparent power is real power.",
    ])

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

# --- vector calculus (ADAPTER_TAXONOMY_SPEC.md §6 T6 calculus backlog) --------------------------------------
# Genuinely T6-shaped, not T7/CAS: each spec FIXES a specific function/field and gives its ALREADY-DIFFERENTIATED
# formula (derived and verified by hand below, then cross-checked against numerical finite differences) — the
# engine evaluates that formula numerically at a given point, exactly like every other formula-plug-in concept.
# It teaches the VALUE of a partial derivative/curl/divergence at a point, not the differentiation PROCESS
# itself (symbolic differentiation is T7-deferred — needs a real CAS, not this engine).
PARTIAL_DERIVATIVE_XY = FormulaSpec(
    slug="partial_derivative_xy", title="partial derivative of f(x,y) = x^2*y + 3*y^3", family="calculus",
    aliases=["partial derivative", "partial derivative at a point", "compute the partial derivative",
             "partial derivative of a multivariable function"],
    not_aliases=["curl", "divergence", "gradient", "directional derivative"],
    priority=53,
    problem_template="For f(x, y) = x^2*y + 3*y^3, find the partial derivative df/dx at the point "
                     "(x, y) = ({x}, {y}).",
    givens=[Given("x", "", -6, 6), Given("y", "", -4, 4)],
    outputs=[Output("fx", "df/dx = 2*x*y", "2*x*y", "", "compute_partial_derivative",
                    "partial derivative with respect to x")],
    conventions={"function": "f(x,y) = x^2*y + 3y^3", "rule": "differentiate w.r.t. x, holding y constant"},
    canonical_latex="\\frac{\\partial f}{\\partial x} = 2xy",
    canonical_notes=[
        "\\(f(x,y) = x^2 y + 3y^3\\). Differentiating with respect to \\(x\\) treats \\(y\\) as a constant: "
        "the power rule gives \\(2xy\\) from the \\(x^2y\\) term, and the \\(3y^3\\) term has no \\(x\\), so "
        "it vanishes entirely.",
    ],
    edge_cases=[
        "At \\(x = 0\\), \\(\\partial f/\\partial x = 0\\) regardless of \\(y\\) — the surface has zero slope "
        "in the x-direction anywhere on the y-axis.",
    ])

GRADIENT_MAGNITUDE_XY = FormulaSpec(
    slug="gradient_magnitude_xy", title="magnitude of the gradient of f(x,y) = x^2*y + 3*y^3",
    family="calculus",
    aliases=["gradient magnitude", "magnitude of the gradient", "magnitude of the gradient vector",
             "compute the gradient magnitude"],
    not_aliases=["curl", "divergence", "directional derivative"],
    priority=53,
    problem_template="For f(x, y) = x^2*y + 3*y^3, find the magnitude of the gradient vector "
                     "grad(f) at (x, y) = ({x}, {y}).",
    givens=[Given("x", "", -6, 6), Given("y", "", -4, 4)],
    outputs=[Output("grad_mag", "|grad(f)| = sqrt((2*x*y)^2 + (x^2 + 9*y^2)^2)",
                    "sqrt((2*x*y)**2 + (x**2 + 9*y**2)**2)", "", "compute_gradient_magnitude",
                    "gradient magnitude")],
    conventions={"function": "f(x,y) = x^2*y + 3y^3",
                 "gradient": "grad(f) = (df/dx, df/dy) = (2xy, x^2 + 9y^2)"},
    canonical_latex="|\\nabla f| = \\sqrt{(2xy)^2 + (x^2 + 9y^2)^2}",
    canonical_notes=[
        "The gradient collects both partial derivatives into one vector: "
        "\\(\\nabla f = (\\partial f/\\partial x,\\ \\partial f/\\partial y) = (2xy,\\ x^2 + 9y^2)\\). "
        "Its magnitude is the Euclidean length of that vector.",
    ],
    edge_cases=[
        "At \\(x = 0, y = 0\\), both partial derivatives are 0, so \\(|\\nabla f| = 0\\) — the origin is a "
        "critical point of the surface.",
    ])

DIRECTIONAL_DERIVATIVE_XY = FormulaSpec(
    slug="directional_derivative_xy", title="directional derivative of f(x,y) = x^2*y + 3*y^3",
    family="calculus",
    aliases=["directional derivative", "directional derivative at a point",
             "compute the directional derivative"],
    not_aliases=["curl", "divergence", "gradient magnitude"],
    priority=54,
    problem_template="For f(x, y) = x^2*y + 3*y^3, find the directional derivative at (x, y) = ({x}, {y}) "
                     "in the direction of the vector (a, b) = ({a}, {b}).",
    givens=[Given("x", "", -6, 6), Given("y", "", -4, 4), Given("a", "", 1, 5), Given("b", "", 1, 5)],
    outputs=[Output("D_u_f", "D_u f = (2*x*y*a + (x^2 + 9*y^2)*b) / sqrt(a^2 + b^2)",
                    "(2*x*y*a + (x**2 + 9*y**2)*b) / sqrt(a**2 + b**2)", "", "compute_directional_derivative",
                    "directional derivative")],
    conventions={"function": "f(x,y) = x^2*y + 3y^3", "gradient": "grad(f) = (2xy, x^2 + 9y^2)",
                 "definition": "D_u f = grad(f) . (u / |u|) — the direction vector is normalized first"},
    canonical_latex="D_{\\mathbf{u}}f = \\nabla f \\cdot \\frac{\\mathbf{u}}{|\\mathbf{u}|}",
    canonical_notes=[
        "The direction vector \\((a, b)\\) is not required to already be a unit vector — dividing by "
        "\\(\\sqrt{a^2+b^2}\\) normalizes it, since the directional derivative is only meaningful for a unit "
        "direction.",
    ],
    edge_cases=[
        "Moving in the direction of \\(\\nabla f\\) itself gives the LARGEST possible directional derivative "
        "at that point — this is why the gradient points in the direction of steepest ascent.",
    ])

CURL_2D = FormulaSpec(
    slug="curl_2d_vector_field", title="scalar curl of the 2D vector field F(x,y) = (x^2*y, x*y^2)",
    family="calculus",
    aliases=["curl of a vector field", "compute the curl", "curl in 2d", "scalar curl", "curl of F"],
    # "stokes" guard: a title mentioning both curl and Stokes' theorem must route to the dedicated
    # stokes_theorem adapter (a full surface-vs-boundary integral verification), not this 2D point-value
    # curl formula plug-in — same collision class DIV_2D already guards against ("divergence theorem setup").
    not_aliases=["divergence", "gradient", "partial derivative", "stokes"],
    priority=53,
    problem_template="For the vector field F(x, y) = (x^2*y, x*y^2), find the scalar curl at "
                     "(x, y) = ({x}, {y}).",
    givens=[Given("x", "", -5, 5), Given("y", "", -5, 5)],
    outputs=[Output("curl_z", "curl_z = y^2 - x^2", "y**2 - x**2", "", "compute_curl", "scalar curl")],
    conventions={"field": "F(x,y) = (P, Q) = (x^2*y, x*y^2)",
                 "definition": "curl_z = dQ/dx - dP/dy"},
    canonical_latex="\\text{curl}_z\\, F = \\frac{\\partial Q}{\\partial x} - \\frac{\\partial P}{\\partial y}",
    canonical_notes=[
        "For \\(F = (P, Q) = (x^2y,\\ xy^2)\\): \\(\\partial Q/\\partial x = y^2\\) and "
        "\\(\\partial P/\\partial y = x^2\\), so \\(\\text{curl}_z F = y^2 - x^2\\).",
        "A nonzero scalar curl means the field has local rotation at that point; curl = 0 means the field is "
        "locally irrotational there.",
    ],
    edge_cases=[
        "Along the line \\(y = x\\), \\(\\text{curl}_z F = x^2 - x^2 = 0\\) — the field is irrotational "
        "exactly on that line, even though it rotates elsewhere.",
    ])

DIV_2D = FormulaSpec(
    slug="divergence_2d_vector_field", title="divergence of the 2D vector field F(x,y) = (x^2, y^2)",
    family="calculus",
    # "divergence theorem setup" used to live here as an alias; the dedicated divergence_theorem adapter
    # (full volume-vs-flux verification, priority 111) now owns every "divergence theorem" title, so this
    # spec keeps only the point-value divergence phrasings and guards against the theorem titles.
    aliases=["divergence of a vector field", "compute the divergence", "divergence in 2d",
             "divergence of F"],
    not_aliases=["curl", "gradient", "partial derivative", "theorem"],
    priority=53,
    problem_template="For the vector field F(x, y) = (x^2, y^2), find the divergence at "
                     "(x, y) = ({x}, {y}).",
    givens=[Given("x", "", -5, 5), Given("y", "", -5, 5)],
    outputs=[Output("div_F", "div(F) = 2*x + 2*y", "2*x + 2*y", "", "compute_divergence", "divergence")],
    conventions={"field": "F(x,y) = (P, Q) = (x^2, y^2)", "definition": "div(F) = dP/dx + dQ/dy"},
    canonical_latex="\\text{div}\\, F = \\frac{\\partial P}{\\partial x} + \\frac{\\partial Q}{\\partial y}",
    canonical_notes=[
        "For \\(F = (P, Q) = (x^2,\\ y^2)\\): \\(\\partial P/\\partial x = 2x\\) and \\(\\partial Q/\\partial "
        "y = 2y\\), so \\(\\text{div}\\,F = 2x + 2y\\).",
        "Positive divergence at a point means the field is a net SOURCE there (flux flows outward); negative "
        "divergence means a net sink.",
    ],
    edge_cases=[
        "At \\(x = -y\\) (e.g. the origin), \\(\\text{div}\\,F = 0\\) — the field is locally "
        "divergence-free along that line even though it is a source or sink everywhere else.",
    ])

# --- the full concept set; ALL_SPECS drives the gate, the registry, the manifest, and routing ---------
ALL_SPECS = [
    # physics / EE
    KINEMATICS, KINETIC_ENERGY, NEWTONS_SECOND_LAW, WEIGHT_FORCE, MOMENTUM, WORK_DONE, GRAVITATIONAL_PE, OHMS_LAW,
    PROJECTILE_RANGE, CENTRIPETAL_ACCEL, WAVE_SPEED, PRESSURE, MECHANICAL_POWER, SPRING_PE, REYNOLDS_NUMBER,
    LAMINAR_PRESSURE_DROP, TURBULENT_KINETIC_ENERGY,
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
    DESCRIPTIVE_STATS, MEDIAN_RANGE, Z_SCORE, STANDARDIZE_DATASET, COEFF_OF_VARIATION, MEAN_ABS_DEVIATION,
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
    # vector calculus
    PARTIAL_DERIVATIVE_XY, GRADIENT_MAGNITUDE_XY, DIRECTIONAL_DERIVATIVE_XY, CURL_2D, DIV_2D,
    # more linear algebra
    CROSS_PRODUCT_3D, ANGLE_BETWEEN_VECTORS, COSINE_SIMILARITY, DETERMINANT_3X3, MATRIX_TRACE,
    # more statistics
    CORRELATION, BINOMIAL_PROBABILITY,
    # more finance
    NPV_THREE_PERIOD, DISCOUNT_FACTOR, CAPM_EXPECTED_RETURN, PORTFOLIO_RETURN_TWO_ASSET, FORWARD_PRICE,
    OPTION_PAYOFF_CALL, SHARPE_RATIO,
    # more EE
    SERIES_RESISTANCE, PARALLEL_RESISTANCE, VOLTAGE_DIVIDER, CURRENT_DIVIDER, IMPEDANCE_MAGNITUDE,
    POWER_FACTOR, THREE_PHASE_POWER,
]

# ======================================================================================================
# GROUNDING TABLE — canonical formula + symbol notes + authored edge cases for the remaining specs, so EVERY
# formula adapter is uniform (isolated `$$` math, `\(...\)`-wrapped symbols, correct boundary facts) rather
# than letting the LLM write the formula/edge card. Applied by the loop below to any spec not already grounded
# inline. Keep LaTeX renderer-safe (\frac, \sqrt, \sum, greek, subscripts; avoid \sin/\det/\max/\text/\cdots).
# ======================================================================================================
_GROUNDING: dict[str, tuple[str, list[str], list[str]]] = {
    # --- algebra / sequences / rates -----------------------------------------------------------------
    "distance_rate_time": ("d = rt", ["\\(r\\): rate (speed).  \\(t\\): time."],
                           ["Assumes a constant rate over the whole time."]),
    "percent_of": ("\\frac{percent \\times whole}{100}",
                   ["\\(percent\\): the percentage.  \\(whole\\): the amount it is taken of."],
                   ["E.g. 20% of 50 is \\(\\frac{20 \\times 50}{100} = 10\\)."]),
    "arithmetic_sequence_term": ("a_n = a_1 + (n-1)d",
                                 ["\\(a_1\\): first term.  \\(d\\): common difference.  \\(n\\): term number."],
                                 ["The terms grow LINEARLY in \\(n\\) (a fixed step \\(d\\) each time)."]),
    "geometric_sequence_term": ("a_n = a_1 r^{n-1}",
                                ["\\(a_1\\): first term.  \\(r\\): common ratio.  \\(n\\): term number."],
                                ["With \\(|r| > 1\\) the terms grow; with \\(|r| < 1\\) they shrink toward 0."]),
    # --- finance / business --------------------------------------------------------------------------
    "present_value": ("PV = \\frac{FV}{(1 + \\frac{r}{100})^t}",
                      ["\\(FV\\): future amount.  \\(r\\): annual discount rate (percent).  \\(t\\): years."],
                      ["Today's worth of a future amount; a higher rate or longer wait lowers it."]),
    "future_value": ("FV = PV(1 + \\frac{r}{100})^t",
                     ["\\(PV\\): present amount.  \\(r\\): annual rate (percent).  \\(t\\): years."],
                     ["Grows exponentially with time (compound growth); at \\(r = 0\\) it stays at \\(PV\\)."]),
    "break_even": ("q = \\frac{F}{p - c}",
                   ["\\(F\\): fixed cost.  \\(p\\): price per unit.  \\(c\\): variable cost per unit.  "
                    "\\(p - c\\) is the contribution margin."],
                   ["Undefined when \\(p = c\\) (no margin — the business never breaks even); needs \\(p > c\\)."]),
    "profit_margin": ("\\frac{revenue - cost}{revenue} \\times 100",
                      ["Profit as a percent of \\(revenue\\)."],
                      ["Undefined when \\(revenue = 0\\); a negative margin means a loss."]),
    "discount_price": ("sale = price(1 - \\frac{disc}{100})",
                       ["\\(price\\): original price.  \\(disc\\): discount percent."],
                       ["A 100% discount gives a sale price of 0."]),
    "sales_tax_total": ("total = price(1 + \\frac{tax}{100})",
                        ["\\(price\\): pre-tax price.  \\(tax\\): tax percent."], ["Tax adds to the price."]),
    "simple_roi": ("ROI = \\frac{gain - cost}{cost} \\times 100",
                   ["\\(gain\\): amount returned.  \\(cost\\): amount invested."],
                   ["Undefined when \\(cost = 0\\); a negative ROI is a loss."]),
    "unit_price": ("\\frac{price}{quantity}",
                   ["\\(price\\): total price.  \\(quantity\\): number of units."],
                   ["Undefined when \\(quantity = 0\\); a lower unit price is the better value."]),
    "percent_increase": ("new = original(1 + \\frac{pct}{100})",
                         ["\\(original\\): starting value.  \\(pct\\): percent increase."],
                         ["A percent DEcrease uses \\(1 - \\frac{pct}{100}\\)."]),
    # --- geometry ------------------------------------------------------------------------------------
    "sphere_volume": ("V = \\frac{4}{3}\\pi r^3", ["\\(r\\): the radius."],
                      ["Volume scales with \\(r^3\\): doubling the radius multiplies the volume by 8."]),
    "sphere_surface_area": ("A = 4\\pi r^2", ["\\(r\\): the radius."],
                            ["Surface area scales with \\(r^2\\)."]),
    "cylinder_volume": ("V = \\pi r^2 h", ["\\(r\\): base radius.  \\(h\\): height."],
                        ["It is the base area \\(\\pi r^2\\) times the height."]),
    "cone_volume": ("V = \\frac{1}{3}\\pi r^2 h", ["\\(r\\): base radius.  \\(h\\): height."],
                    ["A cone is exactly one-third of the cylinder with the same base and height."]),
    "cube_volume": ("V = s^3", ["\\(s\\): the side length."],
                    ["Doubling the side multiplies the volume by 8."]),
    "cube_surface_area": ("A = 6s^2", ["\\(s\\): the side length (6 faces, each \\(s \\times s\\))."],
                          ["Doubling the side quadruples the surface area."]),
    "rectangle_perimeter": ("P = 2(l + w)", ["\\(l\\): length.  \\(w\\): width."],
                            ["A square is the special case \\(l = w\\), giving \\(P = 4l\\)."]),
    "parallelogram_area": ("A = bh", ["\\(b\\): base.  \\(h\\): the PERPENDICULAR height."],
                           ["\\(h\\) is the perpendicular distance, not a slanted side."]),
    "trapezoid_area": ("A = \\frac{a + b}{2} \\times h",
                       ["\\(a\\), \\(b\\): the two parallel sides.  \\(h\\): the perpendicular distance between them."],
                       ["It uses the AVERAGE of the two parallel sides."]),
    "coordinate_distance": ("d = \\sqrt{(x_2 - x_1)^2 + (y_2 - y_1)^2}",
                            ["The straight-line distance between \\((x_1, y_1)\\) and \\((x_2, y_2)\\)."],
                            ["This is the Pythagorean theorem applied to the coordinate differences."]),
    "midpoint": ("(\\frac{x_1 + x_2}{2}, \\frac{y_1 + y_2}{2})",
                 ["The AVERAGE of the two endpoints' coordinates."],
                 ["The midpoint lies exactly halfway along the segment."]),
    "slope": ("m = \\frac{y_2 - y_1}{x_2 - x_1}", ["Rise over run — vertical change divided by horizontal change."],
              ["Undefined for a VERTICAL line (\\(x_2 = x_1\\), division by zero); 0 for a horizontal line."]),
    "sector_area": ("A = \\frac{\\theta}{360} \\times \\pi r^2",
                    ["\\(\\theta\\): the central angle in degrees.  \\(r\\): the radius."],
                    ["It is the fraction \\(\\theta/360\\) of the full circle's area."]),
    "arc_length": ("L = \\frac{\\theta}{360} \\times 2\\pi r",
                   ["\\(\\theta\\): the central angle in degrees.  \\(r\\): the radius."],
                   ["It is the fraction \\(\\theta/360\\) of the full circumference."]),
    "polygon_interior_angle": ("\\frac{(n-2) \\times 180}{n}", ["\\(n\\): the number of sides (regular polygon)."],
                               ["The interior angles of any \\(n\\)-gon sum to \\((n-2) \\times 180°\\)."]),
    "polygon_exterior_angle": ("\\frac{360}{n}", ["\\(n\\): the number of sides (regular polygon)."],
                               ["The exterior angles of ANY convex polygon sum to 360°."]),
    "tangent_ratio": ("tan(\\theta) = \\frac{opp}{adj}",
                      ["\\(opp\\): side opposite the angle.  \\(adj\\): side adjacent to it."],
                      ["Defined for the acute angles of a RIGHT triangle."]),
    # --- physics -------------------------------------------------------------------------------------
    "weight_force": ("W = mg", ["\\(m\\): mass.  \\(g \\approx 9.8\\) m/s²."],
                     ["Weight (a force) is not mass; it changes with \\(g\\) (e.g. on the Moon)."]),
    "work_done": ("W = Fd", ["\\(F\\): force ALONG the displacement.  \\(d\\): distance moved."],
                  ["Zero work if the force is perpendicular to the motion."]),
    "gravitational_pe": ("PE = mgh", ["\\(m\\): mass.  \\(g \\approx 9.8\\) m/s².  \\(h\\): height."],
                         ["Only DIFFERENCES in height matter — the zero of height is a free choice."]),
    "average_speed": ("v = \\frac{d}{t}", ["\\(d\\): total distance.  \\(t\\): total time."],
                      ["This is the AVERAGE, not the speed at any instant."]),
    "centripetal_acceleration": ("a = \\frac{v^2}{r}",
                                 ["\\(v\\): speed.  \\(r\\): radius of the circular path."],
                                 ["Points toward the center; grows with the SQUARE of speed."]),
    "wave_speed": ("v = f\\lambda", ["\\(f\\): frequency.  \\(\\lambda\\): wavelength."],
                   ["In a given medium \\(v\\) is fixed, so higher frequency means shorter wavelength."]),
    "pressure": ("P = \\frac{F}{A}", ["\\(F\\): force.  \\(A\\): area it acts on."],
                 ["The same force over a SMALLER area gives MORE pressure."]),
    "fluid_pressure": ("P = \\rho g h", ["\\(\\rho\\): fluid density.  \\(g\\): gravity.  \\(h\\): depth."],
                       ["Pressure increases with depth; it does not depend on the container's shape."]),
    "mechanical_power": ("P = \\frac{W}{t}", ["\\(W\\): work done.  \\(t\\): time taken."],
                         ["Power is the RATE of doing work."]),
    "power_from_current": ("P = I^2 R", ["\\(I\\): current.  \\(R\\): resistance."],
                           ["Power grows with the SQUARE of the current."]),
    "ohms_power": ("P = \\frac{V^2}{R}", ["\\(V\\): voltage.  \\(R\\): resistance."],
                   ["Undefined at \\(R = 0\\); grows with the square of the voltage."]),
    "ohms_resistance": ("R = \\frac{V}{I}", ["\\(V\\): voltage.  \\(I\\): current."],
                        ["Undefined at \\(I = 0\\)."]),
    "spring_pe": ("PE = \\frac{k x^2}{2}", ["\\(k\\): spring constant.  \\(x\\): displacement from rest."],
                  ["Energy grows with the SQUARE of the stretch; it is 0 at the natural length."]),
    "hookes_force": ("F = kx", ["\\(k\\): spring constant.  \\(x\\): displacement from rest."],
                     ["Holds only within the ELASTIC limit; the force opposes the displacement."]),
    "impulse": ("J = Ft", ["\\(F\\): force.  \\(t\\): time it acts for."],
                ["Impulse equals the change in momentum."]),
    "pendulum_period": ("T = 2\\pi\\sqrt{\\frac{L}{g}}", ["\\(L\\): length.  \\(g\\): gravity."],
                        ["For small swings the period is INDEPENDENT of mass and amplitude."]),
    "spring_period": ("T = 2\\pi\\sqrt{\\frac{m}{k}}", ["\\(m\\): mass.  \\(k\\): spring constant."],
                      ["A heavier mass oscillates slower; a stiffer spring, faster."]),
    "frequency_from_period": ("f = \\frac{1}{T}", ["\\(T\\): period (s).  \\(f\\): frequency (Hz)."],
                              ["Frequency and period are reciprocals."]),
    "heat_energy": ("Q = mc\\Delta T",
                    ["\\(m\\): mass.  \\(c\\): specific heat.  \\(\\Delta T\\): temperature change."],
                    ["\\(Q > 0\\) heats the sample, \\(Q < 0\\) cools it."]),
    "free_fall_velocity": ("v = gt", ["\\(g \\approx 9.8\\) m/s².  \\(t\\): time falling from rest."],
                           ["Ignores air resistance; speed grows linearly with time."]),
    "free_fall_distance": ("d = \\frac{g t^2}{2}", ["\\(g \\approx 9.8\\) m/s².  \\(t\\): time falling from rest."],
                           ["Ignores air resistance; distance grows with the SQUARE of time."]),
    "potential_to_kinetic": ("v = \\sqrt{2gh}", ["\\(g\\): gravity.  \\(h\\): height dropped."],
                             ["From energy conservation; the final speed is INDEPENDENT of mass."]),
    "projectile_range": ("R = \\frac{v^2 sin(2\\theta)}{g}",
                         ["\\(v\\): launch speed.  \\(\\theta\\): launch angle.  \\(g\\): gravity."],
                         ["Maximum range is at \\(\\theta = 45°\\); ignores air resistance, level ground."]),
    "celsius_to_fahrenheit": ("F = \\frac{9C}{5} + 32", ["\\(C\\): temperature in Celsius."],
                              ["The two scales read equal at \\(-40°\\)."]),
    "fahrenheit_to_celsius": ("C = \\frac{5(F - 32)}{9}", ["\\(F\\): temperature in Fahrenheit."],
                              ["The two scales read equal at \\(-40°\\)."]),
    "kelvin_conversion": ("K = C + 273", ["\\(C\\): temperature in Celsius (more precisely add 273.15)."],
                          ["0 K is absolute zero, so Kelvin is never negative."]),
    "efficiency": ("\\frac{useful}{useful + wasted} \\times 100",
                   ["\\(useful\\): useful energy out.  \\(wasted\\): energy lost."],
                   ["Real efficiency is always LESS than 100% — some energy is always wasted."]),
    # --- linear algebra ------------------------------------------------------------------------------
    "determinant_2x2": ("det = ad - bc", ["For the matrix with rows \\((a, b)\\) and \\((c, d)\\)."],
                        ["\\(det = 0\\) means the matrix is SINGULAR (has no inverse)."]),
    "vector_magnitude": ("|v| = \\sqrt{x^2 + y^2 + z^2}", ["\\(x, y, z\\): the vector's components."],
                         ["The magnitude is 0 only for the zero vector; it is never negative."]),
    "dot_product_3d": ("a \\cdot b = a_x b_x + a_y b_y + a_z b_z",
                       ["Multiply matching components and add; the result is a SCALAR."],
                       ["The dot product is 0 exactly when the vectors are perpendicular."]),
    # --- discrete / combinatorics --------------------------------------------------------------------
    "factorial": ("n! = 1 \\times 2 \\times 3 \\times ... \\times n",
                  ["The product of every positive integer up to \\(n\\)."],
                  ["By definition \\(0! = 1\\)."]),
    "permutations": ("P(n,r) = \\frac{n!}{(n-r)!}",
                     ["Number of ways to ARRANGE \\(r\\) of \\(n\\) items (order matters)."],
                     ["Requires \\(0 \\leq r \\leq n\\)."]),
    "combinations": ("C(n,r) = \\frac{n!}{r!(n-r)!}",
                     ["Number of ways to CHOOSE \\(r\\) of \\(n\\) items (order does not matter)."],
                     ["Requires \\(0 \\leq r \\leq n\\); \\(C(n,0) = C(n,n) = 1\\)."]),
    # --- chemistry -----------------------------------------------------------------------------------
    "percent_yield": ("\\frac{actual}{theoretical} \\times 100",
                      ["\\(actual\\): mass obtained.  \\(theoretical\\): maximum possible mass."],
                      ["Normally 0–100%; a value above 100% signals impurity or measurement error."]),
    "moles_from_mass": ("n = \\frac{m}{M}", ["\\(m\\): mass.  \\(M\\): molar mass."],
                        ["\\(M\\) comes from the periodic table for the substance."]),
    "mole_fraction": ("x_A = \\frac{n_A}{n_A + n_B}", ["\\(n_A, n_B\\): moles of each component."],
                      ["Mole fractions lie between 0 and 1 and sum to 1 (\\(x_A + x_B = 1\\))."]),
    "moles_ideal_gas": ("n = \\frac{PV}{RT}",
                        ["\\(P\\): pressure.  \\(V\\): volume.  \\(R\\): gas constant.  \\(T\\): temperature."],
                        ["\\(T\\) must be in KELVIN."]),
    "percent_composition": ("\\frac{m_{element}}{m_{total}} \\times 100",
                            ["\\(m_{element}\\): mass of the element.  \\(m_{total}\\): mass of the compound."],
                            ["The percent compositions of all elements sum to 100%."]),
    "ph_poh": ("pOH = 14 - pH", ["\\(pH\\): acidity measure."],
               ["\\(pH + pOH = 14\\) holds at 25°C."]),
    "boyles_law": ("V_2 = \\frac{P_1 V_1}{P_2}",
                   ["At constant temperature, pressure and volume are INVERSELY related."],
                   ["Holds at constant temperature and amount of gas (\\(P_1 V_1 = P_2 V_2\\))."]),
    "charles_law": ("V_2 = \\frac{V_1 T_2}{T_1}",
                    ["At constant pressure, volume is proportional to temperature."],
                    ["\\(T\\) must be in KELVIN."]),
    "combined_gas_law": ("V_2 = \\frac{P_1 V_1 T_2}{T_1 P_2}",
                         ["Combines Boyle's and Charles's laws for a fixed amount of gas."],
                         ["All temperatures must be in KELVIN."]),
    "mass_from_density": ("m = \\rho V", ["\\(\\rho\\): density.  \\(V\\): volume."],
                          ["Rearranges \\(\\rho = m/V\\)."]),
    # --- statistics ----------------------------------------------------------------------------------
    "median_range": ("range = max - min",
                     ["Median = the middle of the SORTED data (average the two middle values for an even count).",
                      "Range = maximum minus minimum."],
                     ["The range uses only the two extremes, so a single outlier can inflate it."]),
    "covariance": ("\\frac{\\sum (x_i - \\mu_x)(y_i - \\mu_y)}{n}",
                   ["\\(\\mu_x, \\mu_y\\): the means of each dataset."],
                   ["Positive → the variables tend to move together; negative → oppositely."]),
    "coefficient_of_variation": ("CV = \\frac{\\sigma}{\\mu} \\times 100",
                                 ["\\(\\sigma\\): standard deviation.  \\(\\mu\\): mean.  A relative spread (%)."],
                                 ["Undefined when the mean is 0; lets you compare spread across different scales."]),
    "mean_absolute_deviation": ("\\frac{\\sum |x_i - \\mu|}{n}",
                                ["The AVERAGE distance of the values from the mean \\(\\mu\\)."],
                                ["Uses absolute values, so it is never negative; 0 means no spread."]),
    "root_mean_square": ("RMS = \\sqrt{\\frac{\\sum x_i^2}{n}}",
                         ["The 'quadratic mean' — square, average, then take the root."],
                         ["Always \\(\\geq\\) the ordinary mean's magnitude; never negative."]),
    "percent_error": ("\\frac{|measured - actual|}{actual} \\times 100",
                      ["\\(measured\\): your value.  \\(actual\\): the true value."],
                      ["Undefined when the true value is 0."]),
    "probability_simple": ("P = \\frac{favorable}{favorable + unfavorable}",
                           ["Favorable outcomes over the total (equally-likely outcomes)."],
                           ["Always between 0 (impossible) and 1 (certain)."]),
}

for _spec in ALL_SPECS:
    if not _spec.canonical_latex and _spec.slug in _GROUNDING:
        _spec.canonical_latex, _notes, _edges = _GROUNDING[_spec.slug]
        _spec.canonical_notes = list(_notes)
        _spec.edge_cases = list(_edges)
