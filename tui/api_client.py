# wiltware (scaffolded by ChatGPT Codex 5.3)
# minimal api functions for frontends

import logging
import os
from typing import Any, Dict, List

import requests

logging.basicConfig(
    filename="tui.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

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

def get_file(slug: str) -> Dict[str, Any]:
    resp = requests.get(_url(f"/files/{slug}"), timeout=5)
    resp.raise_for_status()
    return resp.json()


# EDIT


def edit_song(slug: str, payload: dict) -> Dict[str, Any]:
    resp = requests.patch(_url(f"/songs/{slug}"), json=payload, timeout=5)
    logging.info(f"resp: {resp}")
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        # re-raise with status + body so UI can show it
        raise RuntimeError(f"{resp.status_code}: {resp.text}") from exc

    return resp.json()

def edit_album(slug: str, payload: dict) -> Dict[str, Any]:
    resp = requests.patch(_url(f"/albums/{slug}"), json=payload, timeout=5)
    logging.info(f"resp: {resp}")
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        # re-raise with status + body so UI can show it
        raise RuntimeError(f"{resp.status_code}: {resp.text}") from exc

    return resp.json()

# CREATION

def create_song(title: str, payload: dict) -> Dict[str, Any]:
    resp = requests.post(_url(f"/songs"), json=payload, timeout=5)
    logging.info(f"resp: {resp}")
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        # re-raise with status + body so UI can show it
        raise RuntimeError(f"{resp.status_code}: {resp.text}") from exc

    return resp.json()

def create_album(title: str, payload: dict) -> Dict[str, Any]:
    resp = requests.post(_url(f"/albums"), json=payload, timeout=5)
    logging.info(f"resp: {resp}")
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        # re-raise with status + body so UI can show it
        raise RuntimeError(f"{resp.status_code}: {resp.text}") from exc

    return resp.json()

def create_lyric(slug: str, payload: dict) -> Dict[str, Any]:
    resp = requests.post(_url(f"/songs/{slug}/lyrics"), json=payload, timeout=5)
    logging.info(f"resp: {resp}")
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        # re-raise with status + body so UI can show it
        raise RuntimeError(f"{resp.status_code}: {resp.text}") from exc

    return resp.json()

def create_project(slug: str, payload: dict) -> Dict[str, Any]:
    resp = requests.post(_url(f"/songs/{slug}/projects"), json=payload, timeout=5)
    logging.info(f"resp: {resp}")
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        # re-raise with status + body so UI can show it
        raise RuntimeError(f"{resp.status_code}: {resp.text}") from exc

    return resp.json()