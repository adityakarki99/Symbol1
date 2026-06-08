# Symbolikon Encyclopedia Web App

A browsable encyclopedia of ancient symbols scraped from [symbolikon.com](https://symbolikon.com/), with search, category filters, tag filters, and detailed symbol pages.

## Features

- **1,500+ symbols** with names, descriptions, cultural context, tags, and preview images
- **66 categories** (Adinkra, Egyptian, Norse, Celtic, Maya, and more)
- **Full-text search** across names, descriptions, tags, and categories
- **Responsive layout** with sidebar navigation and symbol detail modal

## Quick start

```bash
# Serve locally (required for JSON loading)
python3 -m http.server 8080
```

Open [http://localhost:8080](http://localhost:8080)

## Data

Symbol data is stored in `data/`:

- `symbols.json` — symbol records with descriptions and image URLs
- `categories.json` — category metadata
- `tags.json` — tag metadata

To refresh the dataset:

```bash
python3 scripts/scrape_symbolikon.py
```

## Attribution

Symbol descriptions and artwork are sourced from [Symbolikon](https://symbolikon.com/). This project is an educational index; all rights to symbol designs and text belong to Symbolikon.
