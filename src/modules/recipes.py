# ──────────────────────────────────────────────
# INPUT BLOCK — hardcoded test inputs
# ──────────────────────────────────────────────
from profile import build_profile

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
TEST_N_RESULTS = 5
# ──────────────────────────────────────────────

import os
from dataclasses import dataclass, field

import requests
from dotenv import load_dotenv

from profile import UserProfile

load_dotenv()

SPOONACULAR_BASE = "https://api.spoonacular.com"
MACRO_TOLERANCE = 0.25  # ±25% band around per-meal macro targets


@dataclass
class Recipe:
    """Structured representation of a single recipe with nutrition and metadata."""

    id: int
    title: str
    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float
    ingredients: list[str]
    ready_in_minutes: int
    macro_fit_score: float = 0.0


def _per_meal_targets(profile: UserProfile) -> dict[str, float]:
    """Return calorie and macro targets divided by meals_per_day."""
    return {
        "calories": profile.target_calories / profile.meals_per_day,
        "protein":  profile.target_protein_g / profile.meals_per_day,
        "fat":      profile.target_fat_g / profile.meals_per_day,
        "carbs":    profile.target_carbs_g / profile.meals_per_day,
    }


def _macro_fit_score(recipe: Recipe, targets: dict[str, float]) -> float:
    """Return a 0–1 score reflecting how closely a recipe hits per-meal macro targets.

    Each macro contributes equally. A perfect match scores 1.0; deviations beyond
    MACRO_TOLERANCE reduce the score proportionally, floored at 0.
    """
    fields = [
        (recipe.calories, targets["calories"]),
        (recipe.protein_g, targets["protein"]),
        (recipe.fat_g, targets["fat"]),
        (recipe.carbs_g, targets["carbs"]),
    ]
    scores = []
    for actual, target in fields:
        if target == 0:
            scores.append(1.0)
            continue
        deviation = abs(actual - target) / target
        scores.append(max(0.0, 1.0 - deviation / MACRO_TOLERANCE))
    return round(sum(scores) / len(scores), 3)


def _parse_recipe(raw: dict, targets: dict[str, float]) -> Recipe:
    """Parse a raw Spoonacular API result dict into a Recipe dataclass.

    Args:
        raw: Single item from the Spoonacular findByNutrients response.
        targets: Per-meal macro targets used to compute the fit score.

    Returns:
        A Recipe dataclass with macro_fit_score populated.
    """
    recipe = Recipe(
        id=raw["id"],
        title=raw["title"],
        calories=raw.get("calories", 0),
        protein_g=raw.get("protein", 0),
        fat_g=raw.get("fat", 0),
        carbs_g=raw.get("carbs", 0),
        ingredients=[i["name"] for i in raw.get("usedIngredients", []) + raw.get("missedIngredients", [])],
        ready_in_minutes=raw.get("readyInMinutes", 0),
    )
    recipe.macro_fit_score = _macro_fit_score(recipe, targets)
    return recipe


def fetch_recipes(profile: UserProfile, n: int = 10) -> list[Recipe]:
    """Fetch recipes from Spoonacular that fit the user's per-meal macro targets.

    Queries /recipes/findByNutrients with ±MACRO_TOLERANCE bounds around each
    per-meal target. Results are sorted by macro fit score descending.

    Args:
        profile: A populated UserProfile with calorie and macro targets.
        n: Maximum number of recipes to return.

    Returns:
        List of Recipe dataclasses sorted by macro_fit_score descending.

    Raises:
        EnvironmentError: If SPOONACULAR_API_KEY is not set.
        requests.HTTPError: If the API returns a non-2xx response.
    """
    api_key = os.getenv("SPOONACULAR_API_KEY")
    if not api_key:
        raise EnvironmentError("SPOONACULAR_API_KEY is not set in environment.")

    targets = _per_meal_targets(profile)

    def bounds(value: float) -> tuple[float, float]:
        """Return (min, max) as ±MACRO_TOLERANCE around value."""
        return value * (1 - MACRO_TOLERANCE), value * (1 + MACRO_TOLERANCE)

    cal_min, cal_max = bounds(targets["calories"])
    pro_min, pro_max = bounds(targets["protein"])
    fat_min, fat_max = bounds(targets["fat"])
    car_min, car_max = bounds(targets["carbs"])

    params = {
        "apiKey": api_key,
        "minCalories": round(cal_min),
        "maxCalories": round(cal_max),
        "minProtein":  round(pro_min),
        "maxProtein":  round(pro_max),
        "minFat":      round(fat_min),
        "maxFat":      round(fat_max),
        "minCarbs":    round(car_min),
        "maxCarbs":    round(car_max),
        "number": n,
        "ignorePantry": True,
        "fillIngredients": True,
    }

    response = requests.get(f"{SPOONACULAR_BASE}/recipes/findByNutrients", params=params)
    response.raise_for_status()

    raw_recipes = response.json()
    recipes = [_parse_recipe(r, targets) for r in raw_recipes]
    return sorted(recipes, key=lambda r: r.macro_fit_score, reverse=True)


def print_recipes(recipes: list[Recipe], profile: UserProfile) -> None:
    """Print a human-readable ranked list of recipes to stdout."""
    targets = _per_meal_targets(profile)
    sep = "-" * 50
    print(f"\n{sep}")
    print(f"  Recipes for {profile.name} | goal: {profile.goal}")
    print(f"  Per-meal targets: {targets['calories']:.0f} kcal | "
          f"P {targets['protein']:.0f}g | F {targets['fat']:.0f}g | C {targets['carbs']:.0f}g")
    print(sep)
    for i, r in enumerate(recipes, 1):
        print(f"  {i}. {r.title}")
        print(f"     {r.calories:.0f} kcal | P {r.protein_g:.0f}g | "
              f"F {r.fat_g:.0f}g | C {r.carbs_g:.0f}g | "
              f"{r.ready_in_minutes} min | fit: {r.macro_fit_score:.2f}")
        if r.ingredients:
            print(f"     Ingredients: {', '.join(r.ingredients[:5])}"
                  + (" ..." if len(r.ingredients) > 5 else ""))
    print(f"{sep}\n")


if __name__ == "__main__":
    recipes = fetch_recipes(TEST_PROFILE, n=TEST_N_RESULTS)
    print_recipes(recipes, TEST_PROFILE)
