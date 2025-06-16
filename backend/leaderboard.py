# leaderboard.py
"""
Dieses Modul verwaltet das Leaderboard.
Es kann das Gesamtvermögen (net worth) aller Benutzer berechnen,
indem es den Barbestand mit dem Wert des Aktien-Depots kombiniert.
Aktienwerte werden über die yfinance-Bibliothek abgefragt.
"""

import sqlite3
import yfinance as yf
import pandas as pd
from datetime import datetime
from collections import defaultdict


class LeaderboardEndpoint:
    """
    Diese Klasse bündelt alle Funktionen, die mit dem Leaderboard interagieren.
    """

    @staticmethod
    def get_leaderboard(conn: sqlite3.Connection) -> list[dict]:
        """
        Gibt das komplette Leaderboard als Liste von Dictionaries aus,
        sortiert nach dem Gesamtvermögen (net_worth).
        """
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT username, net_worth, last_updated FROM leaderboard ORDER BY net_worth DESC")
        leaderboard_data = [dict(row) for row in cursor.fetchall()]
        conn.row_factory = None  # Auf Standard zurücksetzen
        return leaderboard_data

    @staticmethod
    def get_paginated_leaderboard(conn: sqlite3.Connection, page: int = 1, page_size: int = 10) -> list[dict]:
        """
        Gibt eine "Seite" des Leaderboards zurück, z.B. die Top 10, oder Platz 11-20.
        Ideal für eine Seitenansicht im Frontend.
        """
        if page < 1:
            page = 1
        offset = (page - 1) * page_size

        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        sql = "SELECT username, net_worth, last_updated FROM leaderboard ORDER BY net_worth DESC LIMIT ? OFFSET ?"
        cursor.execute(sql, (page_size, offset))

        paginated_data = [dict(row) for row in cursor.fetchall()]
        conn.row_factory = None
        return paginated_data

    @staticmethod
    def update_net_worth_for_user(conn: sqlite3.Connection, username: str) -> dict:
        """
        Berechnet und aktualisiert das Gesamtvermögen für EINEN einzelnen Benutzer.
        Gibt das Ergebnis als Dictionary zurück.
        """
        cursor = conn.cursor()

        # 1. Hole Cash und User-ID des Benutzers
        cursor.execute("SELECT user_id, money FROM all_users WHERE username = ?", (username,))
        user_data = cursor.fetchone()
        if not user_data:
            return {"success": False, "message": "Benutzer nicht gefunden."}
        user_id, cash_balance = user_data

        # 2. Hole alle Positionen des Benutzers aus dem Depot
        cursor.execute("SELECT ticker, quantity FROM stock_depot WHERE user_id_fk = ?", (user_id,))
        positions = cursor.fetchall()

        portfolio_value = 0.0
        if positions:
            # Hole aktuelle Preise für alle Ticker im Portfolio
            tickers = [pos[0] for pos in positions]
            try:
                # Batch-Download für bessere Performance
                data = yf.download(tickers, period="1d", progress=False)
                if data.empty:
                    raise ValueError("Keine Preisdaten von yfinance erhalten.")

                # Extrahiere den letzten Schlusskurs für jeden Ticker
                latest_prices = data['Close'].iloc[-1]

                for ticker, quantity in positions:
                    price = latest_prices.get(ticker)
                    if price:
                        portfolio_value += quantity * price
            except Exception as e:
                return {"success": False, "message": f"Fehler beim Abrufen der Aktienkurse: {e}"}

        # 3. Berechne Gesamtvermögen
        net_worth = cash_balance + portfolio_value

        # 4. Aktualisiere oder füge den Eintrag im Leaderboard hinzu (Upsert)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sql_upsert = """
            INSERT INTO leaderboard (user_id_fk, username, net_worth, last_updated)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id_fk) DO UPDATE SET
            net_worth = excluded.net_worth,
            last_updated = excluded.last_updated;
        """
        cursor.execute(sql_upsert, (user_id, username, net_worth, now))

        return {
            "success": True,
            "username": username,
            "net_worth": round(net_worth, 2),
            "message": "Gesamtvermögen erfolgreich aktualisiert."
        }

    @staticmethod
    def update_all_net_worths(conn: sqlite3.Connection) -> dict:
        """
        Berechnet das Gesamtvermögen für ALLE Benutzer und aktualisiert das Leaderboard.
        Dies ist eine aufwendige Operation.
        """
        print("Starte die Berechnung des Gesamtvermögens für alle Benutzer. Dies kann einen Moment dauern...")

        # Schritt 1: Alle Benutzerdaten und Portfolios aus der DB holen
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, money FROM all_users") # lieber Utilities aufrufen
        all_users = cursor.fetchall()

        cursor.execute("SELECT user_id_fk, ticker, quantity FROM stock_depot")
        all_positions_raw = cursor.fetchall()

        # Portfolios pro User gruppieren für einfachen Zugriff
        portfolios = defaultdict(list)
        all_tickers = set()
        for user_id, ticker, quantity in all_positions_raw:
            portfolios[user_id].append({'ticker': ticker, 'quantity': quantity})
            all_tickers.add(ticker)

        # Schritt 2: Alle benötigten Aktienkurse in einem einzigen Aufruf abfragen
        print(f"Rufe aktuelle Kurse für {len(all_tickers)} einzigartige Ticker ab...")
        prices = {}
        if all_tickers:
            try:
                data = yf.download(list(all_tickers), period="1d", progress=False, group_by='ticker')
                if not data.empty:
                    for ticker in all_tickers:
                        # yfinance gibt manchmal Spalten mit Multi-Index zurück
                        try:
                            # Versuche den Preis direkt zu bekommen
                            price = data[ticker]['Close'].iloc[-1]
                            if not pd.isna(price):  # Prüfe auf NaN
                                prices[ticker] = price
                        except (KeyError, IndexError):
                            print(f"Warnung: Konnte keinen aktuellen Preis für {ticker} finden.")
                            continue
                else:
                    print("Warnung: yfinance hat keine Daten zurückgegeben.")
            except Exception as e:
                return {"success": False, "message": f"Fehler bei yfinance-Abfrage: {e}"}

        # Schritt 3: Net Worth für jeden User berechnen und in die DB schreiben
        print("Berechne Gesamtvermögen und aktualisiere das Leaderboard...")
        leaderboard_updates = []
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for user_id, username, cash_balance in all_users:
            portfolio_value = 0.0
            user_portfolio = portfolios.get(user_id, [])
            for position in user_portfolio:
                price = prices.get(position['ticker'], 0.0)  # Nutze 0.0 wenn Preis nicht verfügbar
                portfolio_value += position['quantity'] * price

            net_worth = cash_balance + portfolio_value
            leaderboard_updates.append((user_id, username, net_worth, now))

        # Schritt 4: Alle Updates in einer Transaktion in die DB schreiben (Upsert)
        sql_upsert = """
            INSERT INTO leaderboard (user_id_fk, username, net_worth, last_updated)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id_fk) DO UPDATE SET
            net_worth = excluded.net_worth,
            last_updated = excluded.last_updated;
        """
        cursor.executemany(sql_upsert, leaderboard_updates)

        print("Leaderboard wurde erfolgreich aktualisiert.")
        return {"success": True, "message": f"{len(all_users)} Benutzer im Leaderboard aktualisiert."}


# Dieser Block wird nur ausgeführt, wenn das Skript direkt gestartet wird
if __name__ == '__main__':
    import pandas as pd  # yfinance benötigt pandas, importieren wir es hier für den Fall der Fälle

    DB_FILE = "StockBroker.db"
    conn = None

    try:
        conn = sqlite3.connect(DB_FILE)

        # Gesamtes Leaderboard für alle User aktualisieren
        update_result = LeaderboardEndpoint.update_all_net_worths(conn)
        print(f"Update-Ergebnis: {update_result['message']}")

        if update_result['success']:
            # Wichtig: Änderungen committen!
            conn.commit()
            print("\n--- Vollständiges Leaderboard ---")
            full_lb = LeaderboardEndpoint.get_leaderboard(conn)
            for i, entry in enumerate(full_lb):
                print(f"{i + 1}. {entry['username']}: {entry['net_worth']:.2f}€")

            print("\n--- Leaderboard Seite 1 (Top 2) ---")
            page1 = LeaderboardEndpoint.get_paginated_leaderboard(conn, page=1, page_size=2)
            for entry in page1:
                print(f"- {entry['username']}: {entry['net_worth']:.2f}€")

            print("\n--- Leaderboard Seite 2 (Platz 3-4) ---")
            page2 = LeaderboardEndpoint.get_paginated_leaderboard(conn, page=2, page_size=2)
            for entry in page2:
                print(f"- {entry['username']}: {entry['net_worth']:.2f}€")
        else:
            conn.rollback()

    except sqlite3.Error as e:
        print(f"Ein Datenbankfehler ist aufgetreten: {e}")
    finally:
        if conn:
            conn.close()
            print("\nDatenbankverbindung wurde geschlossen.")