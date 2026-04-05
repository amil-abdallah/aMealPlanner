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
- requests — HTTP calls to Spoonacular and Kroger APIs
- python-dotenv — load API keys from .env file
- pytest — unit testing each module independently
- dataclasses — structured data objects for profiles, recipes, ingredients

## Testing
- Framework: pytest

## Maintenance log

| Date | Mistake | Rule added |
|------|---------|------------|
| | | |

---
_Update this file whenever: a new library is added, the AI makes a corrected
mistake, a new convention is established, or project scope changes._
