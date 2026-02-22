---
name: figma
description: Работа с Figma макетом через backend и плагин. Используй когда нужно прочитать Figma файл, проанализировать дизайн, изменить текст или цвет элемента, создать фигуру в макете, сгенерировать код по дизайну.
metadata: {"clawdbot":{"emoji":"🎨"}}
---

**КРИТИЧЕСКИ ВАЖНО:** Когда пользователь просит что-либо сделать с Figma, ты **ОБЯЗАН** использовать инструмент **exec** с curl-командами ниже.

**ЗАПРЕЩЕНО:**
- Говорить «нет прямого доступа к backend»
- Говорить «не могу дернуть API»
- Предлагать пользователю самому выполнять команды

---

## Шаг 0 — Определить user_id (делать ВСЕГДА первым)

Перед любым действием нужно узнать figma `user_id` текущего пользователя.

### Способ 1 — по Telegram ID (приоритетный)

Узнай Telegram ID текущего пользователя из контекста чата, затем:

```bash
curl -s "http://localhost:4000/figma/user-by-telegram/TELEGRAM_ID"
```

Если вернул `user_id` — использовать его. Переходить к нужной команде.

### Способ 2 — аккаунт не привязан (выполнять строго по шагам)

Если Способ 1 вернул ошибку — выполни exec:

```bash
curl -s "http://localhost:4000/tokens"
```

Затем **обязательно** сделай следующее:

1. Покажи пользователю список аккаунтов из ответа (login, email)
2. Напиши: _"Чтобы я мог работать с Figma автоматически, нужно один раз привязать твой Telegram к аккаунту. Это твой аккаунт: [login]? Напиши «да» или выбери нужный."_
3. Когда пользователь подтвердит — **сразу выполни exec**:

```bash
curl -s -X POST "http://localhost:4000/figma/link-telegram" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"FIGMA_USER_ID","telegram_id":"TELEGRAM_ID"}'
```

4. Сообщи: _"Готово! Теперь я буду знать твой Figma-аккаунт автоматически."_
5. Продолжи выполнять исходный запрос пользователя с найденным `user_id`.

**ЗАПРЕЩЕНО** говорить "я не могу привязать" или "сделай это сам" — бот выполняет привязку через exec.

---

## 1. Получить узлы текущей страницы (приоритетный способ)

Через плагин — быстро, без rate limit Figma API:

```bash
# Запросить все узлы
curl -s -X POST "http://localhost:4000/figma/command" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"USER_ID","command":{"type":"get-page-nodes"}}'
```

```bash
# Забрать ответ (подождать 2-3 секунды после запроса)
curl -s "http://localhost:4000/figma/response/USER_ID"
```

Ответ содержит массив `nodes` с полями `id`, `name`, `type`, `x`, `y`, `width`, `height`.
Можно фильтровать по имени: `"nameFilter":"кнопка"` — вернёт только элементы с "кнопка" в названии.

## 1б. Получить структуру через Figma REST API (резервный)

```bash
curl -s "http://localhost:4000/figma/file/FILEKEY?user_id=USER_ID"
```

fileKey берётся из URL Figma: `figma.com/file/FILEKEY/...`
Используй этот способ только если плагин не подключён. Кэш 60 сек.

---

## 2. Изменить текст элемента

```bash
curl -s -X POST "http://localhost:4000/figma/command" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"USER_ID","command":{"type":"change-text","nodeId":"NODE_ID","text":"Новый текст"}}'
```

---

## 3. Изменить цвет элемента

```bash
curl -s -X POST "http://localhost:4000/figma/command" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"USER_ID","command":{"type":"change-color","nodeId":"NODE_ID","color":{"r":0.2,"g":0.6,"b":1.0}}}'
```

> Цвет в формате RGB от 0 до 1. Красный = `{"r":1,"g":0,"b":0}`, синий = `{"r":0,"g":0,"b":1}`.

---

## 4. Создать прямоугольник

```bash
curl -s -X POST "http://localhost:4000/figma/command" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"USER_ID","command":{"type":"create-rect","width":300,"height":150,"color":{"r":0.2,"g":0.6,"b":1.0}}}'
```

---

## 5. Изменить шрифт / размер / цвет текста

```bash
curl -s -X POST "http://localhost:4000/figma/command" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"USER_ID","command":{"type":"change-font","nodeId":"NODE_ID","family":"Inter","style":"Bold","size":24,"color":{"r":0,"g":0,"b":0}}}'
```

> `family`, `style`, `size`, `color` — все опциональны, указывай только нужные.

---

## 6. Переместить элемент

```bash
curl -s -X POST "http://localhost:4000/figma/command" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"USER_ID","command":{"type":"move","nodeId":"NODE_ID","x":100,"y":200}}'
```

---

## 7. Изменить размер элемента

```bash
curl -s -X POST "http://localhost:4000/figma/command" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"USER_ID","command":{"type":"resize","nodeId":"NODE_ID","width":300,"height":150}}'
```

---

## 8. Выравнивание нескольких элементов

```bash
curl -s -X POST "http://localhost:4000/figma/command" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"USER_ID","command":{"type":"align","nodeIds":["ID1","ID2","ID3"],"axis":"horizontal","align":"center"}}'
```

> `axis`: `"horizontal"` или `"vertical"`. `align`: `"min"` (лево/верх), `"center"`, `"max"` (право/низ).

---

## 9. Авто-layout

```bash
curl -s -X POST "http://localhost:4000/figma/command" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"USER_ID","command":{"type":"set-autolayout","nodeId":"NODE_ID","direction":"HORIZONTAL","spacing":16,"padding":24,"wrap":false}}'
```

> `direction`: `"HORIZONTAL"`, `"VERTICAL"`, `"NONE"`.

---

## 10. Эффекты (тень, blur)

```bash
curl -s -X POST "http://localhost:4000/figma/command" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"USER_ID","command":{"type":"set-effects","nodeId":"NODE_ID","effects":[{"type":"DROP_SHADOW","color":{"r":0,"g":0,"b":0,"a":0.25},"offset":{"x":0,"y":4},"radius":8,"spread":0,"visible":true,"blendMode":"NORMAL"}]}}'
```

> Типы эффектов: `DROP_SHADOW`, `INNER_SHADOW`, `LAYER_BLUR`, `BACKGROUND_BLUR`.

---

## 11. Обводка (stroke)

```bash
curl -s -X POST "http://localhost:4000/figma/command" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"USER_ID","command":{"type":"set-stroke","nodeId":"NODE_ID","color":{"r":0,"g":0,"b":0},"weight":2}}'
```

---

## 12. Скругление углов

```bash
curl -s -X POST "http://localhost:4000/figma/command" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"USER_ID","command":{"type":"set-corner-radius","nodeId":"NODE_ID","radius":12}}'
```

---

## 13. Создать текстовый элемент

```bash
curl -s -X POST "http://localhost:4000/figma/command" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"USER_ID","command":{"type":"create-text","text":"Заголовок","x":100,"y":50,"size":32,"family":"Inter","style":"Bold","color":{"r":0,"g":0,"b":0},"name":"Title"}}'
```

---

## 14. Создать фрейм

```bash
curl -s -X POST "http://localhost:4000/figma/command" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"USER_ID","command":{"type":"create-frame","width":375,"height":812,"x":0,"y":0,"name":"Mobile Screen","color":{"r":1,"g":1,"b":1}}}'
```

---

## 15. Удалить элемент

```bash
curl -s -X POST "http://localhost:4000/figma/command" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"USER_ID","command":{"type":"delete-node","nodeId":"NODE_ID"}}'
```

---

## 16. Переименовать элемент

```bash
curl -s -X POST "http://localhost:4000/figma/command" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"USER_ID","command":{"type":"rename","nodeId":"NODE_ID","name":"Button / Primary"}}'
```

---

## 17. Переместить элемент внутрь другого

```bash
curl -s -X POST "http://localhost:4000/figma/command" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"USER_ID","command":{"type":"append-to","nodeId":"NODE_ID","parentId":"PARENT_NODE_ID"}}'
```

---

## Примечание: работа с новыми элементами

Если пользователь добавил что-то в Figma вручную и хочет это изменить — сначала получи актуальную структуру файла (команда 1), найди nodeId нужного элемента по `"name"`, затем применяй команды. Файл всегда возвращает актуальное состояние макета.

---

## Типичный сценарий: изменить цвет по названию элемента

1. exec: определить user_id (Шаг 0)
2. exec: получить структуру файла → найти nodeId нужного элемента
3. exec: отправить change-color с этим nodeId
4. Сообщить пользователю результат

**Условие работы команд:** плагин "OpenClaw Figma Assistant" должен быть открыт в Figma со статусом `🟢 Подключено`.
Если ответ `{"ok":false,"error":"Plugin not connected"}` — попросить пользователя открыть плагин в Figma.
