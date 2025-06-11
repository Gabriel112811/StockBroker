# user_database_operations.py
"""
Dieses Modul enthält alle Datenbankoperationen und die Geschäftslogik 
für die Benutzerverwaltung (Login, Registrierung, etc.).
Es ist so konzipiert, dass es von einem Hauptskript importiert wird, 
welches die Datenbankverbindung (conn) bereitstellt und verwaltet.
"""

import sqlite3
import hashlib
import os
from datetime import datetime, timedelta
import secrets


# --- Private Hilfsfunktionen ---
# Der Unterstrich am Anfang signalisiert, dass diese Funktionen
# nur für den internen Gebrauch in diesem Modul gedacht sind.




def _is_username_in_db(conn: sqlite3.Connection, username: str) -> bool:
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM all_users WHERE username = ?", (username,))
    return cursor.fetchone() is not None


def _is_email_in_db(conn: sqlite3.Connection, email: str) -> bool:
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM all_users WHERE email = ?", (email,))
    return cursor.fetchone() is not None


def _is_email_format_valid(email: str) -> bool:
    if email.count('@') != 1:
        return False
    local_part, domain_part = email.split('@', 1)
    if not local_part or not domain_part:
        return False
    if '.' not in domain_part:
        return False
    return True


class UTILITIES:
    """Enthält statische Utility-Methoden, die von mehreren Modulen genutzt werden können."""

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
        rehashed_password, _ = UTILITIES.hash_password(provided_password, salt)
        return rehashed_password == stored_password_hash


class ENDPOINT:
    """
    Diese Klasse enthält alle Funktionen, die von einem Frontend oder Hauptskript aufgerufen werden können.
    Alle Funktionen akzeptieren ein 'conn'-Objekt und geben unser Protokoll-Dictionary zurück.
    """

    @staticmethod
    def create_account(conn: sqlite3.Connection, password: str, email: str, username: str) -> dict:
        output = UTILITIES.get_base_protocol()

        if not all([password, email, username]):
            output["message"] = "Bitte alle Felder ausfüllen, dafür sind sie da!"
            return output

        if not _is_email_format_valid(email):
            output["message"] = "Das E-Mail-Format ist ungültig."
            return output

        # Sequentielle Prüfung auf Existenz
        if _is_username_in_db(conn, username):
            output["message"] = "Dieser Benutzername ist schon vergeben!"
            return output

        if _is_email_in_db(conn, email):
            output["message"] = "Diese E-Mail-Adresse ist schon vergeben!"
            return output

        try:
            hashed_password, salt = UTILITIES.hash_password(password)
            cursor = conn.cursor()

            sql = """
                INSERT INTO all_users (username, password_hash, salt, email, money, joined_date) 
                VALUES (?, ?, ?, ?, ?, ?)
            """
            params = (
                username,
                hashed_password,
                salt,
                email.lower(), #@Fabius Idee
                50000.0,  # Startgeld
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
            cursor.execute(sql, params)

            output["success"] = True
            output["message"] = f"Willkommen, {username}! Dein Account wurde erstellt."
            output["user_id"] = cursor.lastrowid
            output["user_email"] = email.lower()

        except sqlite3.Error:
            output["message"] = f"Es kam zu einem Fehler. Ist nur ein Hobbyprojekt, sorry!"

        return output

    @staticmethod
    def login(conn: sqlite3.Connection, username_email: str, password: str) -> dict:
        output = UTILITIES.get_base_protocol()
        username_email = username_email.lower()

        try:
            # Bestimme, ob mit E-Mail oder Username eingeloggt wird
            if _is_email_format_valid(username_email):
                sql = "SELECT user_id, username, password_hash, salt, email FROM all_users WHERE email = ?"
            else:
                sql = "SELECT user_id, username, password_hash, salt, email FROM all_users WHERE username = ?"

            cursor = conn.cursor()
            cursor.execute(sql, (username_email,))
            user_data = cursor.fetchone()

            if user_data is None:
                output["message"] = ("Benutzername oder E-Mail nicht gefunden. "
                                     "Registrieren oder Tippen lernen!")
                return output

            # Entpacke die Benutzerdaten
            user_id, username, stored_hash, stored_salt, user_email = user_data

            # Überprüfen, ob Hash oder Salt aus der DB fehlen
            if not stored_hash or not stored_salt:
                output["message"] = "Anmeldefehler: Benutzerkonto ist nicht vollständig eingerichtet."
                return output

            # Verifiziere das Passwort mit der sicheren Funktion
            if UTILITIES.verify_password(stored_hash, stored_salt, password):
                output["success"] = True
                output["message"] = f"Willkommen zurück, {username}!"
                output["user_id"] = user_id
                output["user_email"] = user_email
                output["username"] = username
            else:
                output["message"] = "Falsches Passwort. Fettfinger?"

        except sqlite3.Error as e:
            # Fängt Datenbank-spezifische Fehler ab
            print(f"Datenbankfehler beim Login: {e}")
            output["message"] = "Ein Datenbankfehler ist aufgetreten."
        except Exception as e:
            # Fängt alle anderen unerwarteten Fehler ab (z.B. bei der Passwort-Verifizierung)
            print(f"Unerwarteter Fehler beim Login: {e}")
            output["message"] = "Ein unerwarteter interner Fehler ist aufgetreten."

        return output


    @staticmethod
    def get_all_users(conn: sqlite3.Connection) -> list[dict]:
        """ohne sensible Daten wie Passwort-Hashes"""
        # conn.row_factory ermöglicht direkten Zugriff auf Spalten per Namen
        #danke an w3 schools
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, email, money FROM all_users")

        # Erstellt eine Liste von Dictionaries, was viel lesbarer ist
        # eventuell pretty print: pprint()
        users = [dict(row) for row in cursor.fetchall()]

        conn.row_factory = None  # Setze zurück auf Standard
        return users

    @staticmethod
    def get_balance(conn: sqlite3.Connection, username: str=None, user_id: int=None) -> float | None:
        if username is None and user_id is None:
            return None
        if not user_id:
            user_id = UTILITIES.get_user_id(conn, username)

        cursor = conn.cursor()
        cursor.execute("SELECT money FROM all_users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else None

    @staticmethod
    def update_balance(conn: sqlite3.Connection, username: str, amount: float, only_subtract:bool=False) -> bool:
        """
        Aktualisiert den Kontostand eines Benutzers atomar. #danke an w3schools
        Ein positiver Betrag fügt Geld hinzu, ein negativer Betrag zieht Geld ab.
        """
        # Falls irgendwoher eine Aktie oder
        # Transaktion mit negativem Wert kommt
        if only_subtract and amount > 0:
            return False

        current_balance = ENDPOINT.get_balance(conn, username=username)
        if current_balance is None:
            return False  # Benutzer existiert nicht

        # Verhindere, dass der Kontostand unter 0 fällt
        if current_balance + amount < 0:
            return False

        try:
            cursor = conn.cursor()
            # Atomares Update: Sicher gegen Race Conditions
            sql = "UPDATE all_users SET money = money + ? WHERE username = ?"
            cursor.execute(sql, (amount, username))
            return cursor.rowcount > 0  # Gibt True zurück, wenn eine Zeile geändert wurde
        except sqlite3.Error:
            return False

    @staticmethod
    def request_password_reset(conn: sqlite3.Connection, email: str) -> dict:
        """
        Startet den Prozess zum Zurücksetzen des Passworts.
        Generiert einen Token und speichert ihn in der DB.
        """
        output = UTILITIES.get_base_protocol()
        cursor = conn.cursor()

        # Finde den Benutzer anhand der E-Mail
        cursor.execute("SELECT user_id FROM all_users WHERE email = ?", (email.lower(),))
        user_row = cursor.fetchone()

        if user_row is None:
            # Aus Sicherheitsgründen geben wir keine Info, ob die E-Mail existiert.
            output[
                "message"] = "Wenn ein Account mit dieser E-Mail existiert, wurde eine Anleitung zum Zurücksetzen gesendet."
            output["success"] = True  # Der Prozess für den User ist hier "erfolgreich"
            return output

        user_id = user_row[0]

        # Generiere einen sicheren, zufälligen Token
        token = secrets.token_hex(32)
        # Setze die Gültigkeit auf 1 Stunde
        expires_at = datetime.now() + timedelta(hours=1)

        try:
            # Speichere den Token in der neuen Tabelle
            sql = "INSERT INTO login_tokens (token, user_id_fk, expires_at) VALUES (?, ?, ?)"
            cursor.execute(sql, (token, user_id, expires_at.strftime('%Y-%m-%d %H:%M:%S')))

            # --- HIER WÜRDE DER E-MAIL-VERSAND STATTFINDEN ---
            # z.B. mit smtplib oder einem E-Mail-Service
            reset_link = f"https://deine-webseite.de/reset-password?token={token}"
            print(f"DEBUG: Passwort-Reset-Link für user_id {user_id}: {reset_link}")
            # ---------------------------------------------------

            output[
                "message"] = "Wenn ein Account mit dieser E-Mail existiert, wurde eine Anleitung zum Zurücksetzen gesendet."
            output["success"] = True

        except sqlite3.Error as e:
            output["message"] = f"Datenbankfehler: {e}"

        return output

    @staticmethod
    def verify_reset_token(conn: sqlite3.Connection, token: str) -> dict:
        """Überprüft, ob ein Token gültig und nicht abgelaufen ist."""
        output = UTILITIES.get_base_protocol()
        cursor = conn.cursor()

        sql = "SELECT expires_at FROM login_tokens WHERE token = ?"
        cursor.execute(sql, (token,))
        result = cursor.fetchone()

        if result is None:
            output["message"] = "Ungültiger oder abgelaufener Token."
            return output

        expires_at = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')

        if datetime.now() > expires_at:
            output["message"] = "Token ist abgelaufen."
        else:
            output["success"] = True
            output["message"] = "Token ist gültig."

        return output

    @staticmethod
    def reset_password_with_token(conn: sqlite3.Connection, token: str, new_password: str) -> dict:
        """Setzt das Passwort mit einem gültigen Token zurück."""
        output = UTILITIES.get_base_protocol()

        # Zuerst den Token verifizieren
        verification = ENDPOINT.verify_reset_token(conn, token)
        if not verification["success"]:
            return verification  # Gibt die Fehlermeldung von verify_reset_token zurück

        cursor = conn.cursor()
        # Hole die User-ID, die zum Token gehört
        cursor.execute("SELECT user_id_fk FROM login_tokens WHERE token = ?", (token,))
        result = cursor.fetchone()

        if result is None:
            # Sollte nicht passieren, wenn die Verifizierung erfolgreich war, aber sicher ist sicher.
            output["message"] = "Ungültiger Token."
            return output

        user_id = result[0]

        try:
            # Erstelle einen neuen Hash und Salt für das neue Passwort
            new_hashed_password, new_salt = UTILITIES.hash_password(new_password)

            # Aktualisiere das Passwort des Benutzers in der Haupttabelle
            update_sql = "UPDATE all_users SET password_hash = ?, salt = ? WHERE user_id = ?"
            cursor.execute(update_sql, (new_hashed_password, new_salt, user_id))

            # Lösche den benutzten Token, damit er nicht wiederverwendet werden kann
            delete_sql = "DELETE FROM login_tokens WHERE token = ?"
            cursor.execute(delete_sql, (token,))

            output["success"] = True
            output["message"] = "Ihr Passwort wurde erfolgreich zurückgesetzt."

        except sqlite3.Error as e:
            output["message"] = f"Datenbankfehler beim Zurücksetzen des Passworts: {e}"

        return output
