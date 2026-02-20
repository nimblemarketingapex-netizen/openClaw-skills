import os
import sys
import json
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SUMMARY_DIR = os.path.join(BASE_DIR, "summaries")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SUMMARY_DIR, exist_ok=True)


# ----------------------------
# Очистка файлов старше 40 дней
# ----------------------------
def cleanup_old_files():
    today = datetime.today()
    for file in os.listdir(DATA_DIR):
        if file.endswith(".json"):
            try:
                date_str = file.replace(".json", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if (today - file_date).days > 40:
                    os.remove(os.path.join(DATA_DIR, file))

                    md_file = file.replace(".json", ".md")
                    md_path = os.path.join(DATA_DIR, md_file)
                    if os.path.exists(md_path):
                        os.remove(md_path)
            except:
                continue


# ----------------------------
# Сохранение дня
# ----------------------------
def save_day(data):
    today = datetime.today().strftime("%Y-%m-%d")

    json_path = os.path.join(DATA_DIR, f"{today}.json")
    md_path = os.path.join(DATA_DIR, f"{today}.md")

    # JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Markdown
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# {today}\n\n")
        for project in data.get("projects", []):
            f.write(f"## Проект: {project['name']}\n\n")
            for task in project.get("tasks", []):
                status_icon = {
                    "done": "[x]",
                    "in_progress": "[~]",
                    "todo": "[ ]",
                    "moved": "[>]"
                }.get(task["status"], "[ ]")

                f.write(f"- {status_icon} {task['title']}\n")

        f.write(f"\nЭнергия: {data.get('energy', '-')}/10\n")
        f.write(f"Заметки: {data.get('notes', '')}\n")

    cleanup_old_files()

    return "День сохранён."


# ----------------------------
# Месячный отчёт
# ----------------------------
def monthly_summary():
    today = datetime.today()
    month_prefix = today.strftime("%Y-%m")

    total = 0
    done = 0
    project_stats = {}
    unfinished_tasks = []
    productive_days = 0
    best_day = None
    best_day_count = 0

    for file in os.listdir(DATA_DIR):
        if file.startswith(month_prefix) and file.endswith(".json"):
            day_done_count = 0

            with open(os.path.join(DATA_DIR, file), "r", encoding="utf-8") as f:
                data = json.load(f)

                for project in data.get("projects", []):
                    project_stats.setdefault(project["name"], 0)

                    for task in project.get("tasks", []):
                        total += 1

                        if task["status"] == "done":
                            done += 1
                            day_done_count += 1
                            project_stats[project["name"]] += 1
                        else:
                            unfinished_tasks.append(
                                f"{file.replace('.json','')} — {project['name']} — {task['title']} ({task['status']})"
                            )

            if day_done_count > 0:
                productive_days += 1

            if day_done_count > best_day_count:
                best_day_count = day_done_count
                best_day = file.replace(".json", "")

    completion_rate = round((done / total) * 100, 1) if total else 0
    best_project = max(project_stats, key=project_stats.get, default="—")

    # ---- Мотивационный блок ----
    if completion_rate >= 80:
        praise = "Это мощный результат. Ты работала системно и дисциплинированно."
    elif completion_rate >= 60:
        praise = "Хороший темп. Есть устойчивый прогресс."
    else:
        praise = "Месяц был непростым, но ты продолжала двигаться."

    recommendation = """
Рекомендации на следующий месяц:
- Сфокусироваться на 1–2 ключевых проектах.
- Чётче завершать начатые задачи.
- Планировать реалистичный объём на день.
"""

    summary_text = f"""
# Отчёт за {month_prefix}

📊 Основная статистика
Всего задач: {total}
Выполнено: {done}
Процент выполнения: {completion_rate}%

🔥 Продуктивных дней: {productive_days}

🏆 День-рекорд: {best_day if best_day else "—"} ({best_day_count} выполненных задач)

🚨 Незавершённые задачи:
{chr(10).join(unfinished_tasks[:20]) if unfinished_tasks else "Нет незавершённых задач 🎉"}

⭐ Самый продуктивный проект: {best_project}

💬 Итог месяца:
{praise}

{recommendation}
"""

    summary_path = os.path.join(SUMMARY_DIR, f"{month_prefix}-summary.md")

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_text.strip())

    return summary_text.strip()
# ----------------------------
# Точка входа
# ----------------------------
def main():
    if len(sys.argv) < 2:
        print("Команда не указана.")
        return

    command = sys.argv[1]

    if command == "save":
        # ожидаем JSON через stdin
        try:
            input_data = sys.stdin.read()
            data = json.loads(input_data)
            result = save_day(data)
            print(result)
        except Exception as e:
            print(f"Ошибка сохранения: {e}")

    elif command == "monthly_report":
        print(monthly_summary())

    else:
        print("Неизвестная команда.")


if __name__ == "__main__":
    main()