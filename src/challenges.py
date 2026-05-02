import random
import requests
from datetime import date, timedelta

PROMPTS = [
    "Find something {}",
    "Spot something {}",
    "Hunt down something {}",
    "Show us something {}",
    "Capture something {}",
]


def _fetch_color_name(hex_color: str) -> str:
    """Look up a human-readable name for a hex color via thecolorapi.com."""
    try:
        resp = requests.get(
            "https://www.thecolorapi.com/id",
            params={"hex": hex_color.lstrip("#")},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()["name"]["value"]
    except Exception:
        return hex_color


def generate_challenge(for_date: date) -> dict:
    """Generate a random color for a given date and fetch its name from thecolorapi.com."""
    seed = int(for_date.strftime("%Y%m%d"))
    rng = random.Random(seed)
    r, g, b = rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255)
    hex_color = f"#{r:02X}{g:02X}{b:02X}"
    prompt_template = rng.choice(PROMPTS)
    name = _fetch_color_name(hex_color)
    return {
        "prompt": prompt_template.format(name),
        "color_hex": hex_color,
        "date": for_date.isoformat(),
    }


def two_days_ago(for_date: date) -> str:
    return (for_date - timedelta(days=2)).isoformat()
