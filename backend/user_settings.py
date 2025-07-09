import sqlite3
from backend.utilities import Utilities

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
        if not Utilities.is_ig_link_valid(ig_link):
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