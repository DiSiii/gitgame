# server.py
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from datetime import datetime

print("сервер запущен!!!!!!!!")

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

# === ВЫБОР ПРОВИНЦИЙ С ПРОВЕРКОЙ КОНФЛИКТОВ ===
@app.route('/choose', methods=['POST'])
def choose_provinces():
    data = request.json
    player_id = str(data['player_id'])
    capital = str(data['capital'])
    others = [str(x) for x in data['others']]
    all_provinces = [capital] + others

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    with conn.cursor() as cur:
        # Игрок уже существует?
        cur.execute("SELECT id FROM players WHERE id = %s", (player_id,))
        if cur.fetchone():
            conn.close()
            return jsonify({"error": "Игрок уже существует"}), 400

        # Собираем все занятые провинции
        cur.execute("SELECT provinces FROM players")
        rows = cur.fetchall()
        occupied = set()
        for row in rows:
            try:
                prov = json.loads(row['provinces'])
                if prov.get("capital"):
                    occupied.add(str(prov["capital"]))
                for p in prov.get("others", []):
                    occupied.add(str(p))
            except:
                pass

        # Проверяем каждую провинцию
        for pid in all_provinces:
            if pid in occupied:
                conn.close()
                return jsonify({"error": f"Провинция {pid} уже занята"}), 409

        # Создаём игрока
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
            "",
            json.dumps(provinces_data),
            500,
            250,
            1000,
            1800,
            2500,
            capital
        ))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok"})

# === ИГРОВЫЕ ДЕЙСТВИЯ ===
@app.route('/action', methods=['POST'])
def game_action():
    data = request.json
    player_id = str(data.get("player_id"))
    action = data.get("action", {})

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

        provinces = json.loads(player["provinces"])
        gold = player["gold"]
        food = player["food"]
        wood = player["wood"]
        army_power = player["army_power"]
        garrison_power = player["garrison_power"]
        army_position = player["army_position"] or provinces.get("capital", "")

        act_type = action.get("type") if action else None

        # 🔍 ОТЛАДКА: начальное состояние
        print(f"DEBUG: Игрок {player_id}, действие: {act_type}")
        print(f"DEBUG: До: армия={army_power}, позиция={army_position}, провинции={provinces}")

        if act_type == "move_army":
            to_province = str(action["to_province"])
            new_army_power = int(action.get("army_power", army_power))
            army_position = to_province
            army_power = new_army_power
            print(f"DEBUG: Перемещение в {to_province}, новая армия={army_power}")

        elif act_type == "capture_province":
            prov = str(action["province"])
            new_army_power = int(action.get("army_power", army_power))
            
            # Добавляем провинцию, если её нет
            if prov != provinces.get("capital") and prov not in provinces.get("others", []):
                provinces["others"].append(prov)
                print(f"DEBUG: Захват провинции {prov}")
            else:
                print(f"DEBUG: Провинция {prov} уже принадлежит игроку")
            
            army_position = prov
            army_power = new_army_power
            print(f"DEBUG: После захвата: армия={army_power}, позиция={army_position}")

        elif act_type == "idle":
            print("DEBUG: Простой ход (idle)")

        elif not action or act_type is None:
            print("DEBUG: Пустое действие — простой ход")

        else:
            conn.close()
            return jsonify({"error": "Неизвестное действие"}), 400

        # 🔥 Сохраняем изменения
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

        # 🔍 ОТЛАДКА: финальное состояние
        print(f"DEBUG: Успешно обновлено для игрока {player_id}")
        print(f"DEBUG: После: армия={army_power}, позиция={army_position}, провинции={provinces}")
        return jsonify({"status": "ok"})

# === DEBUG: сброс хода ===
@app.route('/debug/reset_move_date', methods=['POST'])
def debug_reset_move_date():
    data = request.json
    player_id = str(data.get("player_id"))

    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    with conn.cursor() as cur:
        cur.execute("UPDATE players SET last_move_date = '' WHERE id = %s", (player_id,))
        conn.commit()
    conn.close()
    print(f"DEBUG: Сброшен ход для игрока {player_id}")
    return jsonify({"status": "ok"})

@app.route('/clear', methods=['POST'])
def clear_game():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM players")
        conn.commit()
    conn.close()
    print("DEBUG: Игра очищена")
    return jsonify({"status": "cleared"})

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

