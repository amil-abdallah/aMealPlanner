# ──────────────────────────────────────────────
# INPUT BLOCK — hardcoded test inputs
# ──────────────────────────────────────────────
TEST_INPUT_METRIC = {
    "name": "Amil",
    "age": 28,
    "weight_kg": 82.0,
    "height_cm": 178.0,
    "sex": "male",           # "male" | "female"
    "activity_level": 1.55,  # sedentary=1.2, light=1.375, moderate=1.55, active=1.725, very_active=1.9
    "goal": "cut",           # "cut" | "maintain" | "bulk"
    "meals_per_day": 3,
    "units": "metric",       # "metric" | "imperial"
}

TEST_INPUT_IMPERIAL = {
    "name": "Amil",
    "age": 28,
    "weight_kg": 181.0,      # lbs when units="imperial"
    "height_cm": 70.0,       # inches when units="imperial"
    "sex": "male",
    "activity_level": 1.55,
    "goal": "cut",
    "meals_per_day": 3,
    "units": "imperial",
}
# ──────────────────────────────────────────────

from dataclasses import dataclass


@dataclass
class UserProfile:
    """Structured representation of a user's physical stats and dietary goal."""

    name: str
    age: int
    weight_kg: float
    height_cm: float
    sex: str
    activity_level: float
    goal: str
    meals_per_day: int
    tdee: float
    target_calories: float
    target_protein_g: float
    target_fat_g: float
    target_carbs_g: float


def imperial_to_metric(weight: float, height: float) -> tuple[float, float]:
    """Convert imperial weight (lbs) and height (inches) to kg and cm.

    Args:
        weight: Body weight in pounds.
        height: Height in inches.

    Returns:
        (weight_kg, height_cm) as a tuple.
    """
    return weight * 0.453592, height * 2.54


def _calculate_bmr(weight_kg: float, height_cm: float, age: int, sex: str) -> float:
    """Return Basal Metabolic Rate using the Mifflin-St Jeor equation."""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if sex == "male" else base - 161


def _apply_goal_adjustment(tdee: float, goal: str) -> float:
    """Return target calories after applying a deficit or surplus based on goal."""
    adjustments = {"cut": -500, "maintain": 0, "bulk": +300}
    if goal not in adjustments:
        raise ValueError(f"Invalid goal '{goal}'. Must be one of: {list(adjustments)}")
    return tdee + adjustments[goal]


def _calculate_macros(
    target_calories: float, weight_kg: float, goal: str
) -> tuple[float, float, float]:
    """Return (protein_g, fat_g, carbs_g) split based on goal.

    Protein is set by body weight; fat is 25% of calories; carbs fill the rest.
    """
    protein_multipliers = {"cut": 2.2, "maintain": 1.8, "bulk": 2.0}
    protein_g = weight_kg * protein_multipliers[goal]
    fat_g = (target_calories * 0.25) / 9
    carbs_g = (target_calories - protein_g * 4 - fat_g * 9) / 4
    return protein_g, fat_g, carbs_g


def build_profile(
    name: str,
    age: int,
    weight_kg: float,
    height_cm: float,
    sex: str,
    activity_level: float,
    goal: str,
    meals_per_day: int,
    units: str = "metric",
) -> UserProfile:
    """Build and return a validated UserProfile with computed TDEE and macros.

    Args:
        name: Display name for the user.
        age: Age in years.
        weight_kg: Body weight in kg, or lbs when units="imperial".
        height_cm: Height in cm, or inches when units="imperial".
        sex: Biological sex — "male" or "female".
        activity_level: PAL multiplier (1.2–1.9).
        goal: Dietary goal — "cut", "maintain", or "bulk".
        meals_per_day: How many meals to split the daily calories across.
        units: Unit system for weight/height — "metric" (default) or "imperial".

    Returns:
        A fully populated UserProfile dataclass. Weight/height are always stored
        in metric (kg / cm) regardless of input units.
    """
    if units not in ("metric", "imperial"):
        raise ValueError(f"Invalid units '{units}'. Must be 'metric' or 'imperial'.")
    if sex not in ("male", "female"):
        raise ValueError(f"Invalid sex '{sex}'. Must be 'male' or 'female'.")
    if meals_per_day < 1:
        raise ValueError("meals_per_day must be at least 1.")

    if units == "imperial":
        weight_kg, height_cm = imperial_to_metric(weight_kg, height_cm)

    bmr = _calculate_bmr(weight_kg, height_cm, age, sex)
    tdee = bmr * activity_level
    target_calories = _apply_goal_adjustment(tdee, goal)
    protein_g, fat_g, carbs_g = _calculate_macros(target_calories, weight_kg, goal)

    return UserProfile(
        name=name,
        age=age,
        weight_kg=weight_kg,
        height_cm=height_cm,
        sex=sex,
        activity_level=activity_level,
        goal=goal,
        meals_per_day=meals_per_day,
        tdee=round(tdee, 1),
        target_calories=round(target_calories, 1),
        target_protein_g=round(protein_g, 1),
        target_fat_g=round(fat_g, 1),
        target_carbs_g=round(carbs_g, 1),
    )


def print_profile(profile: UserProfile) -> None:
    """Print a human-readable summary of a UserProfile to stdout."""
    per_meal_cal = profile.target_calories / profile.meals_per_day
    sep = "-" * 40
    print(f"\n{sep}")
    print(f"  User Profile - {profile.name}")
    print(sep)
    print(f"  Age / Sex:        {profile.age} / {profile.sex}")
    print(f"  Weight / Height:  {profile.weight_kg} kg / {profile.height_cm} cm")
    print(f"  Goal:             {profile.goal}  |  Activity: {profile.activity_level}")
    print(f"  TDEE:             {profile.tdee} kcal")
    print(f"  Target calories:  {profile.target_calories} kcal/day")
    print(f"  Per meal (~{profile.meals_per_day}):   {per_meal_cal:.0f} kcal")
    print(f"  Protein:          {profile.target_protein_g} g")
    print(f"  Fat:              {profile.target_fat_g} g")
    print(f"  Carbs:            {profile.target_carbs_g} g")
    print(f"{sep}\n")


if __name__ == "__main__":
    print("-- Metric input --")
    profile_metric = build_profile(**TEST_INPUT_METRIC)
    print_profile(profile_metric)

    print("-- Imperial input (181 lbs / 70 in) --")
    profile_imperial = build_profile(**TEST_INPUT_IMPERIAL)
    print_profile(profile_imperial)
