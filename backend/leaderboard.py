# leaderboard.py
"""
Dieses Modul verwaltet das Leaderboard.
Es kann das Gesamtvermögen (net worth) aller Benutzer berechnen,
indem es den Barbestand mit dem Wert des Aktien-Depots kombiniert.
Aktienwerte werden über die yfinance-Bibliothek abgefragt.
"""

import sqlite3
import collections
import yfinance as yf
import pandas as pd
from datetime import datetime
from collections import defaultdict

from backend.accounts_to_database import UTILITIES, ENDPOINT

from backend.depot_system import DepotEndpoint
from backend.sql_tests import cursor


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
        leaderboard_data = []
        for user_id in ENDPOINT.get_all_user_ids(conn):
            cursor.execute(f"SELECT user_id_fk, net_worth, last_updated FROM "
                           f"leaderboard WHERE user_id_fk='{user_id}' ORDER BY net_worth")
            leaderboard_data.append(dict(cursor.fetchone()))
        conn.row_factory = None  # Auf Standard zurücksetzen
        #später effizientere methode finden
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
        for i in paginated_data:
            i["username"] = UTILITIES.get_username(conn, i["user_id_fk"])
        conn.row_factory = None
        return paginated_data

    @staticmethod
    def insert_current_net_worth_for_user(conn: sqlite3.Connection, user_id: int) -> bool :
        """
        Berechnet und aktualisiert das Gesamtvermögen für EINEN einzelnen Benutzer.
        Gibt das Ergebnis als Dictionary zurück.
        """
        cursor = conn.cursor()

        # 1. Hole Cash und User-ID des Benutzers
        depot_data = DepotEndpoint.get_depot_details(conn, user_id)
        if depot_data is None:
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
        all_users = ENDPOINT.get_all_user_ids(conn)
        for user_id in all_users:
            LeaderboardEndpoint.insert_current_net_worth_for_user(conn, user_id)
        return {"success": True}

    @staticmethod
    def delete_row(conn: sqlite3.Connection, row_id: int) -> None:
        sql = "DELETE FROM leaderboard WHERE id = ?"
        cursor = conn.cursor()
        cursor.execute(sql, (row_id,))

    @staticmethod
    def fetch_and_group_leaderboard(conn: sqlite3.Connection) -> dict:
        """
        Holt alle Einträge aus der 'leaderboard'-Tabelle, sortiert sie und
        formatiert sie in ein verschachteltes Dictionary.

        :param db_path: Der Dateipfad zur SQLite-Datenbank.
        :return: Ein Dictionary, gruppiert nach user_id_fk.
                 Beispiel: {1: [{'last_updated': '...', 'net_worth': ...}, ...]}
        """
        sql_query = """
            SELECT id, user_id_fk, last_updated, net_worth
            FROM leaderboard
            ORDER BY user_id_fk ASC, last_updated DESC;
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
    def decimate_entries(conn:sqlite3.Connection, target:int=200):
        all_data = LeaderboardEndpoint.fetch_and_group_leaderboard(conn)
        for user_id, data in all_data.items():
            print(f"betrachte Nutzer {user_id}. Datenlänge: {len(data)}")
            to_delete_rows = []
            og_length = len(data)

            #gleiche löschen
            if len(data) >= 2:
                for i in range(len(data) - 2, -1, -1):
                    if data[i]['net_worth'] == data[i+1]['net_worth']:
                        to_delete_rows.append(data[i]['row_id'])
                        data.pop(i)

            delta = [data[i]["datetime"] - data[i - 1]["datetime"] for i in range(1, len(data))]

            while True:
                if og_length - len(to_delete_rows) <= target:
                    break

                mini_mum = min(delta)
                i_minimum = delta.index(mini_mum)
                if i_minimum == 0:
                    to_delete_rows.append(data[i_minimum + 1]["row_id"])
                    delta[i_minimum + 1] = delta[i_minimum + 1] + delta[i_minimum]
                    delta.pop(i_minimum)
                    data.pop(i_minimum + 1)
                else:
                    to_delete_rows.append(data[i_minimum]["row_id"])
                    delta[i_minimum - 1] = delta[i_minimum - 1] + delta[i_minimum]
                    delta.pop(i_minimum)
                    data.pop(i_minimum)

            for i in to_delete_rows:
                LeaderboardEndpoint.delete_row(conn, i)





















