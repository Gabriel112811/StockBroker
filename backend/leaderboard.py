# leaderboard.py
"""
Dieses Modul verwaltet das Leaderboard.
Es kann das Gesamtvermögen (net worth) aller Benutzer berechnen,
indem es den Barbestand mit dem Wert des Aktien-Depots kombiniert.
Aktienwerte werden über die yfinance-Bibliothek abgefragt.
"""

import sqlite3
import collections
from datetime import datetime
from yfinance.exceptions import YFPricesMissingError

from backend.accounts_to_database import AccountEndpoint
from backend.user_settings import Settings
from backend.utilities import Utilities
from backend.depot_system import DepotEndpoint

link_color = "#e017c0" #Instagram-Farbe

class LeaderboardEndpoint:
    """
    Diese Klasse bündelt alle Funktionen, die mit dem Leaderboard interagieren.
    """

    #unused
    @staticmethod
    def get_leaderboard(conn: sqlite3.Connection) -> list[dict]:
        """
        Gibt das komplette Leaderboard als Liste von Dictionaries aus,
        sortiert nach dem Gesamtvermögen (net_worth).
        """

        user_ids = AccountEndpoint.get_all_user_ids(conn)

        if not user_ids: # keine User = kein Ergebnis
            return []

        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        placeholders = ','.join(['?'] * len(user_ids))
        sql_query = f"""
                SELECT
                    user_id_fk,
                    net_worth,
                    last_updated
                FROM (
                    SELECT
                        user_id_fk,
                        net_worth,
                        last_updated,
                        -- Weist jeder Zeile eine Nummer zu, partitioniert nach User,
                        -- sortiert nach dem neuesten Datum zuerst.
                        ROW_NUMBER() OVER(PARTITION BY user_id_fk ORDER BY last_updated DESC) as rn
                    FROM
                        leaderboard
                    WHERE
                        user_id_fk IN ({placeholders})
                )
                -- Wähle nur die Zeilen aus, die der jeweils neueste Eintrag sind (rn = 1)
                WHERE rn = 1;
            """

        cursor.execute(sql_query, user_ids)

        leaderboard_data = [dict(row) for row in cursor.fetchall()] # unsere standart list_dict comprehension

        conn.row_factory = None

        #später effizientere methode finden || habe ich jetzt gemacht suiii

        return leaderboard_data

    @staticmethod
    def get_paginated_leaderboard(conn: sqlite3.Connection, page: int = 1, page_size: int = 10) -> set[dict]:
        """
        Gibt eine "Seite" des Leaderboards zurück, z.B. die Top 10, oder Platz 11-20.
        Ideal für eine Seitenansicht im Frontend.
        """
        if page < 1:
            page = 1
        offset = (page - 1) * page_size

        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        #sql = "SELECT user_id_fk, net_worth, last_updated FROM leaderboard ORDER BY net_worth DESC LIMIT ? OFFSET ?"
        sql = (
            "WITH RankedEntries AS ("
                   "SELECT user_id_fk, net_worth, last_updated, ROW_NUMBER() "
                        "OVER("
                            "PARTITION BY user_id_fk "
                            "ORDER BY last_updated DESC"
                        ") "
                        "as rn FROM leaderboard"
                ") "
               "SELECT user_id_fk, net_worth, last_updated "
               "FROM RankedEntries "
               "WHERE rn = 1 "
               "ORDER BY net_worth DESC "
               "LIMIT ? OFFSET ?;"
               )
        cursor.execute(sql, (page_size, offset))

        paginated_data = [dict(row) for row in cursor.fetchall()]
        user_ids = {i["user_id_fk"] for i in paginated_data}
        #warum nicht auch mal ein set benutzen, da man es sonst ja nie macht,
        #wenn man eh keine duplikate will
        if user_ids:
            username_map:dict[int, str] = Utilities.get_many_usernames(conn, user_ids)
            link_map:dict[int, str] = Settings.get_many_links(conn, user_ids)
        else:
            username_map = {}
            link_map = {}

        for i in paginated_data:
            i["username"] = username_map.get(i["user_id_fk"])
            i["link"] = link_map.get(i["user_id_fk"])
            i["color"] = link_color #ein pink
        conn.row_factory = None
        return paginated_data

    @staticmethod
    def insert_current_net_worth_for_user(conn: sqlite3.Connection, user_id: int) -> bool :
        """
        Berechnet und aktualisiert das Gesamtvermögen für EINEN einzelnen Benutzer.
        Gibt das Ergebnis als Dictionary zurück.
        """
        cursor = conn.cursor()

        # 1. Versuche drei mal, die daten zu holen.
        tries = 3
        for i in range(tries):
            try:
                depot_data = DepotEndpoint.get_depot_details(conn, user_id)
            except YFPricesMissingError as e:
                print(f"Versuch {i + 1}/{tries} fehlgeschlagen: {e}")
                continue
            except Exception as e:
                print(f"Versuch {i + 1}/{tries} fehlgeschlagen: {e}")
                continue
            if depot_data is None:
                continue
            if depot_data.get("prices_missing"):
                continue

            break
        else:
            return False

        net_worth = depot_data['total_net_worth']

        # 4. Aktualisiere oder füge den Eintrag im Leaderboard hinzu (Upsert)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sql_upsert = """
            INSERT INTO leaderboard (user_id_fk, net_worth, last_updated)
            VALUES (?, ?, ?)
        """
        cursor.execute(sql_upsert, (user_id, net_worth, now))

        return True

    @staticmethod
    def insert_all_current_net_worths(conn: sqlite3.Connection) -> dict:
        """
        Berechnet das Gesamtvermögen für ALLE Benutzer und aktualisiert das Leaderboard.
        Dies ist eine aufwendige Operation.
        """
        print("Starte die Berechnung des Gesamtvermögens für alle Benutzer. Dies kann einen Moment dauern...")
        all_users = AccountEndpoint.get_all_user_ids(conn)
        for user_id in all_users:
            LeaderboardEndpoint.insert_current_net_worth_for_user(conn, user_id)
        return {"success": True}

    @staticmethod
    def delete_row(conn: sqlite3.Connection, row_id: int):
        sql = "DELETE FROM leaderboard WHERE id = ?"
        cursor = conn.cursor()
        cursor.execute(sql, (row_id,))

    @staticmethod
    def delete_multiple_rows(conn: sqlite3.Connection, row_ids: list[int]):
        if not row_ids:
            print("Keine IDs zum Löschen übergeben.")
            return

        placeholders = ', '.join(['?'] * len(row_ids))

        sql = f"DELETE FROM leaderboard WHERE id IN ({placeholders})"

        cursor = conn.cursor()
        try:
            cursor.execute(sql, row_ids)
            print(f"{cursor.rowcount} Zeile(n) erfolgreich gelöscht.")

        except sqlite3.Error as e:
            print(f"Ein Datenbankfehler ist aufgetreten: {e}")

    @staticmethod
    def fetch_and_group_leaderboard(conn: sqlite3.Connection) -> dict:
        """
        Holt alle Einträge aus der 'leaderboard'-Tabelle, sortiert sie und
        formatiert sie in ein verschachteltes Dictionary.

        :param conn: SQLite3 Connection. Verbindung zur DB
        :return: dict
        """
        sql_query = """
            SELECT id, user_id_fk, last_updated, net_worth
            FROM leaderboard
            ORDER BY user_id_fk, last_updated DESC;
        """

        grouped_data = collections.defaultdict(list)

        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute(sql_query)

        for row in cursor.fetchall():
            user_id = row['user_id_fk']

            # Erstellt das innere Dictionary für die Liste.
            data_entry = {
                "date": row['last_updated'],
                "net_worth": row['net_worth'],
                "row_id": row['id'],
                "datetime": datetime.strptime(row['last_updated'], '%Y-%m-%d %H:%M:%S'),
            }

            grouped_data[user_id].append(data_entry)

        return dict(grouped_data)

    @staticmethod
    def decimate_entries(conn:sqlite3.Connection, target:int=1000, use_time_delta=True):
        use_time_delta = True #INOP
        if target < 10:
            return
        all_data = LeaderboardEndpoint.fetch_and_group_leaderboard(conn)

        to_delete_rows = []

        for user_id, data in all_data.items():
            user_to_delete_rows = []

            # gleiche Werte Löschen
            if len(data) >= 2:
                for i in range(len(data) - 3, -1, -1):
                    # in der Mitte löschen. Es wird bei 3 gleichen Werten der Wert in der mitte gelöscht
                    if data[i]['net_worth'] == data[i + 1]['net_worth'] == data[i + 2]['net_worth']:
                        user_to_delete_rows.append(data[i + 1]['row_id'])
                        data.pop(i + 1)

            if use_time_delta:

                delta = [data[i]["datetime"] - data[i - 1]["datetime"] for i in range(1, len(data))]

                while len(data) > target:
                    minimum_delta = min(delta)
                    index_min_delta = delta.index(minimum_delta)
                    if index_min_delta == 0:
                        index_min_delta = 1

                    user_to_delete_rows.append(
                        data.pop(index_min_delta)["row_id"]
                    )
                    delta[index_min_delta - 1] = delta[index_min_delta - 1] + delta.pop(index_min_delta)


                #print(f"{user_id}: {len(user_to_delete_rows)} wurden gelöscht.")
                to_delete_rows += user_to_delete_rows
            #
            #
            # INOP
            #
            #
            if not use_time_delta:
                if len(data) >= 3:  # gleiche Werte Löschen
                    relative_derivative_difference = []
                    for i in range(len(data) - 1):
                        delta_0_to_1 = (data[i + 1]["net_worth"] - data[i]["net_worth"]) / (data[i + 1]["datetime"] - data[i]["datetime"]).total_seconds()
                        delta_0_to_2 = (data[i + 2]["net_worth"] - data[i]["net_worth"]) / (data[i + 2]["datetime"] - data[i]["datetime"]).total_seconds()

                    while len(data) > target:
                        minimum_delta = min(delta)
                        index_min_delta = delta.index(minimum_delta)
                        if index_min_delta == 0:
                            index_min_delta = 1

                        user_to_delete_rows.append(
                            data.pop(index_min_delta)["row_id"]
                        )
                        delta[index_min_delta - 1] = delta[index_min_delta - 1] + delta.pop(index_min_delta)


        LeaderboardEndpoint.delete_multiple_rows(conn, to_delete_rows)

    @staticmethod
    def get_all_user_ids(conn) -> list[int]:

        sql_query = "SELECT DISTINCT user_id_fk FROM leaderboard;"

        cursor = conn.cursor()
        cursor.execute(sql_query)

        user_ids = [row[0] for row in cursor.fetchall()]

        return user_ids

    @staticmethod
    def count_users(conn) -> int:
        # wie LeaderboardEndpont.get_all_user_ids() nur mit count
        sql_query = "SELECT COUNT(DISTINCT user_id_fk) FROM leaderboard;"

        cursor = conn.cursor()
        cursor.execute(sql_query)

        count = cursor.fetchone()[0]

        return count
























