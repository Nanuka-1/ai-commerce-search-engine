MODEL_FAMILIES = [
    "air max",
    "vapormax",
    "shox",
    "pegasus",
    "react",
]

COLORS = [
    "black",
    "white",
    "red",
    "blue",
    "green",
]

def extract_model_family(text: str) -> str | None:
    normalized_text = text.lower().replace("-", " ").replace("_", " ")

    for family in MODEL_FAMILIES:
        if family in normalized_text:
            return family

    return None


def extract_color(name: str) -> str | None:
    normalized_name = name.lower()

    for color in COLORS:
        if color in normalized_name:
            return color

    return None