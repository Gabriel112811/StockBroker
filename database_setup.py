# database_setup.py für den raspberry pi
import sqlite3

DATABASE_FILE = "backend/StockBroker.db"

def create_cache_table():
    """Erstellt die Tabelle zum Zwischenspeichern der Chart-HTML-Daten."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    # Erstellt die Tabelle, falls sie noch nicht existiert
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cached_charts (
            ticker TEXT PRIMARY KEY,
            chart_html TEXT NOT NULL,
            dark_mode INTEGER NOT NULL,
            last_updated TIMESTAMP NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    print("Tabelle 'cached_charts' wurde erfolgreich überprüft/erstellt.")

if __name__ == '__main__':
    create_cache_table()