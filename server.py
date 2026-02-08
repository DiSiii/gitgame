# В autoload/NetworkManager.gd

func send_action(action: Dictionary):
	if current_player_id <= 0:
		emit_signal("error_occurred", "ID игрока не установлен")
		return

	var payload = {
		"player_id": current_player_id,
		"action": action
	}

	var http = HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(_on_action_done.bind(http))
	var headers = ["Content-Type: application/json"]
	var body = JSON.stringify(payload)
	var error = http.request(SERVER_URL + "/action", headers, HTTPClient.METHOD_POST, body)
	
	if error != OK:
		remove_child(http)
		http.queue_free()
		emit_signal("error_occurred", "Не удалось отправить действие")

func _on_action_done(result, response_code, headers, body, http):
	remove_child(http)
	http.queue_free()
	if response_code == 200:
		load_game()  # перезагружаем состояние
	else:
		var msg = "Ошибка действия (HTTP %d)" % response_code
		var body_str = body.get_string_from_utf8()
		if body_str:
			msg += ": " + body_str
		emit_signal("error_occurred", msg)
