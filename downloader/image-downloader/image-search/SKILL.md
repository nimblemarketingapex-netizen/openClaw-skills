---
name: image-search
description: Search and download images by query
---

# Image Search Skill

Поиск и скачивание картинок по текстовому запросу.

## Возможности

| Команда | Описание |
|----------|----------|
| search | поиск URL картинок |
| download | скачивание по URL |
| search_and_download | поиск + скачка одной командой |

## Поиск

```python
skill.search("котики", limit=5)