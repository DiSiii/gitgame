from flask import Flask, jsonify, request
import json
import datetime
import os

app = Flask(__name__)


def today():
    return datetime.date.today().isoformat()


@app.route("/game")
def get_game():
    if os.path.exists("game_state.json"):
        with open("game_state.json") as f:
            return jsonify(json.load(f))
    return jsonify({"version": 0, "players": {}})


@app.route("/submit", methods=["POST"])
def submit_move():
    data = request.json
    player_id = str(data["player_id"])

    state = {"version": 0, "players": {}}
    if os.path.exists("game_state.json"):
        with open("game_state.json") as f:
            state = json.load(f)

    if player_id not in state["players"]:
        state["players"][player_id] = {"name": f"Игрок {player_id}"}
    state["players"][player_id]["last_move_date"] = today()
    state["version"] += 1

    with open("game_state.json", "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))