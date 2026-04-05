# ──────────────────────────────────────────────────────────────────────────────
# RECIPE SOURCE ARCHITECTURE — fallback order
#
#   1. TheMealDB  → free, no key — recipe names, instructions, ingredient lists
#   2. USDA FoodData Central → enriches each ingredient with real macro data
#   3. Claude API (anthropic) → fallback when TheMealDB returns no good match;
#                               generates a custom recipe suited to the profile
#
# Flow:
#   fetch_recipes(profile)
#     └─ search_mealdb()         — get candidate recipes + ingredient names
#         └─ enrich_with_usda()  — look up macros per ingredient via USDA
#             └─ score & filter  — discard recipes below MIN_FIT_SCORE
#                 └─ (if empty)  generate_with_claude()  — AI fallback
# ──────────────────────────────────────────────────────────────────────────────

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
TEST_SEARCH_QUERY = "chicken"   # TheMealDB search term
TEST_N_RESULTS = 5
# ──────────────────────────────────────────────

import json
import os
from dataclasses import dataclass, field

import anthropic
import requests
from dotenv import find_dotenv, load_dotenv

from profile import UserProfile

load_dotenv(find_dotenv())

# ── API base URLs ──────────────────────────────
MEALDB_BASE  = "https://www.themealdb.com/api/json/v1/1"
USDA_BASE    = "https://api.nal.usda.gov/fdc/v1"

MACRO_TOLERANCE = 0.25  # ±25% band around per-meal macro targets
MIN_FIT_SCORE   = 0.40  # recipes below this trigger the Claude fallback


@dataclass
class Recipe:
    """Structured representation of a single recipe with nutrition and metadata."""

    id: str
    title: str
    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float
    ingredients: list[str]
    instructions: str
    source: str          # "mealdb" | "claude"
    macro_fit_score: float = 0.0


# ── Shared helpers ─────────────────────────────

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
        (recipe.calories,   targets["calories"]),
        (recipe.protein_g,  targets["protein"]),
        (recipe.fat_g,      targets["fat"]),
        (recipe.carbs_g,    targets["carbs"]),
    ]
    scores = []
    for actual, target in fields:
        if target == 0:
            scores.append(1.0)
            continue
        deviation = abs(actual - target) / target
        scores.append(max(0.0, 1.0 - deviation / MACRO_TOLERANCE))
    return round(sum(scores) / len(scores), 3)


# ── Source 1: TheMealDB ────────────────────────

def search_mealdb(query: str) -> list[dict]:
    """Search TheMealDB for recipes matching a keyword.

    Args:
        query: Ingredient or dish keyword (e.g. "chicken", "salmon").

    Returns:
        List of raw meal dicts from TheMealDB, or empty list if none found.

    Raises:
        requests.HTTPError: If the API returns a non-2xx response.
    """
    response = requests.get(f"{MEALDB_BASE}/search.php", params={"s": query})
    response.raise_for_status()
    data = response.json()
    return data.get("meals") or []


def _extract_ingredients(raw: dict) -> list[str]:
    """Extract non-empty ingredient names from a TheMealDB meal dict."""
    ingredients = []
    for i in range(1, 21):
        name = (raw.get(f"strIngredient{i}") or "").strip()
        if name:
            ingredients.append(name)
    return ingredients


def _parse_mealdb_recipe(raw: dict, macros: dict[str, float], targets: dict[str, float]) -> Recipe:
    """Combine a TheMealDB meal dict with USDA-derived macros into a Recipe.

    Args:
        raw: Single meal dict from TheMealDB search response.
        macros: Aggregated nutrition totals from USDA enrichment.
        targets: Per-meal macro targets used to compute the fit score.

    Returns:
        A Recipe dataclass with macro_fit_score populated.
    """
    recipe = Recipe(
        id=raw["idMeal"],
        title=raw["strMeal"],
        calories=macros.get("calories", 0.0),
        protein_g=macros.get("protein", 0.0),
        fat_g=macros.get("fat", 0.0),
        carbs_g=macros.get("carbs", 0.0),
        ingredients=_extract_ingredients(raw),
        instructions=(raw.get("strInstructions") or "").strip(),
        source="mealdb",
    )
    recipe.macro_fit_score = _macro_fit_score(recipe, targets)
    return recipe


# ── Source 2: USDA FoodData Central ───────────

def _lookup_usda_macros(ingredient: str, api_key: str) -> dict[str, float]:
    """Fetch macro totals for one ingredient from USDA FoodData Central.

    Returns a dict with keys calories, protein, fat, carbs (per 100 g serving).
    Returns zeros if the ingredient is not found or the key is missing.

    Args:
        ingredient: Plain ingredient name, e.g. "chicken breast".
        api_key: USDA_API_KEY from environment.

    Raises:
        requests.HTTPError: If the API returns a non-2xx response.
    """
    response = requests.get(
        f"{USDA_BASE}/foods/search",
        params={"query": ingredient, "pageSize": 1, "api_key": api_key},
    )
    response.raise_for_status()
    foods = response.json().get("foods", [])
    if not foods:
        return {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}

    nutrients = {n["nutrientName"]: n["value"] for n in foods[0].get("foodNutrients", [])}
    return {
        "calories": nutrients.get("Energy", 0.0),
        "protein":  nutrients.get("Protein", 0.0),
        "fat":      nutrients.get("Total lipid (fat)", 0.0),
        "carbs":    nutrients.get("Carbohydrate, by difference", 0.0),
    }


def enrich_with_usda(ingredients: list[str], api_key: str) -> dict[str, float]:
    """Aggregate USDA macro data across all ingredients in a recipe.

    Sums per-100g values for each ingredient as a rough total macro estimate.
    Ingredients not found in USDA are skipped (contribute zero).

    Args:
        ingredients: List of ingredient name strings from TheMealDB.
        api_key: USDA_API_KEY from environment.

    Returns:
        Dict with total calories, protein, fat, carbs across all ingredients.
    """
    totals: dict[str, float] = {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}
    for ingredient in ingredients:
        macros = _lookup_usda_macros(ingredient, api_key)
        for key in totals:
            totals[key] += macros[key]
    return {k: round(v, 1) for k, v in totals.items()}


# ── Source 3: Claude API fallback ─────────────

def generate_with_claude(profile: UserProfile, targets: dict[str, float]) -> Recipe:
    """Generate a custom recipe using the Claude API when no DB match is found.

    Prompts Claude to return a JSON recipe tailored to the user's per-meal
    macro targets and dietary goal. Used only when TheMealDB + USDA produce
    no recipe above MIN_FIT_SCORE.

    Args:
        profile: The user's profile for goal and macro context.
        targets: Per-meal calorie and macro targets.

    Returns:
        A Recipe dataclass with source="claude".

    Raises:
        EnvironmentError: If ANTHROPIC_API_KEY is not set.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set in environment.")

    client = anthropic.Anthropic(api_key=api_key)

    prompt = (
        f"Create a single meal recipe for a {profile.goal} goal. "
        f"Target per meal: {targets['calories']:.0f} kcal, "
        f"{targets['protein']:.0f}g protein, {targets['fat']:.0f}g fat, "
        f"{targets['carbs']:.0f}g carbs. "
        "Respond with ONLY a JSON object using these exact keys: "
        "title (string), calories (number), protein_g (number), fat_g (number), "
        "carbs_g (number), ingredients (array of strings), instructions (string). "
        "No markdown, no explanation — raw JSON only."
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    data = json.loads(message.content[0].text)
    recipe = Recipe(
        id="claude-generated",
        title=data["title"],
        calories=data["calories"],
        protein_g=data["protein_g"],
        fat_g=data["fat_g"],
        carbs_g=data["carbs_g"],
        ingredients=data["ingredients"],
        instructions=data["instructions"],
        source="claude",
    )
    recipe.macro_fit_score = _macro_fit_score(recipe, targets)
    return recipe


# ── Orchestrator ───────────────────────────────

def fetch_recipes(profile: UserProfile, query: str, n: int = 10) -> list[Recipe]:
    """Return recipes matching the user's macro targets using the three-source stack.

    Fallback order:
      1. TheMealDB search → USDA macro enrichment → score and filter
      2. Claude API generation if no recipe clears MIN_FIT_SCORE

    Args:
        profile: A populated UserProfile with calorie and macro targets.
        query: Keyword forwarded to TheMealDB search (e.g. "chicken").
        n: Maximum number of recipes to return from TheMealDB results.

    Returns:
        List of Recipe dataclasses sorted by macro_fit_score descending.
        Always returns at least one recipe (Claude fallback guarantees this).

    Raises:
        EnvironmentError: If USDA_API_KEY is not set.
        requests.HTTPError: If any API returns a non-2xx response.
    """
    usda_key = os.getenv("USDA_API_KEY")
    if not usda_key:
        raise EnvironmentError("USDA_API_KEY is not set in environment.")

    targets = _per_meal_targets(profile)

    # Source 1 — TheMealDB
    raw_meals = search_mealdb(query)[:n]

    # Source 2 — USDA enrichment
    recipes: list[Recipe] = []
    for raw in raw_meals:
        ingredients = _extract_ingredients(raw)
        macros = enrich_with_usda(ingredients, usda_key)
        recipe = _parse_mealdb_recipe(raw, macros, targets)
        if recipe.macro_fit_score >= MIN_FIT_SCORE:
            recipes.append(recipe)

    # Source 3 — Claude fallback
    if not recipes:
        recipes = [generate_with_claude(profile, targets)]

    return sorted(recipes, key=lambda r: r.macro_fit_score, reverse=True)


def print_recipes(recipes: list[Recipe], profile: UserProfile) -> None:
    """Print a human-readable ranked list of recipes to stdout."""
    targets = _per_meal_targets(profile)
    sep = "-" * 52
    print(f"\n{sep}")
    print(f"  Recipes for {profile.name} | goal: {profile.goal}")
    print(f"  Per-meal targets: {targets['calories']:.0f} kcal | "
          f"P {targets['protein']:.0f}g | F {targets['fat']:.0f}g | C {targets['carbs']:.0f}g")
    print(sep)
    for i, r in enumerate(recipes, 1):
        source_tag = f"[{r.source}]"
        print(f"  {i}. {r.title} {source_tag}")
        print(f"     {r.calories:.0f} kcal | P {r.protein_g:.0f}g | "
              f"F {r.fat_g:.0f}g | C {r.carbs_g:.0f}g | fit: {r.macro_fit_score:.2f}")
        if r.ingredients:
            preview = ", ".join(r.ingredients[:5])
            suffix = " ..." if len(r.ingredients) > 5 else ""
            print(f"     Ingredients: {preview}{suffix}")
    print(f"{sep}\n")


if __name__ == "__main__":
    recipes = fetch_recipes(TEST_PROFILE, query=TEST_SEARCH_QUERY, n=TEST_N_RESULTS)
    print_recipes(recipes, TEST_PROFILE)
