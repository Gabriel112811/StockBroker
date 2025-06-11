# token_system.py
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta


class TokenEndpoint:
    """
    Verwaltet die Erstellung und Verifizierung von sicheren, kurzlebigen Tokens.
    """



    @staticmethod
    def generate_email_token(conn: sqlite3.Connection, user_id: int) -> str:
        """Erzeugt einen E-Mail-Verifizierung-Token (1 Tag gültig)."""
        return _generate_and_store_token(conn, user_id, 'EMAIL_VERIFICATION', lifespan_seconds=86400)

    @staticmethod
    def generate_password_token(conn: sqlite3.Connection, user_id: int) -> str:
        """Erzeugt einen Passwort-Reset-Token (1 Stunde gültig)."""
        return _generate_and_store_token(conn, user_id, 'PASSWORD_RESET', lifespan_seconds=3600)

    @staticmethod
    def generate_admin_token(conn: sqlite3.Connection, user_id: int) -> str:
        """Erzeugt einen Admin-Token (8 Stunden gültig)."""
        return _generate_and_store_token(conn, user_id, 'ADMIN_ACCESS', lifespan_seconds=28800)

    @staticmethod
    def generate_instant_register_token(conn: sqlite3.Connection) -> str:
        """Erzeugt einen Registrierungs-Token (7 Tage gültig), nicht an einen User gebunden."""
        return _generate_and_store_token(conn, None, 'INSTANT_REGISTER', lifespan_seconds=604800)

    # --- Öffentliche Verify-Methoden ---

    @staticmethod
    def verify_email_token(conn: sqlite3.Connection, token: str) -> bool:
        """Verifiziert einen E-Mail-Token."""
        user_id = _verify_and_consume_token(conn, token, 'EMAIL_VERIFICATION')
        return user_id is not None

    @staticmethod
    def verify_password_token(conn: sqlite3.Connection, token: str) -> bool:
        """Verifiziert einen Passwort-Reset-Token."""
        user_id = _verify_and_consume_token(conn, token, 'PASSWORD_RESET')
        return user_id is not None

    @staticmethod
    def verify_admin_token(conn: sqlite3.Connection, token: str) -> bool:
        """Verifiziert einen Admin-Token."""
        user_id = _verify_and_consume_token(conn, token, 'ADMIN_ACCESS')
        return user_id is not None

    @staticmethod
    def verify_instant_register_token(conn: sqlite3.Connection, token: str) -> bool:
        """Verifiziert einen Registrierungs-Token."""
        # Hier ist die user_id bei Erfolg None, da sie nicht existiert.
        # Der Rückgabewert der internen Funktion (None bei Erfolg) wird korrekt zu True.
        result = _verify_and_consume_token(conn, token, 'INSTANT_REGISTER')
        # Der Aufruf war erfolgreich, wenn ein Token gefunden und konsumiert wurde.
        # Im Erfolgsfall gibt _verify_and_consume_token die user_id zurück (hier: None)
        # Wir brauchen eine Prüfung, die auf den erfolgreichen Fund reagiert.
        # Eine kleine Anpassung: _verify_and_consume_token gibt bei Erfolg immer die user_id oder 'SUCCESS_NO_USER' zurück.
        # Hier vereinfacht: Wenn die Funktion durchläuft ohne Fehler, war es valide.
        # Die Logik ist hier leicht anders: der Aufruf an sich ist der Check.
        # Ein Hack wäre `return result is None`, aber das ist unsauber.
        # Saubere Lösung: `_verify_and_consume_token` muss klar signalisieren "gefunden und konsumiert".
        # Für jetzt belassen wir die Logik so, dass `is not None` auf eine User ID prüft, was für diesen Fall nicht passt.

        # Korrigierte Logik für diesen speziellen Fall:
        hashed_token = _hash_token(token)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM secure_tokens WHERE token_hash = ? AND token_type = 'INSTANT_REGISTER' AND expires_at > ?",
            (hashed_token, datetime.now()))
        result = cursor.fetchone()
        if result:
            cursor.execute("DELETE FROM secure_tokens WHERE id = ?", (result[0],))
            return True
        return False
    
    

def _generate_token(length: int = 32) -> str:
    """Erzeugt einen kryptografisch sicheren, URL-freundlichen Token."""
    return secrets.token_urlsafe(length)

def _hash_token(raw_token: str) -> str:
    """Hasht einen Token konsistent mit SHA-256 für die Speicherung."""
    return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

def _generate_and_store_token(conn: sqlite3.Connection, user_id: int | None, token_type: str,
                              lifespan_seconds: int) -> str:
    """
    Interne Kernfunktion: Erzeugt Token, speichert Hash und gibt rohen Token zurück.
    """
    raw_token = _generate_token()
    hashed_token = _hash_token(raw_token)

    now = datetime.now()
    expires = now + timedelta(seconds=lifespan_seconds)

    sql = """
        INSERT INTO secure_tokens (user_id_fk, token_hash, token_type, expires_at)
        VALUES (?, ?, ?, ?)
    """
    cursor = conn.cursor()
    cursor.execute(sql, (user_id, hashed_token, token_type, expires))

    # Der rohe Token wird nur einmal zurückgegeben und niemals gespeichert!
    return raw_token

def _verify_and_consume_token(conn: sqlite3.Connection, raw_token: str, expected_type: str) -> int | None:
    """
    Interne Kernfunktion: Verifiziert und löscht einen Token, um Wiederverwendung zu verhindern.
    Gibt die user_id bei Erfolg zurück, sonst None.
    """
    hashed_token = _hash_token(raw_token)

    sql_find = "SELECT id, user_id_fk, expires_at FROM secure_tokens WHERE token_hash = ? AND token_type = ?"
    cursor = conn.cursor()

    cursor.execute(sql_find, (hashed_token, expected_type))
    result = cursor.fetchone()

    if not result:
        return None  # Token nicht gefunden oder falscher Typ

    token_id, user_id, expires_at_str = result
    expires_at = datetime.fromisoformat(expires_at_str)

    if datetime.now() > expires_at:
        # Token ist abgelaufen, löschen wir ihn trotzdem
        cursor.execute("DELETE FROM secure_tokens WHERE id = ?", (token_id,))
        return None

        # Token ist gültig. Löschen, um Wiederverwendung zu verhindern ("consume").
    cursor.execute("DELETE FROM secure_tokens WHERE id = ?", (token_id,))

    return user_id