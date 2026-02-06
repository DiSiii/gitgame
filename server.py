# server.py
from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import json
import datetime
import os

app = Flask(__name__)
CORS(app)

DB_FILE = "game.db"

def init_db():
    if not os.path.exists(DB_FILE):
        conn = sqlite3.connect(DB_FILE)
        conn.execute("""
            CREATE TABLE players (
                id TEXT PRIMARY KEY,
                name TEXT,
                last_move_date TEXT,
                provinces TEXT  -- JSON: {"capital": "...", "others": [...]}
            )
        """)
        conn.commit()
        conn.close()

def today():
    return datetime.date.today().isoformat()

init_db()

@app.route("/game")
def get_game():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM players")
    players = {}
    for row in cur.fetchall():
        try:
            provinces = json.loads(row["provinces"]) if row["provinces"] else None
        except:
            provinces = None
        players[row["id"]] = {
            "name": row["name"],
            "last_move_date": row["last_move_date"],
            "provinces": provinces
        }
    conn.close()
    return jsonify({"version": 1, "players": players})

@app.route("/submit", methods=["POST"])
def submit_move():
    data = request.get_json()
    if not data or "player_id" not in data:
        return jsonify({"error": "Missing player_id"}), 400
    
    player_id = str(data["player_id"])
    today_str = today()

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # Проверяем, существует ли игрок
    cur.execute("SELECT * FROM players WHERE id = ?", (player_id,))
    row = cur.fetchone()

    if row is None:
        # НОВЫЙ ИГРОК: должен выбрать провинции
        action = data.get("action", {})
        if action.get("type") != "claim_start_provinces":
            conn.close()
            return jsonify({"error": "Новые игроки должны выбрать начальные провинции"}), 400
        
        capital = action.get("capital")
        others = action.get("others", [])
        
        if not capital or not isinstance(others, list) or len(others) != 2:
            conn.close()
            return jsonify({"error": "Требуется столица и ровно 2 соседние провинции"}), 400

        # Сохраняем провинции как JSON
        provinces_data = {
            "capital": str(capital),
            "others": [str(p) for p in others]
        }

        cur.execute("""
            INSERT INTO players (id, name, last_move_date, provinces)
            VALUES (?, ?, ?, ?)
        """, (
            player_id,
            f"Игрок {player_id}",
            today_str,
            json.dumps(provinces_data)
        ))

    else:
        # СУЩЕСТВУЮЩИЙ ИГРОК: просто обновляем дату хода
        cur.execute("""
            UPDATE players SET last_move_date = ?
            WHERE id = ?
        """, (today_str, player_id))

    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/clear", methods=["POST"])
def clear_game():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM players")
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
