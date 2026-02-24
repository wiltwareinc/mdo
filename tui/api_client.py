# wiltware (scaffolded by ChatGPT Codex 5.3)
# minimal api functions for frontends

import os
from typing import Any, Dict, List
import requests


BASE_URL = os.getenv("MDO_API_URL", "http://127.0.0.1:8000")

def _url(path: str) -> str:
    # helper script to turn a path into the url
    return f"{BASE_URL}{path}"

# GET
def get_songs() -> List[Dict[str, Any]]:
    resp = requests.get(_url("/songs"), timeout=5)
    resp.raise_for_status()
    return resp.json()

def get_song(slug: str) -> Dict[str, Any]:
    resp = requests.get(_url(f"/songs/{slug}"), timeout=5)
    resp.raise_for_status()
    return resp.json()
    
def get_albums() -> List[Dict[str, Any]]:
    resp = requests.get(_url("/albums"), timeout=5)
    resp.raise_for_status()
    return resp.json()
    
def get_album(slug: str) -> Dict[str, Any]:
    resp = requests.get(_url(f"/albums/{slug}"), timeout=5)
    resp.raise_for_status()
    return resp.json()