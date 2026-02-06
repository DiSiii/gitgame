# server.py
from flask import Flask, jsonify, request
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import datetime

app = Flask(__name__)
CORS_ENABLED = True

if CORS_ENABLED:
    from flask_cors import CORS
    CORS(app)

# Получаем DATABASE_URL из Render
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("❌ Переменная DATABASE_URL не задана!")

def init_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id TEXT PRIMARY KEY,
                name TEXT,
                last_move_date TEXT,
                provinces TEXT
            )
        """)
        conn.commit()
    conn.close()

init_db()

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def today():
    return datetime.date.today().isoformat()

@app.route("/game")
def get_game():
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM players")
        rows = cur.fetchall()
    conn.close()

    players = {}
    for row in rows:
        try:
            provinces = json.loads(row["provinces"]) if row["provinces"] else None
        except:
            provinces = None
        players[row["id"]] = {
            "name": row["name"],
            "last_move_date": row["last_move_date"],
            "provinces": provinces
        }

    return jsonify({"version": 1, "players": players})

@app.route("/submit", methods=["POST"])
def submit_move():
    data = request.get_json()
    if not data or "player_id" not in data:
        return jsonify({"error": "Missing player_id"}), 400

    player_id = str(data["player_id"])
    today_str = today()

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT provinces FROM players WHERE id = %s", (player_id,))
        row = cur.fetchone()

        if row is None:
            # Новый игрок
            action = data.get("action", {})
            if action.get("type") != "claim_start_provinces":
                conn.close()
                return jsonify({"error": "Новые игроки должны выбрать провинции"}), 400

            capital = action.get("capital")
            others = action.get("others", [])
            if not capital or len(others) != 2:
                conn.close()
                return jsonify({"error": "Требуется столица и 2 соседние провинции"}), 400

            # Проверка занятости
            cur.execute("SELECT provinces FROM players")
            all_rows = cur.fetchall()
            occupied = set()
            for r in all_rows:
                if r["provinces"]:
                    try:
                        p_data = json.loads(r["provinces"])
                        occupied.add(p_data["capital"])
                        occupied.update(p_data["others"])
                    except:
                        pass

            conflict = [p for p in [capital] + others if p in occupied]
            if conflict:
                conn.close()
                return jsonify({"error": f"Провинции заняты: {', '.join(conflict)}"}), 400

            provinces_data = {"capital": capital, "others": others}
            cur.execute("""
                INSERT INTO players (id, name, last_move_date, provinces)
                VALUES (%s, %s, %s, %s)
            """, (player_id, f"Игрок {player_id}", today_str, json.dumps(provinces_data)))

        else:
            # Существующий игрок
            cur.execute("""
                UPDATE players SET last_move_date = %s WHERE id = %s
            """, (today_str, player_id))

    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/clear", methods=["POST"])
def clear_game():
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM players")
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
