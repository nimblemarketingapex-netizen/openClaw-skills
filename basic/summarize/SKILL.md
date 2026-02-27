---
name: summarize
description: Summarize text, URLs, local files, and YouTube videos — extract transcripts or short summaries when asked about content of links or media.
---
# Summarize (security-first)

Settings are externalized to OpenClaw config:

## Config path

`~/.openclaw/openclaw.json`

# Summarize (local LLM)

Fast summarization of URLs, text, and documents using your local AI model.

## How it works

When invoked, OpenClaw will:

1. Pass input (URL or text) to this skill
2. If URL → fetch content (optional, CLI summarize can do this)
3. Send content to local Ollama LLM
4. Return generated summary
5. Optionally forward result to Telegram or UI

## Trigger phrases (auto-invoke)

Use this skill when user asks:

- “summarize this”
- “what is this article about”
- “short summary”
- “explain this link”
- “what’s inside this document”
- “transcribe or summarize YouTube”

OpenClaw will call this skill automatically.

## Model (local)

All processing is local via Ollama:

- default model: `mistral`
- API: http://localhost:11434/api/generate
- no external keys
- offline capable

If model is missing, instruct user to run:

```bash
ollama pull mistral
ollama run mistral
Usage (CLI or internal)
```

## You may call summarize CLI if available:

summarize "https://example.com" --model mistral

# Or process raw text:

summarize --text "large text here"

**OpenClaw will capture output and return it.**

## Output style

- concise summary by default
- highlight key facts
- no marketing fluff
- bullet points preferred
- keep under requested length (if specified)

## Example:

**Original:** 2000 words
**Summary:** 3–5 bullet points + one sentence takeaway

## Error handling

**If LLM unavailable:**

- fallback message
- log error
- notify user

# Example:

Sorry, summary is unavailable right now.
Config (optional)

~/.summarize/config.json

{
  "model": "mistral",
  "max_length": "short"
}

## Extensions

- YouTube transcript → summary
- PDF/text file → summary
- URL content → summary
- Telegram response