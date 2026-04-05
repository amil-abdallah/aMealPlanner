# ──────────────────────────────────────────────
# INPUT BLOCK — hardcoded test inputs
# ──────────────────────────────────────────────
TEST_INGREDIENTS = [
    "chicken breast",
    "brown rice",
    "broccoli",
    "olive oil",
    "garlic",
    "this_ingredient_does_not_exist_xyz",  # intentional miss to test fallback
]
TEST_ZIP_CODE = "30301"  # Atlanta, GA — change to a zip near a Kroger
# ──────────────────────────────────────────────

import os
import time
import warnings
from dataclasses import dataclass, field

import requests
from dotenv import load_dotenv

load_dotenv()

KROGER_BASE        = "https://api.kroger.com/v1"
KROGER_TOKEN_URL   = f"{KROGER_BASE}/connect/oauth2/token"
KROGER_PRODUCTS_URL = f"{KROGER_BASE}/products"

# Cached token state — module-level so it persists across calls in a session
_token_cache: dict = {"access_token": None, "expires_at": 0.0}


@dataclass
class PricedIngredient:
    """Structured pricing result for a single ingredient from Kroger."""

    name: str
    brand: str
    unit: str
    price_usd: float
    found: bool  # False when Kroger returned no match


@dataclass
class PricingResult:
    """Aggregated pricing data for a collection of ingredients."""

    priced: list[PricedIngredient] = field(default_factory=list)
    not_found: list[str] = field(default_factory=list)
    total_usd: float = 0.0


def _get_token(client_id: str, client_secret: str) -> str:
    """Fetch a Kroger OAuth2 client-credentials token, using a cached copy if valid.

    Tokens are cached at module level and reused until 60 seconds before expiry.

    Args:
        client_id: KROGER_CLIENT_ID from environment.
        client_secret: KROGER_CLIENT_SECRET from environment.

    Returns:
        A valid Bearer token string.

    Raises:
        requests.HTTPError: If the token request fails.
    """
    now = time.time()
    if _token_cache["access_token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["access_token"]

    response = requests.post(
        KROGER_TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "scope": "product.compact",
        },
        auth=(client_id, client_secret),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    response.raise_for_status()
    payload = response.json()

    _token_cache["access_token"] = payload["access_token"]
    _token_cache["expires_at"] = now + payload.get("expires_in", 1800)
    return _token_cache["access_token"]


def _extract_price(product: dict) -> tuple[str, float]:
    """Pull the unit description and lowest available price from a Kroger product dict.

    Args:
        product: Single product object from Kroger Products API response.

    Returns:
        (unit_description, price_usd) — price is 0.0 if no pricing data present.
    """
    items = product.get("items", [])
    if not items:
        return "each", 0.0

    item = items[0]
    size = item.get("size", "each")
    price_info = item.get("price", {})
    price = price_info.get("regular", price_info.get("promo", 0.0))
    return size, float(price)


def fetch_price(ingredient: str, token: str, location_id: str | None = None) -> PricedIngredient:
    """Look up the price of one ingredient on Kroger.

    Searches by ingredient name, takes the first result. Returns a not-found
    PricedIngredient (price_usd=0.0, found=False) instead of raising when no
    match exists — allows batch operations to continue past missing items.

    Args:
        ingredient: Plain ingredient name, e.g. "chicken breast".
        token: Valid Kroger Bearer token from _get_token().
        location_id: Optional Kroger store location ID for localised pricing.

    Returns:
        A PricedIngredient dataclass. found=False when Kroger has no match.

    Raises:
        requests.HTTPError: If the API returns a non-2xx response.
    """
    params: dict = {"filter.term": ingredient, "filter.limit": 1}
    if location_id:
        params["filter.locationId"] = location_id

    response = requests.get(
        KROGER_PRODUCTS_URL,
        params=params,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    response.raise_for_status()

    products = response.json().get("data", [])
    if not products:
        warnings.warn(f"Kroger: no match for '{ingredient}' — skipping", stacklevel=2)
        return PricedIngredient(name=ingredient, brand="", unit="", price_usd=0.0, found=False)

    product = products[0]
    unit, price = _extract_price(product)
    brand = product.get("brand", "")
    return PricedIngredient(name=ingredient, brand=brand, unit=unit, price_usd=price, found=True)


def _resolve_location_id(zip_code: str, token: str) -> str | None:
    """Return the nearest Kroger location ID for a zip code, or None if not found.

    Args:
        zip_code: US zip code string, e.g. "30301".
        token: Valid Kroger Bearer token.

    Raises:
        requests.HTTPError: If the API returns a non-2xx response.
    """
    response = requests.get(
        f"{KROGER_BASE}/locations",
        params={"filter.zipCode.near": zip_code, "filter.limit": 1},
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    response.raise_for_status()
    locations = response.json().get("data", [])
    return locations[0]["locationId"] if locations else None


def fetch_prices(
    ingredients: list[str],
    zip_code: str | None = None,
) -> PricingResult:
    """Fetch Kroger prices for a list of ingredient names.

    Resolves a nearby store from zip_code if provided, then looks up each
    ingredient individually. Missing items are collected in result.not_found
    rather than raising exceptions.

    Args:
        ingredients: List of ingredient name strings.
        zip_code: Optional US zip code for localised pricing.

    Returns:
        A PricingResult with priced items, not-found names, and a total.

    Raises:
        EnvironmentError: If KROGER_CLIENT_ID or KROGER_CLIENT_SECRET are not set.
        requests.HTTPError: If any API call returns a non-2xx response.
    """
    client_id = os.getenv("KROGER_CLIENT_ID")
    client_secret = os.getenv("KROGER_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise EnvironmentError("KROGER_CLIENT_ID and KROGER_CLIENT_SECRET must be set in environment.")

    token = _get_token(client_id, client_secret)
    location_id = _resolve_location_id(zip_code, token) if zip_code else None

    result = PricingResult()
    for ingredient in ingredients:
        priced = fetch_price(ingredient, token, location_id)
        if priced.found:
            result.priced.append(priced)
        else:
            result.not_found.append(ingredient)

    result.total_usd = round(sum(p.price_usd for p in result.priced), 2)
    return result


def print_prices(result: PricingResult) -> None:
    """Print a human-readable pricing summary to stdout."""
    sep = "-" * 52
    print(f"\n{sep}")
    print("  Kroger Pricing")
    print(sep)
    for p in result.priced:
        brand = f" ({p.brand})" if p.brand else ""
        print(f"  {p.name:<28} ${p.price_usd:>6.2f}  {p.unit}{brand}")
    if result.not_found:
        print(f"\n  Not found on Kroger ({len(result.not_found)}):")
        for name in result.not_found:
            print(f"    - {name}")
    print(f"\n  Estimated total:             ${result.total_usd:.2f}")
    print(f"{sep}\n")


if __name__ == "__main__":
    pricing = fetch_prices(TEST_INGREDIENTS, zip_code=TEST_ZIP_CODE)
    print_prices(pricing)
