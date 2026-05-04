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
    """
    Convert an sRGB channel value to linear light for luminance calculation.

    :param c: Integer channel value (0–255).
    :returns: Linearized float value.
    """
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(r, g, b):
    """
    Calculate the WCAG relative luminance of an RGB color.

    :param r: Red channel (0–255).
    :param g: Green channel (0–255).
    :param b: Blue channel (0–255).
    :returns: Luminance as a float between 0 (black) and 1 (white).
    """
    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)


def _rgb_distance(r1, g1, b1, r2, g2, b2):
    """
    Calculate the Euclidean distance between two RGB colors in 3D color space.

    :param r1: Red channel of the first color (0–255).
    :param g1: Green channel of the first color (0–255).
    :param b1: Blue channel of the first color (0–255).
    :param r2: Red channel of the second color (0–255).
    :param g2: Green channel of the second color (0–255).
    :param b2: Blue channel of the second color (0–255).
    :returns: Distance as a float. Maximum possible value is ~441 (black to white).
    """
    return ((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2) ** 0.5


def _pick_rgb(seed):
    """
    Generate a deterministic RGB color from an integer seed.

    :param seed: Integer seed for the random number generator.
    :returns: Tuple of (r, g, b) integers each in range 0–255.
    """
    rng = random.Random(seed)
    return rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255)


def _generate_rgb(for_date: date):
    """
    Generate a deterministic RGB color for a given date, ensuring it is distinct
    from yesterday's color and bright enough to be visible.

    Uses the date as a seed so the same color is always produced for the same day.
    Retries up to 19 times with offset seeds if the color is too dark (below
    MIN_LUMINANCE) or too similar to yesterday's (below MIN_COLOR_DISTANCE).

    :param for_date: The date to generate a color for.
    :returns: Tuple of (r, g, b) integers each in range 0–255.
    """
    base_seed = int(for_date.strftime("%Y%m%d"))
    yr, yg, yb = _pick_rgb(int((for_date - timedelta(days=1)).strftime("%Y%m%d")))
    r, g, b = _pick_rgb(base_seed)
    for attempt in range(1, 20):
        if luminance(r, g, b) >= MIN_LUMINANCE and _rgb_distance(r, g, b, yr, yg, yb) >= MIN_COLOR_DISTANCE:
            break
        r, g, b = _pick_rgb(base_seed + attempt)
    return r, g, b


def _fetch_color_name(hex_color: str) -> str:
    """
    Fetch a human-readable name for a hex color from the Color API.

    Falls back to the raw hex string if the request fails or times out.

    :param hex_color: Hex color string with or without leading "#".
    :returns: Color name string (e.g. "Cerulean Blue"), or the hex string on failure.
    """
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
    """
    Return the hex color for a given date without making any API calls.

    :param for_date: The date to generate a color for.
    :returns: Hex color string (e.g. "#A3F0C2").
    """
    r, g, b = _generate_rgb(for_date)
    return f"#{r:02X}{g:02X}{b:02X}"


def generate_challenge(for_date: date) -> dict:
    """
    Generate a full challenge document for a given date.

    Picks a deterministic color, fetches its name from the Color API, and
    selects a prompt template — all seeded by date so the result is identical
    for every user on the same day.

    :param for_date: The date to generate a challenge for.
    :returns: Dict with keys "prompt" (display string), "color_hex", and "date" (ISO string).
    """
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
