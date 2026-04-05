# CLAUDE.md

## Project purpose
A meal planning engine that matches recipes to user macro and calorie targets, scores and optimizes meal plans by cost, nutrition fit, effort, and goal type, and generates smart shopping lists with perishability classification and purchase scheduling.

## Environment
- Language / runtime: Python
- Framework: none
- Local dev OS: Windows
- Deployment target: local
- Package manager: pip

## Project structure
- Backend / core logic: src/core/, src/modules/
- Frontend / UI: src/

## Code conventions
- Use type hints on all functions
- Keep functions under 50 lines — split larger logic into helpers
- Each module lives in its own file and does one thing
- Hardcoded test inputs go at the top of each script under a clearly marked INPUT BLOCK comment

## Always
- ALWAYS use environment variables for API keys because hardcoded secrets get committed
- ALWAYS return structured dicts or dataclasses from every function because raw strings break downstream modules
- ALWAYS print human-readable output at the end of every script because this is a proof of concept and results must be readable
- ALWAYS write a docstring on every function because the codebase will grow and context gets lost

## Never
- NEVER catch bare exceptions because it hides bugs and makes API failures silent
- NEVER commit .env files because they contain API secrets
- NEVER mix UI logic with core logic because Step 2 will swap in Streamlit without rewriting modules
- NEVER hardcode prices or macro values as final answers because they must come from APIs or user input

## Key dependencies
- requests — HTTP calls to TheMealDB, USDA FoodData Central, and Kroger APIs
- python-dotenv — load API keys from .env file
- pytest — unit testing each module independently
- dataclasses — structured data objects for profiles, recipes, ingredients
- anthropic — Claude API SDK for fallback recipe generation

## API stack
| Service | Purpose | Auth |
|---------|---------|------|
| TheMealDB (themealdb.com/api.php) | Recipe names, instructions, ingredient lists | None — free, no key |
| USDA FoodData Central (api.nal.usda.gov) | Macro data per ingredient (protein, carbs, fat, calories) | USDA_API_KEY |
| Claude API (anthropic SDK) | Custom recipe generation when DB results don't fit profile | ANTHROPIC_API_KEY |
| Kroger API (developer.kroger.com) | Real-time local grocery pricing by zip code | KROGER_CLIENT_ID + KROGER_CLIENT_SECRET |

## Kroger API environments
| Environment | Base URL | Credentials | When to use |
|-------------|----------|-------------|-------------|
| Certification | `https://api-ce.kroger.com/v1` | Cert client ID + secret | Development and testing — limited inventory, prices often $0.00 |
| Production | `https://api.kroger.com/v1` | Prod client ID + secret | Live deployment only — requires Kroger production approval |

**Current environment:** Certification (`KROGER_BASE` in `src/modules/pricing.py`)

To switch to production: update `KROGER_BASE` in `pricing.py` and replace
`KROGER_CLIENT_ID` / `KROGER_CLIENT_SECRET` in `.env` with production credentials.

## Testing
- Framework: pytest

## Maintenance log

| Date | Mistake | Rule added |
|------|---------|------------|
| | | |

---
_Update this file whenever: a new library is added, the AI makes a corrected
mistake, a new convention is established, or project scope changes._
