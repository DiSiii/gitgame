import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL')

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
        cur.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS gold INT DEFAULT 500;")
        cur.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS wood INT DEFAULT 250;")
        cur.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS food INT DEFAULT 1000;")
        cur.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS army_power INT DEFAULT 1200;")
        cur.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS garrison_power INT DEFAULT 2500;")
        conn.commit()
    conn.close()

def today():
    return datetime.now().strftime("%Y-%m-%d")

@app.route('/game')
def get_game_state():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM players")
        rows = cur.fetchall()
        players = {}
        for row in rows:
            try:
                provinces = json.loads(row['provinces'])
            except:
                provinces = {"capital": "", "others": []}
            players[row['id']] = {
                "name": row['name'],
                "last_move_date": row['last_move_date'],
                "provinces": provinces,
                "gold": row.get('gold', 500),
                "wood": row.get('wood', 250),
                "food": row.get('food', 1000),
                "army_power": row.get('army_power', 1200),
                "garrison_power": row.get('garrison_power', 2500)
            }
        conn.close()
        return jsonify({
            "version": 1,
            "players": players
        })

# 🔥 НОВЫЙ: обработка /submit для всех действий
@app.route('/submit', methods=['POST'])
def submit_move():
    data = request.json
    player_id = str(data.get("player_id"))
    action = data.get("action", {})

    # Выбор начальных провинций
    if action.get("type") == "claim_start_provinces":
        capital = str(action["capital"])
        others = [str(x) for x in action["others"]]

        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM players WHERE id = %s", (player_id,))
            if cur.fetchone():
                conn.close()
                return jsonify({"error": "Игрок уже существует"}), 400

            provinces_data = {"capital": capital, "others": others}
            cur.execute("""
                INSERT INTO players (
                    id, name, last_move_date, provinces,
                    gold, wood, food, army_power, garrison_power
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                player_id,
                f"Игрок {player_id}",
                today(),
                json.dumps(provinces_data),
                500, 250, 1000, 1200, 2500
            ))
            conn.commit()
            conn.close()
            return jsonify({"status": "ok"})

    # Другие действия (в будущем)
    return jsonify({"status": "ok"})

@app.route('/clear', methods=['POST'])
def clear_game():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM players")
        conn.commit()
    conn.close()
    return jsonify({"status": "cleared"})

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
