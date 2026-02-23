require("dotenv").config();
const express = require("express");
const axios = require("axios");
const cors = require("cors");
const Database = require("better-sqlite3");

const app = express();
app.use(cors());
app.use(express.json());

const WebSocket = require("ws");
const http = require("http");
const server = http.createServer(app);
const wss = new WebSocket.Server({ server, path: "/ws" });

// Хранилище подключённых плагинов: user_id → ws
const pluginClients = new Map();

// Хранилище ответов: requestId → { data, ts }
// Ключ — requestId (UUID), значение — ответ от плагина
const pluginResponses = new Map();

// Очистка старых ответов каждые 5 минут
setInterval(() => {
  const now = Date.now();
  for (const [key, val] of pluginResponses) {
    if (now - val.ts > 5 * 60 * 1000) pluginResponses.delete(key);
  }
}, 60 * 1000);

wss.on("connection", (ws) => {
  console.log("Plugin connected");

  ws.on("message", (data) => {
    const msg = JSON.parse(data);

    if (msg.type === "register") {
      pluginClients.set(msg.userId, ws);
      ws._userId = msg.userId;
      console.log("Plugin registered for user:", msg.userId);
      ws.send(JSON.stringify({ type: "registered" }));
    }

    // Ответ от плагина — сохраняем по requestId (если есть) и по userId
    if (msg.type === "response") {
      const uid = ws._userId;
      if (msg.requestId) {
        // Точное совпадение по requestId — приоритетный способ
        pluginResponses.set(msg.requestId, { data: msg, ts: Date.now() });
      }
      if (uid) {
        // Также сохраняем по userId для обратной совместимости
        pluginResponses.set(`user:${uid}`, { data: msg, ts: Date.now() });
      }
    }
  });

  ws.on("close", () => {
    for (const [uid, client] of pluginClients) {
      if (client === ws) pluginClients.delete(uid);
    }
  });
});

// Функция отправки команды в плагин
function sendToPlugin(userId, command) {
  const ws = pluginClients.get(String(userId));
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    return { ok: false, error: "Plugin not connected" };
  }
  ws.send(JSON.stringify(command));
  return { ok: true };
}

const CLIENT_ID = process.env.FIGMA_CLIENT_ID;
const CLIENT_SECRET = process.env.FIGMA_CLIENT_SECRET;
const REDIRECT_URI = process.env.REDIRECT_URI;

// База данных
const db = new Database("tokens.db");
db.exec(`
  CREATE TABLE IF NOT EXISTS tokens (
    user_id TEXT PRIMARY KEY,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at INTEGER,
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
  )
`);
for (const col of ["login TEXT", "email TEXT", "telegram_id TEXT"]) {
  try { db.exec(`ALTER TABLE tokens ADD COLUMN ${col}`); } catch {}
}

// 1. OAuth начало
app.get("/auth/figma", (req, res) => {
  const state = Math.random().toString(36).substring(2);
  const scope = [
    "current_user:read",
    "file_content:read",
    "file_metadata:read",
    "file_comments:read",
    "file_comments:write"
  ].join(" ");
  const url =
    "https://www.figma.com/oauth?" +
    "client_id=" + CLIENT_ID +
    "&redirect_uri=" + encodeURIComponent(REDIRECT_URI) +
    "&response_type=code" +
    "&scope=" + encodeURIComponent(scope) +
    "&state=" + state;
  res.redirect(url);
});

// 2. OAuth callback
app.get("/oauth/callback", async (req, res) => {
  const code = req.query.code;
  if (!code) return res.status(400).send("No code");
  try {
    const tokenResponse = await axios.post(
      "https://api.figma.com/v1/oauth/token",
      new URLSearchParams({ redirect_uri: REDIRECT_URI, code, grant_type: "authorization_code" }),
      {
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "Authorization": "Basic " + Buffer.from(CLIENT_ID + ":" + CLIENT_SECRET).toString("base64"),
        },
        transformResponse: [(data) => {
          return JSON.parse(data.replace(/"user_id"\s*:\s*(\d+)/g, '"user_id":"$1"'));
        }],
      }
    );
    const { access_token, refresh_token, expires_in, user_id } = tokenResponse.data;
    const me = await axios.get("https://api.figma.com/v1/me", {
      headers: { "Authorization": "Bearer " + access_token }
    });
    const login = me.data.handle || me.data.email || String(user_id);
    const email = me.data.email || null;
    const expires_at = Math.floor(Date.now() / 1000) + expires_in;
    const uid = String(user_id);
    db.prepare(`
      INSERT INTO tokens (user_id, access_token, refresh_token, expires_at, login, email)
      VALUES (?, ?, ?, ?, ?, ?)
      ON CONFLICT(user_id) DO UPDATE SET
        access_token = excluded.access_token,
        refresh_token = excluded.refresh_token,
        expires_at = excluded.expires_at,
        login = excluded.login,
        email = excluded.email
    `).run(uid, access_token, refresh_token, expires_at, login, email);
    console.log("Token saved for user:", user_id);
    res.send(`
      <h2>✅ Figma connected!</h2>
      <p><b>User ID:</b> ${user_id}</p>
      <p><b>Access token:</b></p>
      <textarea rows="4" cols="80" onclick="this.select()">${access_token}</textarea>
      <p><b>Refresh token:</b></p>
      <textarea rows="2" cols="80" onclick="this.select()">${refresh_token}</textarea>
      <p><b>Expires in:</b> ${expires_in} sec</p>
      <p><i>Токен сохранён в базе данных.</i></p>
    `);
  } catch (error) {
    console.error("OAuth error:", error.message);
    res.status(500).send("OAuth failed: " + JSON.stringify(error.response?.data || error.message));
  }
});

// 3. Список пользователей
app.get("/tokens", (req, res) => {
  const rows = db.prepare("SELECT user_id, login, email, telegram_id, expires_at FROM tokens").all();
  res.json(rows);
});

// 3a. Найти user_id по telegram_id
app.get("/figma/user-by-telegram/:telegramId", (req, res) => {
  const row = db.prepare("SELECT user_id, login, email FROM tokens WHERE telegram_id = ?").get(String(req.params.telegramId));
  if (!row) return res.status(404).json({ error: "No Figma account linked for this Telegram user" });
  res.json(row);
});

// 3b. Привязать telegram_id
app.post("/figma/link-telegram", (req, res) => {
  const { user_id, telegram_id } = req.body;
  if (!user_id || !telegram_id) return res.status(400).json({ error: "user_id and telegram_id required" });
  const result = db.prepare("UPDATE tokens SET telegram_id = ? WHERE user_id = ?").run(String(telegram_id), String(user_id));
  if (result.changes === 0) return res.status(404).json({ error: "user_id not found" });
  res.json({ ok: true });
});

// Кэш файлов
const fileCache = new Map();
const CACHE_TTL = 60 * 1000;

// 4. Получение файла
app.get("/figma/file/:fileKey", async (req, res) => {
  const { fileKey } = req.params;
  const userId = req.query.user_id || "default";
  const noCache = req.query.no_cache === "1";
  const cacheKey = `${userId}:${fileKey}`;
  const cached = fileCache.get(cacheKey);
  if (!noCache && cached && Date.now() - cached.ts < CACHE_TTL) {
    return res.json(cached.data);
  }
  const row = db.prepare("SELECT access_token FROM tokens WHERE user_id = ?").get(userId);
  if (!row) return res.status(401).json({ error: "No token for user " + userId });
  try {
    const response = await axios.get(
      `https://api.figma.com/v1/files/${fileKey}`,
      { headers: { "Authorization": "Bearer " + row.access_token } }
    );
    fileCache.set(cacheKey, { data: response.data, ts: Date.now() });
    res.json(response.data);
  } catch (error) {
    res.status(500).json({ error: error.response?.data || error.message });
  }
});

// ── Получить ответ от плагина ──────────────────────────────────────────────
// Поддерживает два режима:
//   GET /figma/response/:userId          — по userId (обратная совместимость)
//   GET /figma/response/:userId?rid=UUID — по requestId (точный)
// Параметр ?wait=1 включает polling до 8 секунд (вместо мгновенного 404)
app.get("/figma/response/:userId", async (req, res) => {
  const uid = String(req.params.userId);
  const rid = req.query.rid || null;
  const wait = req.query.wait === "1";

  const lookup = () => {
    if (rid) {
      const entry = pluginResponses.get(rid);
      if (entry) { pluginResponses.delete(rid); return entry.data; }
    }
    const entry = pluginResponses.get(`user:${uid}`);
    if (entry) { pluginResponses.delete(`user:${uid}`); return entry.data; }
    return null;
  };

  // Быстрый ответ если уже есть
  const immediate = lookup();
  if (immediate) return res.json(immediate);

  if (!wait) return res.status(404).json({ error: "No response yet" });

  // Polling: ждём до 8 секунд с интервалом 300ms
  const deadline = Date.now() + 8000;
  const poll = () => {
    const data = lookup();
    if (data) return res.json(data);
    if (Date.now() >= deadline) return res.status(408).json({ error: "Timeout waiting for plugin response" });
    setTimeout(poll, 300);
  };
  setTimeout(poll, 300);
});

// ── Команда в плагин ──────────────────────────────────────────────────────
// Автоматически генерирует requestId и возвращает его боту
// Бот может затем запросить /figma/response/:userId?rid=UUID&wait=1
app.post("/figma/command", (req, res) => {
  const { user_id, command } = req.body;

  // Генерируем requestId если не передан
  const requestId = command.requestId || `req_${Date.now()}_${Math.random().toString(36).slice(2)}`;
  const enrichedCommand = { ...command, requestId };

  const result = sendToPlugin(user_id, enrichedCommand);
  res.json({ ...result, requestId });
});

server.listen(4000, "0.0.0.0", () => {
  console.log("Server running on port 4000");
});