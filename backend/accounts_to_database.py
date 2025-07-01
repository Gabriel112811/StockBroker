import sqlite3
import hashlib
import os
from datetime import datetime, timedelta
import locale
import re
from urllib.parse import urlparse

if not __name__ == "__main__":
    from backend.tokens import TokenEndpoint
    from backend.send_emails import send_confirmation_email


def _strip_submails(adress:str) -> str:
    """Entfernt die meisten unnötigen + und Punkte"""
    if not _is_email_format_valid(adress):
        return adress
    username, domain = adress.split("@")
    dot_is_optional = domain in ["gmail.com", "protonmail.com"]

    if dot_is_optional:
        username.replace(".", "")

    username = username.split("+")[0] #Ich+Fan@gmail.com wird zu Ich@gmail.com, da das die main ist

    return f"{username}@{domain}"

def _is_email_in_db(conn: sqlite3.Connection, email: str, include_submails:bool=True) -> bool:
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

def _update_last_login_date(conn: sqlite3.Connection, user_id:int):
    cursor = conn.cursor()
    login_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("UPDATE all_users SET last_login = ? WHERE user_id = ?", (login_time, user_id))


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
        rehashed_password, _ = UTILITIES.hash_password(provided_password, salt)
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
        output = UTILITIES.get_base_protocol()
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

        date = UTILITIES.get_join_date(conn, username)
        if date:
            output["message"] = f"Dieser Benutzername ist bereits seit {_date_to_month_year(date)} vergeben!"
            print(_date_to_month_year(date))
            #evtl ist es nicht so schlau, dass man so von Jeem Nutzer das beitritsdatum sehen kann.
            return output

        output = UTILITIES.get_base_protocol()
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
            result = UTILITIES.get_base_protocol()
            result.update({"message":"Die URL ist ungültig"})
            return result

        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        try:
            parsed_url = urlparse(url)
        except ValueError:
            result = UTILITIES.get_base_protocol()
            result.update({"message":"Die URL ist ungültig"})
            return result

        # 1. Überprüfung der Top-Level-Domain (Netloc)
        # Erlaubt 'instagram.com' oder 'www.instagram.com'
        if parsed_url.netloc not in ['instagram.com', 'www.instagram.com', 'instagram.de', "www.instagram.de"]:
            result = UTILITIES.get_base_protocol()
            result.update({"message":"Die URL gehört nicht zu Instagram"})
            return result

        # 2. Überprüfung der Pfadstruktur
        path = parsed_url.path

        # Pfad muss vorhanden sein und mehr als nur '/' enthalten
        if not path or path == '/':
            result = UTILITIES.get_base_protocol()
            result.update({"message":"Du bist Instagram?"})
            return result

        # Entferne führende und nachfolgende Schrägstriche für die Analyse
        path_segments = path.strip('/').split('/')

        # Prüfen, ob das erste Segment ein bekannter Inhaltspfad ist
        bekannte_inhaltspfade = ['p', 'reel', 'stories', 'tv', 'explore', 'accounts', 'direct']
        if path_segments[0] in bekannte_inhaltspfade:
            result = UTILITIES.get_base_protocol()
            result.update({"message":"Die URL führt nicht zu einem Profil"})
            return result


        # 3. Validierung des Benutzernamens
        username = path_segments[0]

        # Instagram-Benutzernamen: 1-30 Zeichen, Buchstaben, Zahlen, Unterstriche, Punkte.
        # Darf nicht mit einem Punkt beginnen oder enden und keine aufeinanderfolgenden Punkte enthalten.
        if '..' in username or not (1 <= len(username) <= 30):
            result = UTILITIES.get_base_protocol()
            result.update({"message": "ungültiger Instagram Benutzername"})
            return result

        # Regex prüft auf gültige Zeichen und stellt sicher, dass Anfang/Ende kein Punkt ist.
        username_regex = r'^[a-z0-9_](?:[a-z0-9_.]*[a-z0-9_])?$'
        if not re.fullmatch(username_regex, username.lower()):  # Instagram-Namen sind case-insensitive
            result = UTILITIES.get_base_protocol()
            result.update({"message":"Die URL beinhaltet ungültige Zeichen"})
            return result

        result = UTILITIES.get_base_protocol()
        result.update({"success": True, "message":"gültig"})
        return result


class ENDPOINT:
    """
    Diese Klasse enthält alle Funktionen, die von einem Frontend oder Hauptskript aufgerufen werden können.
    Alle Funktionen akzeptieren ein 'conn'-Objekt und geben unser Protokoll-Dictionary zurück.
    """
    @staticmethod
    def create_account(conn: sqlite3.Connection, password: str, email: str, username: str,
                       instant_register_token: str = None) -> dict:
        output = UTILITIES.get_base_protocol()
        output['email_verification_required'] = False

        error_messages = []

        email = _strip_submails(email)
        username = username.lower()

        if not UTILITIES.is_username_valid(conn, username).get("success"):
            error_messages.append("Da steht doch sogar, dass dieser Benutzername nicht geht!!!")

        if not all([password, email, username]):
            error_messages.append("Bitte alle Felder ausfüllen.")

        if len(password) < 6:
            error_messages.append("Das Passwort muss mindestens 6 Zeichen lang sein.")

        if not _is_email_format_valid(email):
            error_messages.append("Das E-Mail-Format ist ungültig.")

        # jetzt in is_username_valid()
        #if UTILITIES.is_username_in_db(conn, username):
            #error_messages.append("Dieser Benutzername ist schon vergeben.")

        if _is_email_in_db(conn, email, include_submails=True):
            pass
            #error_messages.append("Diese E-Mail-Adresse ist schon vergeben.")

        if len(error_messages) == 1:
            output['message'] = error_messages[0]
            return output
        elif len(error_messages) > 1:
            output['message'] = '+++'.join(f"- {fehler}" for fehler in error_messages) #Com on das ist so fucking geiler code
            print(output['message'])
            #Diese wunderbahre Comprehension
            #this is Python!
            return output


        is_verified = 0  # Standard: nicht verifiziert
        if instant_register_token:
            if TokenEndpoint.verify_instant_register_token(conn, instant_register_token):
                is_verified = 1
                print(f"Instant-Register-Token '{instant_register_token}' erfolgreich validiert.")
            else:
                output["message"] = "Der angegebene Registrierungs-Code ist ungültig oder abgelaufen."
                return output

        try:
            hashed_password, salt = UTILITIES.hash_password(password)
            cursor = conn.cursor()
            sql_command = """
                INSERT INTO all_users (username, password_hash, salt, email, money, joined_date, is_verified, last_login) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                username,
                hashed_password,
                salt,
                email.lower(),
                50000.0,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                is_verified,
                None
            )
            cursor.execute(sql_command, params)


            output["success"] = True
            output["user_email"] = email.lower()
            user_id = UTILITIES.get_user_id(conn, username)

            if is_verified == 1:
                output["message"] = f"Willkommen, {username}! Dein Account wurde erstellt und ist sofort aktiv."
            else:

                # E-Mail senden (Funktion muss den Link zur App enthalten)
                result = send_confirmation_email(
                    recipient_email=email.lower(),
                    user_name=username,
                    confirmation_code=TokenEndpoint.generate_email_token(conn, user_id)
                )

                output["email_verification_required"] = True
                if result:
                    output[
                        "message"] = f"Willkommen, {username}! Dein Account wurde erstellt. Bitte prüfe deine E-Mails, um ihn zu aktivieren."
                else:
                    output[
                        "message"] = f"Es ist ein Fehler aufgetreten! Sorry :("

            Settings.initialize_settings_for_user(conn, user_id)

        except sqlite3.Error as e:
            output["message"] = f"Es kam zu einem Datenbankfehler: {e}"
        return output

    @staticmethod
    def login(conn: sqlite3.Connection, username_email: str, password: str) -> dict:
        output = UTILITIES.get_base_protocol()
        username_email = str(username_email).lower()
        #try:
        if _is_email_format_valid(username_email):

            username_email = _strip_submails(username_email)

            sql = "SELECT user_id, username, password_hash, salt, email, is_verified FROM all_users WHERE email = ?"
        else:
            sql = "SELECT user_id, username, password_hash, salt, email, is_verified FROM all_users WHERE username = ?"
        cursor = conn.cursor()
        cursor.execute(sql, (username_email,))
        user_data = cursor.fetchone()

        if user_data is None:
            output["message"] = "Benutzername oder E-Mail nicht gefunden."
            return output

        user_id, username, stored_hash, stored_salt, user_email, is_verified = user_data

        if not UTILITIES.verify_password(stored_hash, stored_salt, password):
            output["message"] = "Falsches Passwort."
            return output

        # NEUER CHECK: Ist der Account verifiziert?
        if not is_verified:
            output["message"] = "Dein Account ist noch nicht verifiziert. Bitte prüfe deine E-Mails."
            # Optional: Neuen Token senden
            # verification_token = TokenEndpoint.generate_email_token(conn, user_id)
            # send_confirmation_email(user_email, username, verification_token)
            return output

        ENDPOINT.update_last_login_date(conn, user_id)

        output["success"] = True
        output["message"] = f"Willkommen zurück, {username}!"
        output["user_id"] = user_id
        output["user_email"] = user_email
        output["username"] = username
        #except Exception as e:
            #print(f"Fehler beim Login: {e}")
            #output["message"] = "Ein interner Fehler ist aufgetreten."
        return output

    @staticmethod
    def delete_account(conn: sqlite3.Connection, user_id: int) -> bool:
        """
        Löscht einen Benutzer und alle zugehörigen Daten aus der Datenbank.
        Dies setzt voraus, dass Foreign Keys mit 'ON DELETE CASCADE' eingerichtet sind.
        """
        try:
            cursor = conn.cursor()
            # Das Löschen des Users in 'all_users' löst die Kaskade aus.
            cursor.execute("DELETE FROM all_users WHERE user_id = ?", (user_id,))
            # Überprüfen, ob die Löschung erfolgreich war
            if cursor.rowcount > 0:
                return True
            else:
                return False
        except sqlite3.Error as e:
            return False

    @staticmethod
    def request_password_reset(conn: sqlite3.Connection, email: str) -> dict:
        output = UTILITIES.get_base_protocol()
        cursor = conn.cursor()

        email = _strip_submails(email)

        cursor.execute("SELECT user_id, username FROM all_users WHERE email = ?", (email.lower(),))
        user_row = cursor.fetchone()

        if user_row is None:
            output["message"] = "Wenn ein Account existiert, wurde eine E-Mail gesendet."
            return output

        user_id, username = user_row
        reset_token = TokenEndpoint.generate_password_token(conn, user_id)

        # E-Mail senden
        from backend.send_emails import send_password_reset_email
        send_password_reset_email(email, username, reset_token)

        output["message"] = "Wenn ein Account existiert, wurde eine E-Mail gesendet."
        return output

    @staticmethod
    def reset_password_with_token(conn: sqlite3.Connection, token: str, new_password: str) -> dict:
        output = UTILITIES.get_base_protocol()
        token_verification = TokenEndpoint.verify_and_consume_password_token(conn, token)

        if not token_verification.get("success"):
            output["message"] = token_verification.get("message")
            return output

        user_id = token_verification.get("user_id")
        try:
            new_hashed_password, new_salt = UTILITIES.hash_password(new_password)
            cursor = conn.cursor()
            update_sql = "UPDATE all_users SET password_hash = ?, salt = ? WHERE user_id = ?"
            cursor.execute(update_sql, (new_hashed_password, new_salt, user_id))

            output["success"] = True
            output["message"] = "Dein Passwort wurde erfolgreich geändert."
            output["user_id"] = user_id
        except sqlite3.Error as e:
            output["message"] = f"Datenbankfehler: {e}"

        return output

    @staticmethod
    def verify_email_delete_token(conn: sqlite3.Connection, token: str) -> dict:
        """Verifiziert einen E-Mail-Token und aktiviert den Account."""
        output = UTILITIES.get_base_protocol()
        user_id = TokenEndpoint.verify_email_delete_token(conn, token)

        if user_id is None:
            output["message"] = "Der Verifizierungs-Code ist ungültig oder abgelaufen."
            return output

        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE all_users SET is_verified = 1 WHERE user_id = ?", (user_id,))
            if cursor.rowcount > 0:
                output["success"] = True
                output["message"] = "Deine E-Mail-Adresse wurde erfolgreich verifiziert."
                output["user_id"] = user_id
            else:
                # Sollte nicht passieren, wenn Token valide war
                output["message"] = "Fehler: zugehöriger Benutzer oder Token konnte nicht gefunden werden."
        except sqlite3.Error as e:
            output["message"] = f"Datenbankfehler bei der Verifizierung. Grrr :( -> {e}"

        return output

    #unused
    @staticmethod
    def get_all_users_data(conn: sqlite3.Connection) -> list[dict]:
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
    def get_all_user_ids(conn: sqlite3.Connection) -> list:
        """ohne sensible Daten wie Passwort-Hashes"""
        # conn.row_factory ermöglicht direkten Zugriff auf Spalten per Namen
        # danke an w3 schools
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM all_users")

        # Erstellt eine Liste von Dictionaries, was viel lesbarer ist
        # eventuell pretty print: pprint()
        users = [dict(row)["user_id"] for row in cursor.fetchall()]
        #nice

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
    def can_change_username(conn: sqlite3.Connection, user_id: int) -> bool:
        """Prüft, ob der Benutzername geändert werden darf (mehr als 7 Tage seit letzter Änderung)."""
        settings = Settings.get_settings(conn, user_id)
        if not settings or not settings['last_name_change']:
            return True  # Noch nie geändert, also erlaubt

        last_change_time = datetime.fromisoformat(settings['last_name_change'])
        return (datetime.now() - last_change_time) > timedelta(days=7)

    @staticmethod
    def update_username(conn: sqlite3.Connection, user_id: int, new_username: str) -> dict:
        """Aktualisiert den Benutzernamen in allen relevanten Tabellen."""
        if UTILITIES.is_username_in_db(conn, new_username):
            return {"success": False, "message": "Benutzername ist bereits vergeben."}

        # In all_users, leaderboard, etc. aktualisieren
        conn.execute("UPDATE all_users SET username = ? WHERE user_id = ?", (new_username, user_id))

        # Zeitstempel der Änderung aktualisieren
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute("UPDATE settings SET last_name_change = ? WHERE user_id_fk = ?", (now_str, user_id))

        return {"success": True, "message": "Benutzername erfolgreich geändert."}

    @staticmethod
    def update_last_login_date(conn: sqlite3.Connection, user_id: int):
        cursor = conn.cursor()
        login_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("UPDATE all_users SET last_login = ? WHERE user_id = ?", (login_time, user_id))


class Settings:
    """Verwaltet die Einstellungen eines Benutzers."""

    @staticmethod
    def initialize_settings_for_user(conn: sqlite3.Connection, user_id: int):
        """Erstellt einen Standard-Eintrag in der Settings-Tabelle für einen neuen Benutzer."""
        sql = "INSERT INTO settings (user_id_fk, dark_mode) VALUES (?, ?)"
        cursor = conn.cursor()
        cursor.execute(sql, (user_id, 0))
        #print(f"Standard-Einstellungen für User-ID {user_id} erstellt.")

    @staticmethod
    def get_settings(conn: sqlite3.Connection, user_id: int) -> dict | None:
        """Ruft die Einstellungen für einen Benutzer ab."""
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM settings WHERE user_id_fk = ?", (user_id,))
        settings_data = cursor.fetchone()
        conn.row_factory = None
        return dict(settings_data) if settings_data else None

    @staticmethod
    def update_instagram_link(conn: sqlite3.Connection, user_id: int, ig_link: str | None):
        """Aktualisiert oder löscht den Instagram-Link eines Benutzers."""
        if not UTILITIES.is_ig_link_valid(ig_link):
            return
        sql = "UPDATE settings SET ig_link = ? WHERE user_id_fk = ?"
        conn.execute(sql, (ig_link, user_id))

    @staticmethod
    def update_dark_mode(conn: sqlite3.Connection, user_id: int, dark_mode_status: bool):
        """Schaltet den Dark Mode für einen Benutzer um."""
        sql = "UPDATE settings SET dark_mode = ? WHERE user_id_fk = ?"
        conn.execute(sql, (1 if dark_mode_status else 0, user_id))

    @staticmethod
    def get_link(conn: sqlite3.Connection, user_id:int) -> int | None:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT ig_link FROM settings WHERE user_id_fk = ?", (user_id,))
        return cursor.fetchone()

    @staticmethod
    def get_many_links(conn: sqlite3.Connection,user_ids: set[int]) -> dict[str: int] | None:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        placeholders = ', '.join(['?'] * len(user_ids))
        sql_query = f"SELECT user_id_fk, ig_link FROM settings WHERE user_id_fk IN ({placeholders})"
        cursor.execute(sql_query, list(user_ids))
        return {user_id: ig_link for user_id, ig_link in cursor.fetchall()}

if __name__ == "__main__":
    print(
    UTILITIES.is_ig_link_valid("https://www.instagram.com/gabriel_112811/profilecard/?igsh=MTcxbmFlcXV5NzVkeQ==")
)

