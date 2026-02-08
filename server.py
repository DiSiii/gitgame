# server.py
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
        # Ресурсы
        cur.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS gold INT DEFAULT 500;")
        cur.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS wood INT DEFAULT 250;")
        cur.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS food INT DEFAULT 1000;")
        # Армия
        cur.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS army_power INT DEFAULT 1800;")
        cur.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS garrison_power INT DEFAULT 2500;")
        cur.execute("ALTER TABLE players ADD COLUMN IF NOT EXISTS army_position TEXT;")
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
            army_pos = row.get('army_position') or provinces.get("capital", "")
            players[row['id']] = {
                "name": row['name'],
                "last_move_date": row['last_move_date'],
                "provinces": provinces,
                "gold": row.get('gold', 500),
                "wood": row.get('wood', 250),
                "food": row.get('food', 1000),
                "army_power": row.get('army_power', 1800),
                "garrison_power": row.get('garrison_power', 2500),
                "army_position": army_pos
            }
        conn.close()
        return jsonify({
            "version": 1,
            "players": players
        })

# === ВЫБОР НАЧАЛЬНЫХ ПРОВИНЦИЙ ===
@app.route('/choose', methods=['POST'])
def choose_provinces():
    data = request.json
    player_id = str(data['player_id'])
    capital = str(data['capital'])
    others = [str(x) for x in data['others']]

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
                gold, wood, food, army_power, garrison_power, army_position
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
        """, (
            player_id,
            f"Игрок {player_id}",
            today(),
            json.dumps(provinces_data),
            500,
            250,
            1000,
            1800,  # 3 воина × 600
            2500,
            capital  # армия в столице
        ))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok"})

# === ЛЮБОЕ ИГРОВОЕ ДЕЙСТВИЕ ===
@app.route('/action', methods=['POST'])
def game_action():
    data = request.json
    player_id = str(data.get("player_id"))
    action = data.get("action", {})

    if not action:
        return jsonify({"error": "Нет действия"}), 400

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM players WHERE id = %s", (player_id,))
        player = cur.fetchone()
        if not player:
            conn.close()
            return jsonify({"error": "Игрок не найден"}), 404

        if player["last_move_date"] == today():
            conn.close()
            return jsonify({"error": "Вы уже сделали ход сегодня"}), 403

        # Загружаем данные
        provinces = json.loads(player["provinces"])
        gold = player["gold"]
        food = player["food"]
        wood = player["wood"]
        army_power = player["army_power"]
        garrison_power = player["garrison_power"]
        army_position = player["army_position"] or provinces.get("capital", "")

        # === ОБРАБОТКА ДЕЙСТВИЙ ===
        act_type = action.get("type")

        if act_type == "move_army":
            to_province = str(action["to_province"])
            new_army_power = int(action.get("army_power", army_power))
            # Проверка: можно ли туда идти? (опционально)
            army_position = to_province
            army_power = new_army_power

        elif act_type == "capture_province":
            prov = str(action["province"])
            new_army_power = int(action.get("army_power", army_power))
            # Добавляем провинцию, если её нет
            if prov != provinces.get("capital") and prov not in provinces.get("others", []):
                provinces["others"].append(prov)
            army_position = prov
            army_power = new_army_power

        else:
            conn.close()
            return jsonify({"error": "Неизвестное действие"}), 400

        # === СОХРАНЕНИЕ ===
        cur.execute("""
            UPDATE players SET
                last_move_date = %s,
                gold = %s,
                food = %s,
                wood = %s,
                army_power = %s,
                garrison_power = %s,
                army_position = %s,
                provinces = %s
            WHERE id = %s
        """, (
            today(),
            gold,
            food,
            wood,
            army_power,
            garrison_power,
            army_position,
            json.dumps(provinces),
            player_id
        ))
        conn.commit()
        conn.close()
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
