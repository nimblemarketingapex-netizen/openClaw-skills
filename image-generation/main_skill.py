import json
import subprocess
from pathlib import Path

def generate_image(prompt: str, output_path: str):
    """
    Запуск скрипта Deer Flow через OpenClaw подскилл.
    prompt: текст описания изображения
    output_path: путь для сохранения результата
    """
    # Путь к рабочей директории скилла
    skill_dir = Path.home() / ".openclaw/workspace/skills/image-generation"
    prompt_file = skill_dir / "prompt.json"
    output_file = Path(output_path)

    # Сохраняем промпт в JSON
    with open(prompt_file, "w", encoding="utf-8") as f:
        json.dump({"prompt": prompt}, f, ensure_ascii=False, indent=2)

    # Запускаем скрипт генерации изображения
    cmd = [
        "python",
        str(skill_dir / "generate.py"),
        "--prompt-file", str(prompt_file),
        "--output-file", str(output_file)
    ]

    try:
        subprocess.run(cmd, check=True)
        return str(output_file)
    except subprocess.CalledProcessError as e:
        return f"Ошибка при генерации: {e}"

# Пример вызова
if __name__ == "__main__":
    result = generate_image(
        "Красивый закат над горами",
        str(Path.home() / ".openclaw/workspace/skills/image-generation/outputs/result.jpg")
    )
    print("Сгенерированное изображение:", result)