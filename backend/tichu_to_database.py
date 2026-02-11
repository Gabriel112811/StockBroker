# game_logic.py

def handle_player_connect(user_id, socket_id):
    print("hallo")
    return
    # Hier Logik: Spieler zur Liste aktiver Spieler hinzufügen
    # Z.B. active_players[user_id] = socket_id

def handle_player_disconnect(user_id):
    return
    # Hier Logik: Spieler als offline markieren oder aus Match entfernen

def handle_game_move(user_id, message_data):
    try:
        number = int(message_data)
        if number == 67:
            return f"Id:{user_id}:  Suuuiiiiiiii"
        else:
            return f"id:{user_id}:  Its not six-seven! Grrrrr"
    except Exception:
        return f"id:{user_id}: Not a Number - NaN"

