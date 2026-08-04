# Pokedex Web App

A FastAPI web application that lets users browse a Pokedex (Kanto + Johto
regions), search Pokemon by number or name, identify a Pokemon from a photo
using OpenCV feature matching, and build a personal team/storage collection
behind a simple username/password login.

## Features

- Browse and search all Kanto (#1–151) and Johto (#152–251) Pokemon
- Search by Pokedex number or name
- Snap/upload a photo and identify the Pokemon via ORB feature matching (OpenCV)
- User accounts (register/login/logout) with salted PBKDF2 password hashing
- Personal "Team" (max 6) and "Storage" lists saved per user in SQLite

## Project structure

```
pokedex-webapp/
├── main.py               # FastAPI app: routes, auth, image detection
├── database.py           # SQLite access layer (users, sessions, collection)
├── requirements.txt      # Python dependencies
├── data/
│   ├── kanto_pokedex.txt       # Kanto Pokedex data (number,name,type,description)
│   └── johto_region_unique.txt # Johto Pokedex data
├── static/
│   ├── web.css
│   ├── pokemon_images/          # Reference images used for photo ID (251 files)
│   └── (icons: menu, camera, pokeball)
├── templates/
│   └── index.html         # Main page template (Jinja2)
└── docs/
    └── Pokedex - Pokemon Encyclopedia.pptx  # Project slide deck
```

## Setup

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Then open http://127.0.0.1:8000 in your browser.

The SQLite database (`pokedex.db`), plus the `team.txt` / `storage.txt`
scratch files, are created automatically on first run — they aren't
included in this package since they're local runtime state.

## Notes

- `python-multipart` was added to `requirements.txt`; it's required by
  FastAPI's `UploadFile`/`File(...)` for the `/detect-image` endpoint but
  was missing from the original dependency list.
- Photo identification uses ORB descriptor matching against the images in
  `static/pokemon_images/` — a clear, well-lit, close-up photo works best.


