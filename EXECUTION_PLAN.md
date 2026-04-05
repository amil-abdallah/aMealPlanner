# Execution Plan — meal-planner

## Purpose
A meal planning engine that matches recipes to user macro and calorie targets, scores and optimizes meal plans by cost, nutrition fit, effort, and goal type, and generates smart shopping lists with perishability classification and purchase scheduling.

## Tech Stack

| Layer          | Choice               |
|----------------|----------------------|
| Language       | Python               |
| Framework      | none          |
| Package manager| pip                |
| Test framework | pytest            |
| Deployment     | local         |
| Dev OS         | Windows     |

---

## Prerequisites

- **Python 3.11+** — [python.org/downloads](https://www.python.org/downloads/)
- **pip** (bundled with Python)
- **Repomix** — `npm install -g repomix`
- **Git** — [git-scm.com](https://git-scm.com/)

---

## Setup Steps

1. `python -m venv .venv`
2. `.venv\Scripts\activate`
3. `pip install requests python-dotenv pytest`
4. `pip freeze > requirements.txt`
5. `cp .env.example .env`
6. `python src/modules/profile.py`
7. `python src/modules/recipes.py`
8. `python src/modules/pricing.py`
9. `python src/modules/optimizer.py`
10. `python src/modules/shopping_list.py`
11. `python src/main.py`

---

## Project Structure

```
meal-planner/
├── CLAUDE.md                  ← AI session rules (always attach this)
├── EXECUTION_PLAN.md          ← this file
├── .claude/
│   ├── review-security.md     ← /review-security prompt
│   ├── review-architecture.md ← /review-architecture prompt
│   └── review-quality.md      ← /review-quality prompt
├── .repomix/
│   ├── backend.json           → ctx backend
│   ├── frontend.json          → ctx frontend
│   └── full.json              → ctx full
├── src/core/                  ← core logic
├── src/
├── ctx.bat / ctx.sh           ← repomix shortcuts
└── .gitignore
```

---

## Development Workflow

1. Write code in `src/core/`
2. Run `ctx full` to snapshot the codebase for your AI session
3. Attach `CLAUDE.md` + `repomix-output.xml` to Claude
4. Implement the next feature with Claude's help
5. Run tests: `pytest`
6. If Claude makes a mistake, log it in `CLAUDE.md` → Maintenance log
7. Repeat

---

## Claude AI Context Workflow

```bash
# Snapshot the full codebase (compressed)
ctx full

# Or just the backend
ctx backend

# Or just the frontend
ctx frontend
```

Then in your Claude session:
1. Attach `CLAUDE.md` — this gives Claude your project rules
2. Attach `repomix-output.xml` — this gives Claude a snapshot of your code
3. Describe what you want to build next

---

## Running Tests

```bash
pytest
```

---

## Deployment

Target: **local**

_No deployment target set. Update this section when you decide where to deploy._

---

## Milestones

### Phase 1 — User Profile `src/modules/profile.py` ✅
**Goal:** Capture user stats and compute daily calorie + macro targets.

- [x] `UserProfile` dataclass (name, age, weight, height, sex, activity, goal, meals/day)
- [x] BMR via Mifflin-St Jeor equation
- [x] TDEE = BMR × activity level
- [x] Goal adjustment: cut −500 kcal / maintain / bulk +300 kcal
- [x] Macro split: protein by bodyweight × multiplier, fat 25% of kcals, carbs remainder
- [x] Imperial input support (lbs / inches → kg / cm conversion)
- [x] `print_profile()` human-readable output

**Deliverable:** `build_profile(**inputs)` returns a fully populated `UserProfile`.

---

### Phase 2 — Recipe Fetching `src/modules/recipes.py` ✅
**Goal:** Query Spoonacular API for recipes that fit the user's macro targets.

- [x] Load `SPOONACULAR_API_KEY` from `.env`
- [x] `fetch_recipes(profile: UserProfile, n: int) -> list[Recipe]` — calls `/recipes/findByNutrients` with ±25% per-meal macro bounds
- [x] `_parse_recipe(raw: dict) -> Recipe` dataclass (id, title, calories, protein_g, fat_g, carbs_g, ingredients, ready_in_minutes)
- [x] Macro fit score: 0–1 score per recipe based on deviation from per-meal targets
- [x] `print_recipes()` human-readable output
- [x] `.env.example` created with all API key slots

**Deliverable:** Given a `UserProfile`, return a ranked list of `Recipe` dataclasses.

---

### Phase 3 — Ingredient Pricing `src/modules/pricing.py` ✅
**Goal:** Look up real ingredient prices from the Kroger API.

- [x] Load `KROGER_CLIENT_ID` + `KROGER_CLIENT_SECRET` from `.env`
- [x] OAuth2 client-credentials token fetch with module-level caching (refreshes 60s before expiry)
- [x] `fetch_price(ingredient, token) -> PricedIngredient` dataclass (name, brand, unit, price_usd, found)
- [x] `fetch_prices(ingredients, zip_code) -> PricingResult` — batch lookup with zip-based store resolution
- [x] Graceful fallback when an ingredient is not found (warns, sets found=False, continues)
- [x] `print_prices()` human-readable output grouped by found / not found

**Deliverable:** Given a list of ingredient names, return a `PricingResult` with per-item prices and an estimated total.

---

### Phase 4 — Meal Plan Optimizer `src/modules/optimizer.py` ✅
**Goal:** Score and select the best combination of recipes for a full day/week.

- [x] `score_recipe(recipe, profile, ingredient_prices) -> ScoredRecipe` — weighted composite score across nutrition fit, protein density, cost, and effort
- [x] `build_meal_plan(recipes, profile, ingredient_prices, days) -> MealPlan` — cycles ranked recipes across days × meals_per_day slots for variety
- [x] Goal-type weighting via `GOAL_WEIGHTS`: cut prioritizes nutrition fit, bulk prioritizes protein density, maintain balances all three
- [x] `DayPlan` and `MealPlan` dataclasses with daily + weekly calorie/macro totals and estimated cost
- [x] `estimate_recipe_cost()` helper sums ingredient prices from pricing module output
- [x] `print_meal_plan()` human-readable day-by-day output with weekly summary
- [x] Added `ready_in_minutes: int = 0` to `Recipe` in recipes.py (TheMealDB omits cook time; 0 → neutral effort score)

**Deliverable:** `build_meal_plan()` returns a scored `MealPlan` with daily recipe assignments and weekly totals.

---

### Phase 5 — Shopping List `src/modules/shopping_list.py` ⬜
**Goal:** Generate a smart shopping list with perishability classification and purchase scheduling.

- [ ] Aggregate ingredients across the full `MealPlan`
- [ ] `classify_perishability(ingredient: str) -> str` — "fresh" / "refrigerated" / "pantry" categories
- [ ] `schedule_purchases(meal_plan: MealPlan) -> ShoppingList` dataclass — split fresh items into mid-week restock vs. single haul
- [ ] Attach prices from Phase 3 and compute total estimated cost
- [ ] `print_shopping_list()` human-readable output grouped by category

**Deliverable:** `schedule_purchases()` returns a `ShoppingList` ready to hand to a user.

---

### Phase 6 — Main Pipeline `src/main.py` ⬜
**Goal:** Wire all modules into a single end-to-end runnable script.

- [ ] Accept user inputs (from `TEST_INPUT` block or future CLI/Streamlit args)
- [ ] Call: `build_profile` → `fetch_recipes` → `fetch_price` → `build_meal_plan` → `schedule_purchases`
- [ ] Print full summary: profile → meal plan → shopping list → estimated cost
- [ ] Keep UI logic isolated here so Streamlit can replace `main.py` without touching modules

**Deliverable:** `python src/main.py` produces a complete, readable meal plan + shopping list.

---
_Update this file whenever your stack or deployment target changes._
_Generated by Claude Project Scaffold v2.0_
