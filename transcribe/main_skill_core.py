import os
import tempfile
import subprocess
from pathlib import Path
import shutil
from faster_whisper import WhisperModel
import soundfile as sf

# === Настройки и папки ===
# Корень OpenClaw, а не только workspace, чтобы работать с реальной папкой media/inbound
WORKSPACE_ROOT = "/home/boss/.openclaw"
INBOUND_DIR = os.path.join(WORKSPACE_ROOT, "media", "inbound")
os.makedirs(INBOUND_DIR, exist_ok=True)

# === Инициализация модели ===
model = WhisperModel("small")  # small работает на 8GB RAM + 2 CPU

# === Вспомогательные функции ===
def save_text_to_file(text, filename):
    filepath = os.path.join(WORKSPACE_ROOT, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[DEBUG] save_text_to_file: сохранено {filepath}")
    return filepath

# === Конвертация в WAV 16kHz моно ===
def convert_to_wav(input_file):
    input_file = os.path.abspath(input_file)
    print(f"[DEBUG] convert_to_wav: input_file={input_file}")

    if not os.path.exists(input_file):
        raise FileNotFoundError(f"[ERROR] Файл не найден: {input_file}")

    tmp_dir = "/tmp"
    os.makedirs(tmp_dir, exist_ok=True)
    output_file = tempfile.NamedTemporaryFile(suffix=".wav", dir=tmp_dir, delete=False).name

    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        raise RuntimeError("[ERROR] ffmpeg не найден в PATH!")

    print(f"[DEBUG] convert_to_wav: output_file={output_file}")
    result = subprocess.run(
        [ffmpeg_path, "-y", "-i", input_file, "-ac", "1", "-ar", "16000", output_file],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"[ERROR] ffmpeg failed:\n{result.stderr}")
        raise RuntimeError(f"ffmpeg конвертация не удалась: {result.stderr}")

    if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
        raise RuntimeError(f"[ERROR] WAV не был создан или пустой: {output_file}")

    print(f"[DEBUG] WAV успешно создан: {output_file}")
    return output_file

# === Транскрипция ===
def transcribe_file(file_path, chunk_duration=5):
    wav_file = convert_to_wav(file_path)
    print(f"[DEBUG] transcribe_file: читаем WAV {wav_file}")
    data, fs = sf.read(wav_file)
    chunk_size = int(fs * chunk_duration)
    full_text = ""

    for start in range(0, len(data), chunk_size):
        chunk = data[start:start + chunk_size]
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmpfile:
            sf.write(tmpfile.name, chunk, fs)
            segments, _ = model.transcribe(tmpfile.name, beam_size=5)
            for segment in segments:
                full_text += segment.text + " "

    os.remove(wav_file)
    print(f"[DEBUG] transcribe_file: транскрипция завершена, длина текста={len(full_text)}")
    return full_text.strip()

# === Основная функция для бота ===
def process_meeting(file_path):
    print(f"[DEBUG] process_meeting: начато для файла {file_path}")

    # Преобразуем относительный путь относительно корня OpenClaw (~/.openclaw)
    if not os.path.isabs(file_path):
        # убираем ведущие ./ если есть
        clean_path = file_path.lstrip("./")
        file_path = os.path.join(WORKSPACE_ROOT, clean_path)
    file_path = os.path.abspath(file_path)

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"[ERROR] Файл не найден: {file_path}")

    # Копируем в inbound, если файл там не лежит
    filename = Path(file_path).name
    dest_path = os.path.join(INBOUND_DIR, filename)
    if os.path.abspath(file_path) != os.path.abspath(dest_path):
        shutil.copy(file_path, dest_path)
        print(f"[DEBUG] Файл скопирован в inbound: {dest_path}")
    file_path = dest_path

    # Транскрипция
    transcript = transcribe_file(file_path)
    transcript_file = save_text_to_file(transcript, os.path.join("workspace", Path(file_path).stem + "_transcript.txt"))

    # На этом этапе Python-скилл отвечает только за транскрипт.
    # Краткое/полное резюме и задачи будут формироваться самим агентом
    # по готовому тексту с использованием подскиллов (short_summary, full_summary, tasks).
    print("[DEBUG] process_meeting: транскрипт сохранён")

    return {
        "transcript": transcript_file
    }

# === Тестовый запуск ===
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Использование: python main_skill_core.py <путь_к_файлу>")
        sys.exit(1)
    file_path = sys.argv[1]
    print(f"[DEBUG] __main__: file_path={file_path}")
    results = process_meeting(file_path)
    print("Файлы с результатами:", results)