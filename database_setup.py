import sqlite3
"""
Setzt die Datenbank auf dem Raspberry Pi auf
"""


def create_all_users_table(conn):
    """Erstellt die Tabelle all_users."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS all_users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            money REAL NOT NULL DEFAULT 50000.0,
            joined_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            is_verified INTEGER NOT NULL DEFAULT 0,
            last_login TIMESTAMP
        );
    """)
    # Index für häufige Logins
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_username ON all_users (username);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_email ON all_users (email);")
    print("Tabelle 'all_users' erstellt oder bereits vorhanden.")

def create_settings_table(conn):
    """Erstellt die Tabelle settings."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            user_id_fk INTEGER PRIMARY KEY,
            ig_link TEXT,
            dark_mode INTEGER NOT NULL DEFAULT 0,
            last_name_change TIMESTAMP,
            FOREIGN KEY (user_id_fk) REFERENCES all_users (user_id) ON DELETE CASCADE
        );
    """)
    print("Tabelle 'settings' erstellt oder bereits vorhanden.")

def create_orders_table(conn):
    """Erstellt die Tabelle orders."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id_fk INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            order_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            limit_price REAL,
            stop_price REAL,
            status TEXT NOT NULL DEFAULT 'OPEN',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            executed_at TIMESTAMP,
            executed_price REAL,
            FOREIGN KEY (user_id_fk) REFERENCES all_users (user_id) ON DELETE CASCADE
        );
    """)
    # Indizes für schnellere Abfragen der Orders eines Users und nach Status
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders (user_id_fk);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status);")
    print("Tabelle 'orders' erstellt oder bereits vorhanden.")

def create_secure_tokens_table(conn):
    """Erstellt die Tabelle secure_tokens."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS secure_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id_fk INTEGER,
            token_hash TEXT NOT NULL UNIQUE,
            token_type TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id_fk) REFERENCES all_users (user_id) ON DELETE CASCADE
        );
    """)
    # Index für schnelle Token-Validierung
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_token_hash ON secure_tokens (token_hash);")
    print("Tabelle 'secure_tokens' erstellt oder bereits vorhanden.")

def create_stock_depot_table(conn):
    """Erstellt die Tabelle stock_depot."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_depot (
            depot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id_fk INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            average_purchase_price REAL NOT NULL,
            last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id_fk, ticker),
            FOREIGN KEY (user_id_fk) REFERENCES all_users (user_id) ON DELETE CASCADE
        );
    """)
    # Index für schnellen Zugriff auf das Depot eines Users
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_depot_user_id ON stock_depot (user_id_fk);")
    print("Tabelle 'stock_depot' erstellt oder bereits vorhanden.")

def create_leaderboard_table(conn):
    """Erstellt die Tabelle leaderboard."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leaderboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id_fk INTEGER NOT NULL,
            net_worth REAL NOT NULL,
            last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id_fk) REFERENCES all_users (user_id) ON DELETE CASCADE
        );
    """)
    # Index für schnellen Zugriff auf den Rang eines Users
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_leaderboard_user_id ON leaderboard (user_id_fk);")
    print("Tabelle 'leaderboard' erstellt oder bereits vorhanden.")

def create_cached_charts_table(conn):
    """Erstellt die Tabelle cached_charts."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cached_charts (
            ticker TEXT NOT NULL,
            dark_mode INTEGER NOT NULL,
            chart_html TEXT NOT NULL,
            company_name TEXT,
            last_updated TIMESTAMP NOT NULL,
            PRIMARY KEY (ticker, dark_mode)
        );
    """)
    print("Tabelle 'cached_charts' erstellt oder bereits vorhanden.")

def setup_database(db_path='backend/StockBroker.db'):
    """Führt alle Funktionen zur Erstellung der Tabellen aus."""
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        print(f"Datenbankverbindung zu '{db_path}' hergestellt.")
        
        create_all_users_table(conn)
        create_settings_table(conn)
        create_orders_table(conn)
        create_secure_tokens_table(conn)
        create_stock_depot_table(conn)
        create_leaderboard_table(conn)
        create_cached_charts_table(conn)
        
        conn.commit()
        print("Datenbank-Setup erfolgreich abgeschlossen.")
        
    except sqlite3.Error as e:
        print(f"Ein Fehler ist aufgetreten: {e}")
    finally:
        if conn:
            conn.close()
            print("Datenbankverbindung geschlossen.")

if __name__ == '__main__':
    setup_database()
