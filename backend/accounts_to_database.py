import sqlite3
from datetime import datetime, timedelta
from utilities import Utilities
from user_settings import Settings

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


def _update_last_login_date(conn: sqlite3.Connection, user_id:int):
    cursor = conn.cursor()
    login_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("UPDATE all_users SET last_login = ? WHERE user_id = ?", (login_time, user_id))


class AccountEndpoint:
    """
    Diese Klasse enthält alle Funktionen, die von einem Frontend oder Hauptskript aufgerufen werden können.
    Alle Funktionen akzeptieren ein 'conn'-Objekt und geben unser Protokoll-Dictionary zurück.
    """
    @staticmethod
    def create_account(conn: sqlite3.Connection, password: str, email: str, username: str,
                       instant_register_token: str = None) -> dict:
        output = Utilities.get_base_protocol()
        output['email_verification_required'] = False

        error_messages = []

        email = _strip_submails(email)
        #username = username.lower()

        if not Utilities.is_username_valid(conn, username).get("success"):
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
            error_messages.append("Diese E-Mail-Adresse ist schon vergeben.")

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
            hashed_password, salt = Utilities.hash_password(password)
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
            user_id = Utilities.get_user_id(conn, username)

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
        output = Utilities.get_base_protocol()
        try:
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

            if not Utilities.verify_password(stored_hash, stored_salt, password):
                output["message"] = "Falsches Passwort."
                return output

            # NEUER CHECK: Ist der Account verifiziert?
            if not is_verified:
                output["message"] = "Dein Account ist noch nicht verifiziert. Bitte prüfe deine E-Mails."
                # Optional: Neuen Token senden
                # verification_token = TokenEndpoint.generate_email_token(conn, user_id)
                # send_confirmation_email(user_email, username, verification_token)
                return output

            AccountEndpoint.update_last_login_date(conn, user_id)

            output["success"] = True
            output["message"] = f"Willkommen zurück, {username}!"
            output["user_id"] = user_id
            output["user_email"] = user_email
            output["username"] = username
        except Exception as e:
            print(f"Fehler beim Login: {e}")
            output["message"] = "Ein interner Fehler ist aufgetreten."
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
        output = Utilities.get_base_protocol()
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
        output = Utilities.get_base_protocol()
        token_verification = TokenEndpoint.verify_and_consume_password_token(conn, token)

        if not token_verification.get("success"):
            output["message"] = token_verification.get("message")
            return output

        user_id = token_verification.get("user_id")
        try:
            new_hashed_password, new_salt = Utilities.hash_password(new_password)
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
        output = Utilities.get_base_protocol()
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
            user_id = Utilities.get_user_id(conn, username)

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

        current_balance = AccountEndpoint.get_balance(conn, username=username)
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
    def can_change_username(conn: sqlite3.Connection, user_id: int) -> dict:
        """Prüft, ob der Benutzername geändert werden darf und gibt zurück, wann die nächste Änderung möglich ist."""
        settings = Settings.get_settings(conn, user_id)
        if not settings or not settings['last_name_change']:
            return {"can_change": True, "next_change_date": None}  # Noch nie geändert

        last_change_time = datetime.fromisoformat(settings['last_name_change'])
        seven_days_later = last_change_time + timedelta(days=7)

        if datetime.now() > seven_days_later:
            return {"can_change": True, "next_change_date": None}
        else:
            return {"can_change": False, "next_change_date": seven_days_later.strftime('%d.%m.%Y, %H:%M Uhr')}

    @staticmethod
    def update_username(conn: sqlite3.Connection, user_id: int, new_username: str) -> dict:
        """Aktualisiert den Benutzernamen in allen relevanten Tabellen."""
        if Utilities.is_username_in_db(conn, new_username):
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

    @staticmethod
    def delete_unverified_users(conn: sqlite3.Connection) -> dict:
        """Löscht alle Benutzer, die ihren Account nicht innerhalb von 24 Stunden verifiziert haben."""
        output = Utilities.get_base_protocol()
        try:
            # Berechne den Zeitpunkt vor 24 Stunden
            twenty_four_hours_ago = datetime.now() - timedelta(hours=24)
            twenty_four_hours_ago_str = twenty_four_hours_ago.strftime('%Y-%m-%d %H:%M:%S')

            cursor = conn.cursor()
            # Zähle zuerst, wie viele Benutzer gelöscht werden
            count_sql = """
                SELECT COUNT(*) FROM all_users 
                WHERE is_verified = 0 AND joined_date <= ?
            """
            cursor.execute(count_sql, (twenty_four_hours_ago_str,))
            num_deleted = cursor.fetchone()[0]

            if num_deleted > 0:
                # Führe die Löschung durch
                delete_sql = """
                    DELETE FROM all_users 
                    WHERE is_verified = 0 AND joined_date <= ?
                """
                cursor.execute(delete_sql, (twenty_four_hours_ago_str,))
                output["message"] = f"{num_deleted} nicht verifizierte Benutzer wurden gelöscht."
            else:
                output["message"] = "Keine abgelaufenen, nicht verifizierten Benutzer gefunden."

            output["success"] = True
            output["deleted_count"] = num_deleted

        except sqlite3.Error as e:
            output["message"] = f"Datenbankfehler: {e}"
        
        return output