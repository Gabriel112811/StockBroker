from app import app, get_db, update_popular_charts_cache
from backend.trading import TradingEndpoint
from backend.leaderboard import LeaderboardEndpoint
from backend.accounts_to_database import AccountEndpoint


def scheduled_order_processing_job():
    """Wird vom Scheduler aufgerufen, um offene Aufträge zu verarbeiten."""
    # app_context wird benötigt, damit der Hintergrund-Thread auf die App und die DB zugreifen kann
    with app.app_context():
        db = get_db()
        try:
            print("[Scheduler] Verarbeite offene Aufträge...")
            TradingEndpoint.process_open_orders(db)
            db.commit()
        except Exception as e:
            print(f"[Scheduler] Fehler im Job 'process_open_orders': {e}")

def scheduled_leaderboard_processing_job():
    with app.app_context():
        db = get_db()
        try:
            print("[Scheduler 2] Berechne das leaderboard Neu...")
            result = LeaderboardEndpoint.insert_all_current_net_worths(db)
            if result.get('success'):
                print("Leaderboard erfolgreich aktualisiert")
            db.commit()
        except Exception as e:
            print(f"[Scheduler] Fehler im Job 'leaderboard_processing_job': {e}")

def scheduled_daily_processing_job():
    with app.app_context():
        db = get_db()
        try:
            print("Starte Daily Scheduler")
            LeaderboardEndpoint.decimate_entries(db)
            result = AccountEndpoint.delete_unverified_users(db)
            print(result.get("message"))
            # Proaktives Caching der beliebten Charts
            update_popular_charts_cache(db)
            db.commit()
        except Exception as e:
            print(f"[Scheduler] Fehler im Job 'leaderboard_processing_job': {e}")