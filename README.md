# MDO: Music Document Organizer

- Python
- File watcher
- FastAPI
- Textual

This is a personal project for me to learn full-stack development with Python using RESTful APIs. This repo serves to hold the **backend**  with a simple TUI.

## What does it do?
This connects to a specific filesystem to eb able to organize albums and songs someone makes. This allows for more in-depth filtering, customization, and tracking.

## Why use the app?
The app actually isn't that important, it's just essentially a set of rules to give a specific layout. One of the major goals of the project is for the filesystem to still be human-readable and easily navigable, the app just makes it that much easier.

## Why is there a TUI?
I wanted to go ahead and use this as soon as possible, as well as provide a simple frontend packaged in the with the backend for development purposes.

## Why does ____ not work?
This is the first full-stack project I have made all by myself. It is still in early beta, and I am the only one working on it. If you find an issue, please submit an issue.

## How can I run the app?
There are a few different ways:
- **Full application:** MDO_ROOT=<path/to/project/root> PYTHONPATH=. python -m tui-bare_tui
- **API:** PYTHONPATH=. MDO_ROOT=./music python -m uvicorn app.main:app --reload
  - note: this runs at localhost:800
- **Tests:** python test/<test>

## Is there any AI Used?
All AI generated code is made by ChatGPT 5.3 Codex. Mostly it is the tests, with minimal contributions to the codebase.

## How can I Build this?
The current method I am using to build this (for Linux) is as follows:
```
PYTHONPATH=. pyinstaller \
  --name mdo \
  --onefile \
  --add-data "tui/bare_tui.tcss:tui" \
  tui/bare_tui.py;
```