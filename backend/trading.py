# backend/trading.py
import sqlite3
import yfinance as yf
from datetime import datetime
import pandas as pd
from dataclasses import dataclass
from typing import Optional

# Lokale Imports
from backend.accounts_to_database import AccountEndpoint as AccountEndpoint
from backend.accounts_to_database import Utilities


# ==============================================================================
# === NEUE DATENKLASSE FÜR STRUKTURIERTE AUFTRÄGE ===
# ==============================================================================
@dataclass
class Order:
    order_id: int
    user_id_fk: int
    ticker: str
    order_type: str
    quantity: float
    status: str
    created_at: str
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    executed_at: Optional[str] = None
    executed_price: Optional[float] = None


class TradingEndpoint:
    # Die Methoden _get_current_price und _update_depot bleiben unverändert
    @staticmethod
    def _get_current_price(ticker: str) -> float | None:
        # ... (keine Änderungen)
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            price = info.get('currentPrice', info.get('regularMarketPrice'))
            if price: return float(price)
            hist = stock.history(period="1d")
            if not hist.empty: return float(hist['Close'].iloc[-1])
            return None
        except Exception:
            return None

    @staticmethod
    def _update_depot(conn: sqlite3.Connection, user_id: int, ticker: str, quantity: float, purchase_price: float,
                      is_buy: bool):
        # ... (keine Änderungen)
        cursor = conn.cursor()
        cursor.execute("SELECT quantity, average_purchase_price FROM stock_depot WHERE user_id_fk = ? AND ticker = ?",
                       (user_id, ticker))
        position = cursor.fetchone()
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if is_buy:
            if position:
                old_quantity, old_avg_price = position
                new_quantity = old_quantity + quantity
                new_avg_price = ((old_avg_price * old_quantity) + (purchase_price * quantity)) / new_quantity
                cursor.execute(
                    "UPDATE stock_depot SET quantity = ?, average_purchase_price = ?, last_updated = ? WHERE user_id_fk = ? AND ticker = ?",
                    (new_quantity, new_avg_price, now_str, user_id, ticker))
            else:
                cursor.execute(
                    "INSERT INTO stock_depot (user_id_fk, ticker, quantity, average_purchase_price, last_updated) VALUES (?, ?, ?, ?, ?)",
                    (user_id, ticker, quantity, purchase_price, now_str))
        else:
            if not position or position[0] < quantity:
                raise ValueError("Nicht genügend Aktien zum Verkaufen vorhanden.")
            new_quantity = position[0] - quantity
            if new_quantity > 0:
                cursor.execute(
                    "UPDATE stock_depot SET quantity = ?, last_updated = ? WHERE user_id_fk = ? AND ticker = ?",
                    (new_quantity, now_str, user_id, ticker))
            else:
                cursor.execute("DELETE FROM stock_depot WHERE user_id_fk = ? AND ticker = ?", (user_id, ticker))

    @staticmethod
    def _execute_market_trade(conn: sqlite3.Connection, user_id: int, ticker: str, quantity: int, is_buy: bool) -> dict:
        """
        Führt einen Market-Trade aus, aktualisiert Kontostand sowie Depot
        und protokolliert den Trade in der 'orders'-Tabelle.
        """
        price = TradingEndpoint._get_current_price(ticker)
        if not price:
            return {"success": False, "message": f"Konnte aktuellen Preis für {ticker} nicht abrufen."}

        total_cost = price * quantity
        username = Utilities.get_username(conn, user_id)
        order_type = 'MARKET_BUY' if is_buy else 'MARKET_SELL'
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Transaktionslogik
        if is_buy:
            current_balance = AccountEndpoint.get_balance(conn, user_id=user_id)
            if current_balance is None or current_balance < total_cost:
                return {"success": False, "message": "Nicht genügend Guthaben für diesen Kauf."}
            AccountEndpoint.update_balance(conn, username, -total_cost)
            TradingEndpoint._update_depot(conn, user_id, ticker, quantity, price, is_buy=True)
            message = f"{quantity} {ticker} für {price:.2f} € pro Aktie gekauft."
        else:  # is_sell
            try:
                TradingEndpoint._update_depot(conn, user_id, ticker, quantity, price, is_buy=False)
                AccountEndpoint.update_balance(conn, username, total_cost)
                message = f"{quantity} {ticker} für {price:.2f} € pro Aktie verkauft."
            except ValueError as e:
                return {"success": False, "message": str(e)}

        # NEU: Protokollierung des ausgeführten Trades in der 'orders'-Tabelle
        try:
            sql_log_order = """
                    INSERT INTO orders 
                    (user_id_fk, ticker, order_type, quantity, status, created_at, executed_at, executed_price)
                    VALUES (?, ?, ?, ?, 'EXECUTED', ?, ?, ?)
                """
            params = (user_id, ticker, order_type, quantity, now_str, now_str, price)
            cursor = conn.cursor()
            cursor.execute(sql_log_order, params)
            print(f"Market-Trade für User {user_id} ({ticker}) erfolgreich in 'orders' protokolliert.")
        except sqlite3.Error as e:
            # Wenn die Protokollierung fehlschlägt, ist der Trade trotzdem durch.
            # Wir geben eine Warnung aus, machen aber keinen Rollback der Finanztransaktion.
            print(f"WARNUNG: Finanztransaktion erfolgreich, aber Protokollierung in 'orders' fehlgeschlagen: {e}")

        return {"success": True, "message": message}

    @staticmethod
    def place_order(conn: sqlite3.Connection, user_id: int, order_details: dict) -> dict:
        # ... (keine Änderungen)
        order_type = order_details.get('order_type')
        ticker = order_details.get('ticker')
        quantity = order_details.get('quantity')
        if order_type == 'MARKET_BUY':
            return TradingEndpoint._execute_market_trade(conn, user_id, ticker, quantity, is_buy=True)
        if order_type == 'MARKET_SELL':
            return TradingEndpoint._execute_market_trade(conn, user_id, ticker, quantity, is_buy=False)
        limit_price = order_details.get('limit_price')
        stop_price = order_details.get('stop_price')
        if (order_type in ['LIMIT_BUY', 'LIMIT_SELL'] and not limit_price) or \
                (order_type == 'STOP_LOSS_SELL' and not stop_price):
            return {"success": False, "message": "Limit- oder Stop-Preis für diesen Auftragstyp erforderlich."}
        sql = "INSERT INTO orders (user_id_fk, ticker, order_type, quantity, limit_price, stop_price, created_at, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN')"
        params = (
        user_id, ticker, order_type, quantity, limit_price, stop_price, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return {"success": True, "message": "Auftrag erfolgreich platziert."}
        except sqlite3.Error as e:
            return {"success": False, "message": f"Datenbankfehler: {e}"}

    @staticmethod
    def get_user_orders(conn: sqlite3.Connection, user_id: int, status_filter: Optional[str] = None) -> list[dict]:
        """
        Holt die Aufträge eines Benutzers.
        :param conn: Datenbankverbindung
        :param user_id: ID des Benutzers
        :param status_filter: Optionaler Filter: 'OPEN' oder 'CLOSED'
        :return: Liste von Aufträgen als Dictionaries
        """
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        sql = "SELECT * FROM orders WHERE user_id_fk = ?"
        params = [user_id]

        if status_filter == 'OPEN':
            sql += " AND status = 'OPEN'"
        elif status_filter == 'CLOSED':
            sql += " AND status != 'OPEN'"

        sql += " ORDER BY created_at DESC"

        cursor.execute(sql, params)
        orders = [dict(row) for row in cursor.fetchall()]
        conn.row_factory = None
        return orders

    @staticmethod
    def cancel_order(conn: sqlite3.Connection, user_id: int, order_id: int) -> dict:
        # ... (keine Änderungen)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM orders WHERE order_id = ? AND user_id_fk = ?", (order_id, user_id))
        result = cursor.fetchone()
        if not result:
            return {"success": False, "message": "Auftrag nicht gefunden oder keine Berechtigung."}
        if result[0] != 'OPEN':
            return {"success": False, "message": "Nur offene Aufträge können storniert werden."}
        cursor.execute("UPDATE orders SET status = 'CANCELED' WHERE order_id = ?", (order_id,))
        return {"success": True, "message": "Auftrag storniert."}

    @staticmethod
    def get_locked_cash(conn: sqlite3.Connection, user_id: int) -> float:
        """Berechnet das Kapital, das in offenen LIMIT_BUY-Aufträgen gebunden ist."""
        cursor = conn.cursor()
        sql = """
                SELECT SUM(quantity * limit_price) 
                FROM orders 
                WHERE user_id_fk = ? AND order_type = 'LIMIT_BUY' AND status = 'OPEN'
            """
        cursor.execute(sql, (user_id,))
        result = cursor.fetchone()
        return result[0] if result and result[0] is not None else 0.0

    @staticmethod
    def get_user_position(conn: sqlite3.Connection, user_id: int, ticker: str) -> Optional[dict]:
        """Holt die Depot-Position eines Benutzers für einen bestimmten Ticker."""
        cursor = conn.cursor()
        sql = "SELECT quantity, average_purchase_price FROM stock_depot WHERE user_id_fk = ? AND ticker = ?"
        cursor.execute(sql, (user_id, ticker))
        result = cursor.fetchone()
        if result:
            return {"quantity": result[0], "average_purchase_price": result[1]}
        return None


    @staticmethod
    def process_open_orders(conn: sqlite3.Connection):
        """
        Überprüft alle offenen Aufträge mithilfe der Order-Datenklasse.
        """
        print(f"[{datetime.now()}] Starte Verarbeitung offener Aufträge...")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE status = 'OPEN'")

        # Rohdaten aus der DB in strukturierte Order-Objekte umwandeln
        orders_raw = cursor.fetchall()
        if not orders_raw:
            print("Keine offenen Aufträge gefunden.")
            return
        open_orders: list[Order] = [Order(**dict(row)) for row in orders_raw]

        tickers = {order.ticker for order in open_orders}
        try:
            data = yf.download(list(tickers), period="1d", progress=False, group_by='ticker', auto_adjust=True)
            if data.empty:
                print("Konnte keine Preisdaten von yfinance abrufen.")
                return
        except Exception as e:
            print(f"Fehler beim Abrufen der Kurse von yfinance: {e}")
            return

        for order in open_orders:
            try:
                # Sicherer Zugriff auf Preisdaten
                if order.ticker in data and not pd.isna(data[order.ticker]['Close'].iloc[-1]):
                    current_price = data[order.ticker]['Close'].iloc[-1]
                else:
                    continue
            except (KeyError, IndexError):
                continue

            execute = False
            execution_price = 0.0

            # Typsicherer Zugriff auf Attribute des Order-Objekts
            if order.order_type == 'LIMIT_BUY' and current_price <= order.limit_price:
                execute = True
                execution_price = order.limit_price
            elif order.order_type == 'LIMIT_SELL' and current_price >= order.limit_price:
                execute = True
                execution_price = order.limit_price
            elif order.order_type == 'STOP_LOSS_SELL' and current_price <= order.stop_price:
                execute = True
                execution_price = order.stop_price

            if execute:
                try:
                    print(f"Führe Auftrag {order.order_id} aus...")
                    username = Utilities.get_username(conn, order.user_id_fk)
                    is_buy = 'BUY' in order.order_type
                    total_value = execution_price * order.quantity

                    if is_buy:
                        AccountEndpoint.update_balance(conn, username, -total_value)
                        TradingEndpoint._update_depot(conn, order.user_id_fk, order.ticker, order.quantity,
                                                      execution_price, is_buy=True)
                    else:  # SELL
                        TradingEndpoint._update_depot(conn, order.user_id_fk, order.ticker, order.quantity,
                                                      execution_price, is_buy=False)
                        AccountEndpoint.update_balance(conn, username, total_value)

                    update_sql = "UPDATE orders SET status = 'EXECUTED', executed_at = ?, executed_price = ? WHERE order_id = ?"
                    cursor.execute(update_sql,
                                   (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), execution_price, order.order_id))
                    print(f"Auftrag {order.order_id} erfolgreich ausgeführt.")

                except Exception as e:
                    print(f"Fehler bei der Ausführung von Auftrag {order.order_id}: {e}")
                    cursor.execute("UPDATE orders SET status = 'FAILED' WHERE order_id = ?", (order.order_id,))

        conn.commit()
        conn.row_factory = None