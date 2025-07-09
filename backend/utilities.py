import os
import sqlite3
import hashlib
from urllib.parse import urlparse
import re
import locale
from datetime import datetime

def _date_to_month_year(join_date_string:str) -> str:
    try:
        locale.setlocale(locale.LC_TIME, 'de_DE.UTF-8')
    except locale.Error:
        print("Deutsche Lokale 'de_DE.UTF-8' nicht installiert. Versuche andere.")
        try:
            locale.setlocale(locale.LC_TIME, 'de_DE')
        except locale.Error:
            print("Fallback auf Standard-Lokale.")

    date_obj = datetime.strptime(join_date_string, '%Y-%m-%d %H:%M:%S')

    formatted_date = date_obj.strftime('%B, %Y')

    return formatted_date


class Utilities:
    """
    Enthält statische Utility-Methoden, die von mehre
    ren Modulen genutzt werden können."""

    @staticmethod
    def get_base_protocol() -> dict:
        """Erstellt und gibt eine frische Kopie des Standard-Antwortprotokolls zurück."""
        return {
            "success": False,
            "user_id": None,
            "user_email": None,
            "message": "",
        }

    @staticmethod
    def get_user_id(conn: sqlite3.Connection, username: str) -> int | None:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM all_users WHERE username = ?", (username,))
        result = cursor.fetchone()
        return result[0] if result else None

    @staticmethod
    def get_username(conn: sqlite3.Connection, user_id: int) -> str | None:
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM all_users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else None

    @staticmethod
    def get_many_usernames(
            conn: sqlite3.Connection, user_ids: set[int]) -> dict[int, str] | None:
        placeholders = ', '.join(['?'] * len(user_ids))
        sql_query = f"SELECT user_id, username FROM all_users WHERE user_id IN ({placeholders})"

        cursor = conn.cursor()
        cursor.execute(sql_query, list(user_ids))

        return {user_id: username for user_id, username in cursor.fetchall()}

    @staticmethod
    def is_username_in_db(conn: sqlite3.Connection, username: str) -> bool:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM all_users WHERE username = ?", (username,))
        return cursor.fetchone() is not None

    @staticmethod
    def hash_password(password: str, salt: bytes = None) -> tuple[str, str]:
        """Hasht ein Passwort sicher mit einem Salt."""
        if salt is None:
            salt = os.urandom(16)
        hashed_password = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return hashed_password.hex(), salt.hex()

    @staticmethod
    def verify_password(stored_password_hash: str, stored_salt_hex: str, provided_password: str) -> bool:
        """Überprüft, ob das angegebene Passwort mit dem gespeicherten Hash übereinstimmt."""
        salt = bytes.fromhex(stored_salt_hex)
        rehashed_password, _ = Utilities.hash_password(provided_password, salt)
        return rehashed_password == stored_password_hash

    @staticmethod
    def get_join_date(conn: sqlite3.Connection, username: str) -> str | None:
        cursor = conn.cursor()
        cursor.execute("SELECT joined_date FROM all_users WHERE username = ?", (username,))
        result = cursor.fetchone()
        return result[0] if result else None

    @staticmethod
    def is_username_valid(conn, username:str) -> dict:
        username = username.lower()
        output = Utilities.get_base_protocol()
        forbidden_words = ["hitler", "penis"]
        forbidden_usernames = ["laurens", "fabius"]
        if len(username) < 3:
            output["message"] = "Zu kurz!"
            return output
        if len(username) > 20:
            output["message"] = "Viel zu lang!"
            return output
        for word in forbidden_words:
            if word.lower() in username.lower():
                output["message"] = f"Enthält verbotene Worte: {word}"
                return output

        if username in forbidden_usernames:
            output["message"] = "Dieser Benutzername ist nicht erlaubt"
            return output

        date = Utilities.get_join_date(conn, username)
        if date:
            output["message"] = f"Dieser Benutzername ist bereits seit {_date_to_month_year(date)} vergeben!"
            print(_date_to_month_year(date))
            #evtl ist es nicht so schlau, dass man so von Jeem Nutzer das beitritsdatum sehen kann.
            return output

        output = Utilities.get_base_protocol()
        output.update({"success": True, "message":"Verfügbar"})
        return output

    @staticmethod
    def is_ig_link_valid(url: str) -> dict[str, str]:
        """
        Überprüft, ob ein String ein Link zu einem Instagram-PROFIL ist.

        Die Funktion stellt sicher, dass es sich um die Domain instagram.com handelt
        und der Link nicht zu einem bestimmten Inhalt wie einem Beitrag, Reel oder einer Story führt.

        Args:
            url: Der zu überprüfende String.

        Returns:
            True, wenn der String ein Link zu einem Instagram-Profil ist, sonst False.
        """
        # URLs ohne http/https anfügen, damit urlparse korrekt funktioniert
        if url is None:
            result = Utilities.get_base_protocol()
            result.update({"message":"Die URL ist ungültig"})
            return result

        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        try:
            parsed_url = urlparse(url)
        except ValueError:
            result = Utilities.get_base_protocol()
            result.update({"message":"Die URL ist ungültig"})
            return result

        # 1. Überprüfung der Top-Level-Domain (Netloc)
        # Erlaubt 'instagram.com' oder 'www.instagram.com'
        if parsed_url.netloc not in ['instagram.com', 'www.instagram.com', 'instagram.de', "www.instagram.de"]:
            result = Utilities.get_base_protocol()
            result.update({"message":"Die URL gehört nicht zu Instagram"})
            return result

        # 2. Überprüfung der Pfadstruktur
        path = parsed_url.path

        # Pfad muss vorhanden sein und mehr als nur '/' enthalten
        if not path or path == '/':
            result = Utilities.get_base_protocol()
            result.update({"message":"Du bist Instagram?"})
            return result

        # Entferne führende und nachfolgende Schrägstriche für die Analyse
        path_segments = path.strip('/').split('/')

        # Prüfen, ob das erste Segment ein bekannter Inhaltspfad ist
        bekannte_inhaltspfade = ['p', 'reel', 'stories', 'tv', 'explore', 'accounts', 'direct']
        if path_segments[0] in bekannte_inhaltspfade:
            result = Utilities.get_base_protocol()
            result.update({"message":"Die URL führt nicht zu einem Profil"})
            return result


        # 3. Validierung des Benutzernamens
        username = path_segments[0]

        # Instagram-Benutzernamen: 1-30 Zeichen, Buchstaben, Zahlen, Unterstriche, Punkte.
        # Darf nicht mit einem Punkt beginnen oder enden und keine aufeinanderfolgenden Punkte enthalten.
        if '..' in username or not (1 <= len(username) <= 30):
            result = Utilities.get_base_protocol()
            result.update({"message": "ungültiger Instagram Benutzername"})
            return result

        # Regex prüft auf gültige Zeichen und stellt sicher, dass Anfang/Ende kein Punkt ist.
        username_regex = r'^[a-z0-9_](?:[a-z0-9_.]*[a-z0-9_])?$'
        if not re.fullmatch(username_regex, username.lower()):  # Instagram-Namen sind case-insensitive
            result = Utilities.get_base_protocol()
            result.update({"message":"Die URL beinhaltet ungültige Zeichen"})
            return result

        result = Utilities.get_base_protocol()
        result.update({"success": True, "message":"gültig"})
        return result
