# wiltware 2026
# naming path safety
import re


_INVALID_DIRECTORY_CHARACTERS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def safe_directory_component(value: str) -> str:
    normalized = " ".join(value.split())
    safe_value = _INVALID_DIRECTORY_CHARACTERS.sub("-", normalized).strip(" .")

    if not safe_value or not safe_value.strip("-_ "):
        raise ValueError("title must contain usable filename characters")

    return safe_value
