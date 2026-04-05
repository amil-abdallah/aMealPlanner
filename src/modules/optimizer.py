# ──────────────────────────────────────────────
# INPUT BLOCK — hardcoded test inputs
# ──────────────────────────────────────────────
from profile import build_profile
from recipes import Recipe

TEST_PROFILE = build_profile(
    name="Amil",
    age=28,
    weight_kg=82.0,
    height_cm=178.0,
    sex="male",
    activity_level=1.55,
    goal="cut",
    meals_per_day=3,
)

# Simulated recipes — mirrors what fetch_recipes() returns
TEST_RECIPES = [
    Recipe(id="1", title="Grilled Chicken & Rice",     calories=620, protein_g=55, fat_g=12, carbs_g=72, ingredients=["chicken breast", "rice", "broccoli"],        instructions="", source="mealdb", macro_fit_score=0.0),
    Recipe(id="2", title="Salmon & Sweet Potato",      calories=700, protein_g=45, fat_g=22, carbs_g=68, ingredients=["salmon", "sweet potato", "spinach"],         instructions="", source="mealdb", macro_fit_score=0.0),
    Recipe(id="3", title="Turkey Meatballs & Pasta",   calories=580, protein_g=48, fat_g=14, carbs_g=65, ingredients=["ground turkey", "pasta", "tomato sauce"],    instructions="", source="mealdb", macro_fit_score=0.0),
    Recipe(id="4", title="Egg & Veggie Stir Fry",      calories=490, protein_g=38, fat_g=18, carbs_g=42, ingredients=["eggs", "bell pepper", "onion", "soy sauce"], instructions="", source="mealdb", macro_fit_score=0.0),
    Recipe(id="5", title="Tuna & Quinoa Bowl",         calories=540, protein_g=50, fat_g=10, carbs_g=60, ingredients=["tuna", "quinoa", "cucumber", "lemon"],       instructions="", source="mealdb", macro_fit_score=0.0),
    Recipe(id="6", title="Chicken Thigh & Potato",     calories=660, protein_g=52, fat_g=20, carbs_g=58, ingredients=["chicken thighs", "potato", "garlic"],        instructions="", source="mealdb", macro_fit_score=0.0),
    Recipe(id="7", title="Greek Yogurt Protein Bowl",  calories=420, protein_g=42, fat_g=8,  carbs_g=48, ingredients=["greek yogurt", "banana", "oats", "honey"],   instructions="", source="claude", macro_fit_score=0.0),
]

# Simulated ingredient prices (mirrors PricingResult.priced)
TEST_INGREDIENT_PRICES = {
    "chicken breast": 4.99,
    "rice": 2.49,
    "broccoli": 2.49,
    "salmon": 8.99,
    "sweet potato": 1.29,
    "spinach": 3.49,
    "ground turkey": 4.79,
    "pasta": 1.49,
    "tomato sauce": 1.49,
    "eggs": 3.99,
    "bell pepper": 1.29,
    "onion": 0.99,
    "soy sauce": 2.99,
    "tuna": 1.49,
    "quinoa": 4.99,
    "cucumber": 0.99,
    "lemon": 0.69,
    "chicken thighs": 3.49,
    "potato": 0.89,
    "garlic": 0.79,
    "greek yogurt": 5.99,
    "banana": 0.29,
    "oats": 3.49,
    "honey": 5.99,
}

TEST_DAYS = 7
# ──────────────────────────────────────────────

from dataclasses import dataclass, field

from profile import UserProfile
from recipes import Recipe

# ── Scoring weights by goal ────────────────────
# Each dict must sum to 1.0
# Keys: nutrition_fit, protein_density, cost, effort
GOAL_WEIGHTS: dict[str, dict[str, float]] = {
    "cut":      {"nutrition_fit": 0.55, "protein_density": 0.25, "cost": 0.10, "effort": 0.10},
    "bulk":     {"nutrition_fit": 0.25, "protein_density": 0.50, "cost": 0.10, "effort": 0.15},
    "maintain": {"nutrition_fit": 0.40, "protein_density": 0.20, "cost": 0.20, "effort": 0.20},
}

MAX_COOK_MINUTES = 60   # cook times at or above this score 0 for effort
MAX_RECIPE_COST  = 20.0 # recipe costs at or above this score 0 for cost


@dataclass
class ScoredRecipe:
    """A Recipe paired with its composite optimizer score and score breakdown."""

    recipe: Recipe
    total_score: float
    nutrition_fit: float
    protein_density: float
    cost_score: float
    effort_score: float
    estimated_cost_usd: float


@dataclass
class DayPlan:
    """One day's worth of meal assignments and nutrition totals."""

    day: int
    meals: list[Recipe] = field(default_factory=list)
    total_calories: float = 0.0
    total_protein_g: float = 0.0
    total_fat_g: float = 0.0
    total_carbs_g: float = 0.0


@dataclass
class MealPlan:
    """Full multi-day meal plan with per-day assignments and weekly totals."""

    profile: UserProfile
    days: list[DayPlan] = field(default_factory=list)
    weekly_calories: float = 0.0
    weekly_protein_g: float = 0.0
    weekly_fat_g: float = 0.0
    weekly_carbs_g: float = 0.0
    weekly_cost_usd: float = 0.0


# ── Score helpers ──────────────────────────────

def _effort_score(ready_in_minutes: int) -> float:
    """Return 0–1 score where faster cook times score higher.

    0 minutes (unknown) → 0.5 neutral. MAX_COOK_MINUTES+ → 0.0.
    """
    if ready_in_minutes <= 0:
        return 0.5
    return max(0.0, 1.0 - ready_in_minutes / MAX_COOK_MINUTES)


def _cost_score(estimated_cost: float) -> float:
    """Return 0–1 score where lower recipe cost scores higher.

    0 cost (unknown) → 0.5 neutral. MAX_RECIPE_COST+ → 0.0.
    """
    if estimated_cost <= 0:
        return 0.5
    return max(0.0, 1.0 - estimated_cost / MAX_RECIPE_COST)


def _protein_density_score(recipe: Recipe) -> float:
    """Return 0–1 score for protein as a fraction of total calories.

    Benchmarked against 40% protein calories as a high-protein ceiling.
    """
    if recipe.calories <= 0:
        return 0.0
    protein_cal_pct = (recipe.protein_g * 4) / recipe.calories
    return min(1.0, protein_cal_pct / 0.40)


def estimate_recipe_cost(recipe: Recipe, ingredient_prices: dict[str, float]) -> float:
    """Estimate the cost of a recipe by summing prices for known ingredients.

    Ingredients not present in ingredient_prices contribute zero.
    Returns the sum rounded to 2 decimal places.

    Args:
        recipe: A Recipe dataclass with an ingredients list.
        ingredient_prices: Mapping of ingredient name → price in USD.

    Returns:
        Estimated total cost in USD.
    """
    return round(sum(ingredient_prices.get(i.lower(), 0.0) for i in recipe.ingredients), 2)


def score_recipe(
    recipe: Recipe,
    profile: UserProfile,
    ingredient_prices: dict[str, float] | None = None,
) -> ScoredRecipe:
    """Compute a composite score for a recipe against a user profile.

    Weights four sub-scores (nutrition fit, protein density, cost, effort)
    according to GOAL_WEIGHTS for the user's goal type.

    Args:
        recipe: A Recipe dataclass (macro_fit_score must already be set).
        profile: The user's profile, used for goal-based weight selection.
        ingredient_prices: Optional dict of ingredient → price USD for cost scoring.
                           Missing ingredients contribute 0 cost.

    Returns:
        A ScoredRecipe with total_score and individual component scores.
    """
    weights = GOAL_WEIGHTS[profile.goal]
    prices = ingredient_prices or {}

    nutrition_fit     = recipe.macro_fit_score
    protein_density   = _protein_density_score(recipe)
    estimated_cost    = estimate_recipe_cost(recipe, prices)
    cost_sc           = _cost_score(estimated_cost)
    effort_sc         = _effort_score(recipe.ready_in_minutes)

    total = (
        weights["nutrition_fit"]    * nutrition_fit
        + weights["protein_density"] * protein_density
        + weights["cost"]            * cost_sc
        + weights["effort"]          * effort_sc
    )

    return ScoredRecipe(
        recipe=recipe,
        total_score=round(total, 4),
        nutrition_fit=round(nutrition_fit, 4),
        protein_density=round(protein_density, 4),
        cost_score=round(cost_sc, 4),
        effort_score=round(effort_sc, 4),
        estimated_cost_usd=estimated_cost,
    )


def _day_totals(meals: list[Recipe]) -> tuple[float, float, float, float]:
    """Return (calories, protein_g, fat_g, carbs_g) summed across a list of recipes."""
    return (
        round(sum(r.calories  for r in meals), 1),
        round(sum(r.protein_g for r in meals), 1),
        round(sum(r.fat_g     for r in meals), 1),
        round(sum(r.carbs_g   for r in meals), 1),
    )


def build_meal_plan(
    recipes: list[Recipe],
    profile: UserProfile,
    ingredient_prices: dict[str, float] | None = None,
    days: int = 7,
) -> MealPlan:
    """Score and assign recipes across a multi-day meal plan.

    Scores all recipes, sorts by composite score, then cycles through the
    ranked list to fill each meal slot — ensuring variety while always
    preferring higher-scored recipes.

    Args:
        recipes: Candidate recipes from fetch_recipes().
        profile: The user's profile for scoring weights and meals_per_day.
        ingredient_prices: Optional price map forwarded to score_recipe().
        days: Number of days to plan for (default 7).

    Returns:
        A MealPlan with per-day assignments, nutrition totals, and weekly totals.

    Raises:
        ValueError: If recipes list is empty.
    """
    if not recipes:
        raise ValueError("Cannot build a meal plan with no recipes.")

    scored = sorted(
        [score_recipe(r, profile, ingredient_prices) for r in recipes],
        key=lambda s: s.total_score,
        reverse=True,
    )

    total_slots = days * profile.meals_per_day
    # Cycle through scored recipes to fill all slots with variety
    assigned = [scored[i % len(scored)].recipe for i in range(total_slots)]

    plan = MealPlan(profile=profile)
    for day_num in range(1, days + 1):
        start = (day_num - 1) * profile.meals_per_day
        meals = assigned[start : start + profile.meals_per_day]
        cal, pro, fat, carb = _day_totals(meals)
        plan.days.append(DayPlan(
            day=day_num, meals=meals,
            total_calories=cal, total_protein_g=pro,
            total_fat_g=fat, total_carbs_g=carb,
        ))

    plan.weekly_calories  = round(sum(d.total_calories  for d in plan.days), 1)
    plan.weekly_protein_g = round(sum(d.total_protein_g for d in plan.days), 1)
    plan.weekly_fat_g     = round(sum(d.total_fat_g     for d in plan.days), 1)
    plan.weekly_carbs_g   = round(sum(d.total_carbs_g   for d in plan.days), 1)
    plan.weekly_cost_usd  = round(
        sum(estimate_recipe_cost(r, ingredient_prices or {}) for r in assigned), 2
    )
    return plan


def print_meal_plan(plan: MealPlan) -> None:
    """Print a human-readable meal plan with daily assignments and weekly totals."""
    p = plan.profile
    sep  = "-" * 56
    sep2 = "=" * 56
    print(f"\n{sep2}")
    print(f"  Meal Plan — {p.name} | goal: {p.goal} | {len(plan.days)} days")
    print(f"  Daily target: {p.target_calories:.0f} kcal | "
          f"P {p.target_protein_g:.0f}g | F {p.target_fat_g:.0f}g | C {p.target_carbs_g:.0f}g")
    print(sep2)
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for day in plan.days:
        label = day_names[(day.day - 1) % 7]
        print(f"\n  {label} — {day.total_calories:.0f} kcal | "
              f"P {day.total_protein_g:.0f}g | F {day.total_fat_g:.0f}g | C {day.total_carbs_g:.0f}g")
        print(f"  {sep}")
        for i, meal in enumerate(day.meals, 1):
            source_tag = f"[{meal.source}]"
            print(f"    Meal {i}: {meal.title} {source_tag}")
            print(f"            {meal.calories:.0f} kcal | P {meal.protein_g:.0f}g | "
                  f"F {meal.fat_g:.0f}g | C {meal.carbs_g:.0f}g")
    print(f"\n{sep2}")
    print(f"  Weekly totals")
    print(sep)
    print(f"  Calories:  {plan.weekly_calories:.0f} kcal  "
          f"(target {p.target_calories * len(plan.days):.0f})")
    print(f"  Protein:   {plan.weekly_protein_g:.0f} g")
    print(f"  Fat:       {plan.weekly_fat_g:.0f} g")
    print(f"  Carbs:     {plan.weekly_carbs_g:.0f} g")
    print(f"  Est. cost: ${plan.weekly_cost_usd:.2f}")
    print(f"{sep2}\n")


if __name__ == "__main__":
    # Re-score test recipes against the test profile before building the plan
    from recipes import Recipe as _R  # noqa: F401 — imported for type clarity
    targets = {
        "calories": TEST_PROFILE.target_calories / TEST_PROFILE.meals_per_day,
        "protein":  TEST_PROFILE.target_protein_g / TEST_PROFILE.meals_per_day,
        "fat":      TEST_PROFILE.target_fat_g / TEST_PROFILE.meals_per_day,
        "carbs":    TEST_PROFILE.target_carbs_g / TEST_PROFILE.meals_per_day,
    }
    # Populate macro_fit_score on each test recipe
    from recipes import _macro_fit_score
    for r in TEST_RECIPES:
        r.macro_fit_score = _macro_fit_score(r, targets)

    plan = build_meal_plan(
        TEST_RECIPES,
        TEST_PROFILE,
        ingredient_prices=TEST_INGREDIENT_PRICES,
        days=TEST_DAYS,
    )
    print_meal_plan(plan)
