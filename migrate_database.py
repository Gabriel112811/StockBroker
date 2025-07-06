
import sqlite3
import os
import datetime
from database_setup import setup_database

# Definiere die Pfade
DB_FOLDER = 'backend'
DB_NAME = 'StockBroker.db'
DB_PATH = os.path.join(DB_FOLDER, DB_NAME)

def migrate_data():
    """Migriert Daten von einer alten DB zu einer neuen, die per Skript erstellt wird."""
    # 1. Backup der alten Datenbank
    if not os.path.exists(DB_PATH):
        print(f"Keine Datenbank unter '{DB_PATH}' gefunden. Es gibt nichts zu migrieren.")
        print("Erstelle eine neue Datenbank von Grund auf...")
        setup_database(DB_PATH)
        return

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d")
    old_db_name = f"StockBroker_old_{timestamp}.db"
    old_db_path = os.path.join(DB_FOLDER, old_db_name)

    # Falls am selben Tag schon ein Backup gemacht wurde, füge eine Nummer hinzu
    counter = 1
    while os.path.exists(old_db_path):
        old_db_name = f"StockBroker_old_{timestamp}_{counter}.db"
        old_db_path = os.path.join(DB_FOLDER, old_db_name)
        counter += 1

    print(f"1. Umbenennen der alten Datenbank zu '{old_db_path}'...")
    os.rename(DB_PATH, old_db_path)
    print("   Alte Datenbank erfolgreich umbenannt.")

    # 2. Neue Datenbank mit dem Setup-Skript erstellen
    print(f"2. Erstellen einer neuen, leeren Datenbank unter '{DB_PATH}'...")
    setup_database(DB_PATH)
    print("   Neue Datenbank erfolgreich erstellt.")

    # 3. Daten von der alten in die neue Datenbank kopieren
    print("3. Start der Datenmigration...")
    try:
        old_conn = sqlite3.connect(old_db_path)
        new_conn = sqlite3.connect(DB_PATH)
        old_cursor = old_conn.cursor()
        new_cursor = new_conn.cursor()

        # Liste der Tabellen, die migriert werden sollen (sqlite_sequence wird ignoriert)
        tables_to_migrate = [
            'all_users', 'settings', 'orders', 'secure_tokens',
            'stock_depot', 'leaderboard' # 'cached_charts' wird bewusst ausgelassen
        ]

        for table_name in tables_to_migrate:
            print(f"   - Migriere Tabelle: {table_name}")
            old_cursor.execute(f"SELECT * FROM {table_name}")
            all_data = old_cursor.fetchall()

            if not all_data:
                print(f"     -> Tabelle '{table_name}' ist leer, wird übersprungen.")
                continue

            # Spaltennamen aus der alten Tabelle holen, um die Reihenfolge zu respektieren
            old_cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [info[1] for info in old_cursor.fetchall()]
            
            # Erstelle den INSERT-Befehl
            placeholders = ', '.join(['?' for _ in columns])
            column_names = ', '.join(columns)
            insert_sql = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"

            try:
                new_cursor.executemany(insert_sql, all_data)
                print(f"     -> {len(all_data)} Zeilen erfolgreich in '{table_name}' eingefügt.")
            except sqlite3.Error as e:
                print(f"     -> FEHLER beim Einfügen in '{table_name}': {e}")
                print(f"        SQL-Befehl: {insert_sql}")
                # Bei einem Fehler wird die Transaktion für diese Tabelle zurückgerollt,
                # aber das Skript versucht, mit der nächsten Tabelle fortzufahren.
                new_conn.rollback()

        # Änderungen committen und Verbindungen schließen
        new_conn.commit()
        old_conn.close()
        new_conn.close()

        print("4. Datenmigration erfolgreich abgeschlossen!")

    except sqlite3.Error as e:
        print(f"Ein schwerwiegender Datenbankfehler ist aufgetreten: {e}")
        print("Die neue Datenbank wurde erstellt, aber die Migration ist fehlgeschlagen.")
        print(f"Die alte Datenbank ist sicher unter '{old_db_path}'.")

if __name__ == '__main__':
    migrate_data()
