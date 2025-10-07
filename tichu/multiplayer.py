# tichu/multiplayer.py
from flask import request
from flask_socketio import emit

# Importiere den Zustand und die Logik-Funktionen aus der tichu.py Datei
from . import tichu


def register_handlers(socketio):
    """Registriert alle SocketIO-Event-Handler."""

    @socketio.on('connect')
    def handle_connect():
        """Wird aufgerufen, wenn sich ein neuer Spieler verbindet."""
        sid = request.sid
        player_id = tichu.add_player(sid)

        if player_id is None:
            emit('game_full', {'message': 'Das Spiel ist leider schon voll.'})
            return

        # Teile dem Client seine Spieler-ID mit
        emit('assign_player_id', {'player_id': player_id})

        # Wenn genügend Spieler da sind, starte das Spiel (hier nur als Bsp. mit 2)
        if len(tichu.players) == 2:
            tichu.start_game()
        else:
            tichu.game_state["message"] = f"Warte auf weitere Spieler... ({len(tichu.players)}/{tichu.MAX_PLAYERS})"

        # Sende den aktuellen Zustand an ALLE
        emit('update_state', tichu.game_state, broadcast=True)

    @socketio.on('disconnect')
    def handle_disconnect():
        """Wird aufgerufen, wenn ein Spieler die Verbindung trennt."""
        sid = request.sid
        if tichu.remove_player(sid):
            # Sende den neuen Zustand an die verbleibenden Spieler
            emit('update_state', tichu.game_state, broadcast=True)

    @socketio.on('play_cards')
    def handle_play_cards(data):
        """Verarbeitet den Spielzug eines Spielers."""
        sid = request.sid
        cards_to_play = data.get("played_cards", [])

        tichu.process_played_cards(sid, cards_to_play)

        # Sende den aktualisierten Zustand an ALLE verbundenen Clients
        emit('update_state', tichu.game_state, broadcast=True)