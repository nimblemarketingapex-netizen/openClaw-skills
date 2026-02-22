require("dotenv").config();
const express = require("express");
const axios = require("axios");
const cors = require("cors");
const Database = require("better-sqlite3");

const app = express();
app.use(cors());
app.use(express.json());

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

// 2. OAuth callback — обмен code → token
app.get("/oauth/callback", async (req, res) => {
  const code = req.query.code;
  if (!code) return res.status(400).send("No code");

  try {
    const tokenResponse = await axios.post(
      "https://api.figma.com/v1/oauth/token",
      new URLSearchParams({
        redirect_uri: REDIRECT_URI,
        code: code,
        grant_type: "authorization_code",
      }),
      {
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "Authorization":
            "Basic " +
            Buffer.from(CLIENT_ID + ":" + CLIENT_SECRET).toString("base64"),
        },
        // Перехватываем сырой JSON до JSON.parse — иначе большие числа теряют точность
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

// Сохраняем в БД — user_id приводим к строке (чтобы совпадал при поиске)
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
    console.error("Response data:", error.response?.data);
    console.error("Status:", error.response?.status);
    res.status(500).send(
      "OAuth failed: " + JSON.stringify(error.response?.data || error.message)
    );
  }
});

// 3. Список всех сохранённых токенов
app.get("/tokens", (req, res) => {
  const rows = db.prepare("SELECT user_id, expires_at, created_at FROM tokens").all();
  res.json(rows);
});

// 4. Получение файла (токен берётся из БД по user_id)
app.get("/figma/file/:fileKey", async (req, res) => {
  const { fileKey } = req.params;
  const userId = req.query.user_id || "default";

  const row = db.prepare("SELECT access_token FROM tokens WHERE user_id = ?").get(userId);
  if (!row) return res.status(401).json({ error: "No token for user " + userId });

  try {
    const response = await axios.get(
      `https://api.figma.com/v1/files/${fileKey}`,
      { headers: { "Authorization": "Bearer " + row.access_token } }
    );
    res.json(response.data);
  } catch (error) {
    console.error("Figma API error:", error.response?.data);
    res.status(500).json({ error: error.response?.data || error.message });
  }
});

app.listen(4000, "0.0.0.0", () => {
  console.log("Server running on port 4000");
});
