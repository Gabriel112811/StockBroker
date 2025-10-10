# tichu/tichu.py
import random

# --- Konstanten und globaler Spielzustand (Single Source of Truth) ---
MAX_PLAYERS = 4
players = {}  # Speichert SID und zugehörige Spieler-ID -> {'sid1': 'player1', 'sid2': 'player2'}
game_state = {
    "message": "Warte auf Spieler...",
    "played_cards": [],
    "player_hands": {}  # Speichert Handkarten für jede Spieler-ID -> {'player1': ['H7', 'D5'], ...}
}


# --- Funktionen zur Zustandsverwaltung ---

def add_player(sid):
    """Fügt einen neuen Spieler zum Spiel hinzu und gibt seine ID zurück."""
    if len(players) >= MAX_PLAYERS:
        return None  # Spiel ist voll

    player_num = 1
    while f"player{player_num}" in players.values():
        player_num += 1
    player_id = f"player{player_num}"

    players[sid] = player_id
    game_state["player_hands"][player_id] = []  # Leere Hand initialisieren
    print(f"Spieler {player_id} ({sid}) hinzugefügt.")
    return player_id


def remove_player(sid):
    """Entfernt einen Spieler aus dem Spiel und gibt seine ID zurück."""
    if sid in players:
        player_id = players[sid]
        del players[sid]
        if player_id in game_state["player_hands"]:
            del game_state["player_hands"][player_id]

        game_state["message"] = f"Spieler {player_id} hat das Spiel verlassen."
        print(f"Spieler {player_id} ({sid}) entfernt.")
        return player_id
    return None


def process_played_cards(sid, cards_to_play):
    """Verarbeitet den Spielzug eines Spielers und aktualisiert den Spielzustand."""
    player_id = players.get(sid)
    if not player_id:
        return  # Spieler nicht gefunden

    player_hand = game_state["player_hands"][player_id]

    # Validierung
    can_play = all(card in player_hand for card in cards_to_play)

    if not can_play:
        game_state["message"] = f"{player_id}, du hast diese Karten nicht! Ungültiger Zug."
    elif not cards_to_play:
        game_state["message"] = f"{player_id} hat versucht, keine Karten zu senden."
    else:
        game_state["message"] = f"{player_id} hat {', '.join(cards_to_play)} gespielt."
        # Karten aus der Hand entfernen
        game_state["player_hands"][player_id] = [card for card in player_hand if card not in cards_to_play]
        # Karten zum Ablagestapel hinzufügen
        game_state["played_cards"].extend(cards_to_play)


def start_game():
    """Initialisiert das Spiel, mischt das Deck und teilt Karten aus."""
    suits = ["red", "green", "blue", "black"]
    letters = [str(i) for i in range(2, 10+1)] + ["J", "Q", "K", "A"]
    values = {rank:i+2 for i, rank in enumerate(letters)}
    deck = []
    for suit in suits:
        for rank in letters:
            deck.append({
                "color": suit,
                "string": rank,
                "value": values[rank],
                "is_hund": False,
                "is_phoenix": False,
                "is_drache": False,
                "is_eins": False,
            })
    for i in ["Hund", "Phoenix", "Drache", "Eins"]:
        deck.append({
            "color": None,
            "string": i,
            "value": 1,
            "is_hund": i is "Hund",
            "is_phoenix": i is "Phoenix",
            "is_drache": i is "Drache",
            "is_eins": i is "Eins"
        })

    print(deck)

    random.shuffle(deck)

    player_ids = list(game_state["player_hands"].keys())

    # Beispiel: Jeder Spieler bekommt 7 Karten
    for i, card in enumerate(deck):
        player_index = i % len(player_ids)
        player_id = player_ids[player_index]
        if len(game_state["player_hands"][player_id]) < 12:
            game_state["player_hands"][player_id].append(card)

    game_state["message"] = "Das Spiel hat begonnen! Du bist am Zug."
    print("Spiel gestartet, Karten ausgeteilt.")

if __name__ == "__main__":
    start_game()