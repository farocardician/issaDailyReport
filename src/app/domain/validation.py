import re

_THOUSAND_SEPARATORS = re.compile(r"[\s.,]+")


def parse_int_lenient(text: str) -> int:
    normalized = _THOUSAND_SEPARATORS.sub("", text.strip())
    if not normalized or not normalized.isdigit():
        raise ValueError("Input must contain digits only after removing separators")
    return int(normalized)


def normalize_text_dash(text: str) -> str:
    normalized = text.strip()
    if normalized == "-":
        return "-"
    return normalized
