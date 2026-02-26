#!/usr/bin/env python3
import json
import os
import subprocess
import sys


def load_api_key():
    config_path = os.path.expanduser("~/.openclaw/openclaw.json")

    if not os.path.exists(config_path):
        raise RuntimeError(f"Config not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    try:
        return config["skills"]["openai-whisper-api"]["apiKey"]
    except KeyError:
        raise RuntimeError("API key not found in config (skills.openai-whisper-api.apiKey)")


def transcribe(audio_path):
    api_key = load_api_key()
    os.environ["OPENAI_API_KEY"] = api_key

    # вызываем твой скрипт
    script = os.path.expanduser("~/.openclaw/workspace/skills/scripts/transcribe.sh")

    if not os.path.exists(script):
        raise RuntimeError(f"transcribe.sh not found: {script}")

    subprocess.run([script, audio_path], check=True)


def main():
    if len(sys.argv) < 2:
        print("Usage: agent.py <audio-file>")
        sys.exit(1)

    audio = sys.argv[1]
    transcribe(audio)


if __name__ == "__main__":
    main()