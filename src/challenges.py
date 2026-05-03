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

MIN_LUMINANCE = 0.05
MIN_COLOR_DISTANCE = 100


def _linearize(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(r, g, b):
    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)


def _rgb_distance(r1, g1, b1, r2, g2, b2):
    return ((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2) ** 0.5


def _pick_rgb(seed):
    rng = random.Random(seed)
    return rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255)


def _generate_rgb(for_date: date):
    base_seed = int(for_date.strftime("%Y%m%d"))
    yr, yg, yb = _pick_rgb(int((for_date - timedelta(days=1)).strftime("%Y%m%d")))
    r, g, b = _pick_rgb(base_seed)
    for attempt in range(1, 20):
        if _luminance(r, g, b) >= MIN_LUMINANCE and _rgb_distance(r, g, b, yr, yg, yb) >= MIN_COLOR_DISTANCE:
            break
        r, g, b = _pick_rgb(base_seed + attempt)
    return r, g, b


def _fetch_color_name(hex_color: str) -> str:
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


def generate_color_hex(for_date: date) -> str:
    """Return just the hex color for a date — no API call."""
    r, g, b = _generate_rgb(for_date)
    return f"#{r:02X}{g:02X}{b:02X}"


def generate_challenge(for_date: date) -> dict:
    r, g, b = _generate_rgb(for_date)
    hex_color = f"#{r:02X}{g:02X}{b:02X}"
    base_seed = int(for_date.strftime("%Y%m%d"))
    prompt_template = random.Random(base_seed).choice(PROMPTS)
    name = _fetch_color_name(hex_color)
    return {
        "prompt": prompt_template.format(name),
        "color_hex": hex_color,
        "date": for_date.isoformat(),
    }


def two_days_ago(for_date: date) -> str:
    return (for_date - timedelta(days=2)).isoformat()
