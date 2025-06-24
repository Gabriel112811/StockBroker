# gunicorn.conf.py


import threading
from apscheduler.schedulers.background import BackgroundScheduler
from backend.jobs import scheduled_order_processing_job
from backend.jobs import scheduled_leaderboard_processing_job
from backend.jobs import scheduled_daily_processing_job


def when_ready(server):
    """
    Dieser Hook wird einmal im Gunicorn Master-Prozess aufgerufen,
    wenn der Server bereit ist.
    """

    # Erstelle einen Scheduler, der im Hintergrund läuft
    scheduler = BackgroundScheduler(daemon=True, timezone="Europe/Berlin")

    # Füge den Job hinzu, der jede Minute ausgeführt werden soll
    scheduler.add_job(scheduled_order_processing_job(), 'cron', minute='*')
    scheduler.add_job(scheduled_daily_processing_job(), 'cron', hour='5' ,minute='0')
    scheduler.add_job(scheduled_leaderboard_processing_job(), 'cron', minute='*/10')

    # Starte den Scheduler
    scheduler.start()

    server.log.info("APScheduler wurde erfolgreich gestartet.")