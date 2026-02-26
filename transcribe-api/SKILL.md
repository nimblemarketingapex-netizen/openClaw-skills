---
name: transcribe-api
description: Transcribe audio via OpenAI Audio Transcriptions API (Whisper)
---

# API OpenAI Whisper (curl)

Транскрибирование аудиофайла через конечную точку OpenAI `/v1/audio/transcriptions`.

## Быстрый старт

```bash
{baseDir}/scripts/transcribe.sh /path/to/audio.m4a
```

Значения по умолчанию:

- Модель: `whisper-1`
- Вывод: `<input>.txt`

## Полезные флаги

```bash
{baseDir}/scripts/transcribe.sh /path/to/audio.ogg --model whisper-1 --out /tmp/transcribe.txt
{baseDir}/scripts/transcribe.sh /path/to/audio.m4a --language en
{baseDir}/scripts/transcribe.sh /path/to/audio.m4a --prompt "Имена говорящих: Питер, Даниэль"
{baseDir}/scripts/transcribe.sh /path/to/audio.m4a --json --out /tmp/transcript.json
```
