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
        """Erzeugt einen E-Mail-Verifizierung-Token (10 Minuten gültig)."""
        return _generate_and_store_token(conn, user_id, 'EMAIL_VERIFICATION', lifespan_seconds=600)

    @staticmethod
    def generate_password_token(conn: sqlite3.Connection, user_id: int) -> str:
        """Erzeugt einen Passwort-Reset-Token (10 Minuten gültig)."""
        # Passend zur E-Mail Vorlage auf 10 Minuten (600 Sekunden) gesetzt
        return _generate_and_store_token(conn, user_id, 'PASSWORD_RESET', lifespan_seconds=600)

    @staticmethod
    def generate_instant_register_token(conn: sqlite3.Connection) -> str:
        """Erzeugt einen Registrierungs-Token (1 Jahr gültig), nicht an einen User gebunden."""
        return _generate_and_store_token(conn, None, 'INSTANT_REGISTER', lifespan_seconds=365*24*3600)

    @staticmethod
    def verify_email_token(conn: sqlite3.Connection, token: str) -> int | None:
        """
        Verifiziert einen E-Mail-Token und gibt bei Erfolg die user_id zurück.
        """
        return _verify_and_consume_token(conn, token, 'EMAIL_VERIFICATION')

    @staticmethod
    def verify_and_consume_password_token(conn: sqlite3.Connection, token: str) -> dict:
        """
        Verifiziert einen Passwort-Reset-Token und gibt bei Erfolg die user_id zurück.
        """
        user_id = _verify_and_consume_token(conn, token, 'PASSWORD_RESET')
        if user_id:
             return {"success": True, "user_id": user_id, "message": "Token valide"}
        return {"success": False, "message": "Token ungültig oder abgelaufen"}

    @staticmethod
    def verify_but_not_consume_password_token(conn: sqlite3.Connection, token: str) -> dict:
        """
        Verifiziert einen Passwort-Reset-Token und gibt bei Erfolg die user_id zurück.
        """
        user_id = _verify_but_not_consume_token(conn, token, 'PASSWORD_RESET')
        if user_id:
            return {"success": True, "user_id": user_id, "message": "Token valide"}
        return {"success": False, "message": "Token ungültig oder abgelaufen"}

    @staticmethod
    def verify_instant_register_token(conn: sqlite3.Connection, token: str) -> bool:
        """
        Verifiziert und konsumiert einen Registrierungs-Token. Gibt True bei Erfolg zurück.
        """
        # Diese Methode ist speziell, da sie keinen User zurückgibt.
        # Sie gibt einfach an, ob der Token gültig war und konsumiert wurde.
        hashed_token = _hash_token(token)
        cursor = conn.cursor()
        find_sql = "SELECT id FROM secure_tokens WHERE token_hash = ? AND token_type = 'INSTANT_REGISTER' AND expires_at > ?"
        cursor.execute(find_sql, (hashed_token, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        result = cursor.fetchone()

        if result:
            token_id = result[0]
            cursor.execute("DELETE FROM secure_tokens WHERE id = ?", (token_id,))
            return True # Token war valide und wurde konsumiert
        return False # Token nicht gefunden oder abgelaufen

    @staticmethod
    def remove_expired_tokens():
        pass


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
    length = 8 if lifespan_seconds <= 1000 else 20
    raw_token = _generate_token(length=length)
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


    result = _verify_but_not_consume_token(conn, raw_token, expected_type)

    if not result:
        return None

    user_id = result['user_id']
    token_id = result['token_id']

    cursor = conn.cursor()
    cursor.execute("DELETE FROM secure_tokens WHERE id = ?", (token_id,))
    cursor.connection.commit()

    return user_id

def _verify_but_not_consume_token(conn: sqlite3.Connection, raw_token: str, expected_type: str) -> dict | None:
    """
    Interne Kernfunktion: Verifiziert und löscht einen Token, um Wiederverwendung zu verhindern.
    Gibt die user_id bei Erfolg zurück, sonst None.
    """
    hashed_token = _hash_token(raw_token)

    cursor = conn.cursor()

    sql_find = "SELECT id, user_id_fk, expires_at FROM secure_tokens WHERE token_hash = ? AND token_type = ?"

    cursor.execute(sql_find, (hashed_token, expected_type))
    result = cursor.fetchone()

    if not result:
        return None  # Token nicht gefunden oder falscher Typ

    token_id, user_id, expires_at_str = result
    expires_at = datetime.fromisoformat(expires_at_str)

    if datetime.now() > expires_at:
        cursor.execute("DELETE FROM secure_tokens WHERE id = ?", (token_id,))
        cursor.connection.commit()
        return None

    return {"user_id": user_id, "token_id": token_id}