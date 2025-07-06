# gunicorn.conf.py
"""
Dieses Skript sorgt dafür, dass der gunicorn-Server Prozesse ausführt, die an die Uhrzeit geknüpft sind
"""
from apscheduler.schedulers.background import BackgroundScheduler
from backend.jobs import scheduled_order_processing_job
from backend.jobs import scheduled_leaderboard_processing_job
from backend.jobs import scheduled_daily_processing_job


def when_ready(server):
    """
    Dieser Hook wird einmal im Gunicorn Master-Prozess aufgerufen,
    wenn der Server bereit ist.
    """

    # Hintergrund Scheduler wird erstellt
    scheduler = BackgroundScheduler(daemon=True, timezone="Europe/Berlin")

    scheduler.add_job(scheduled_order_processing_job, 'cron', minute='*') #Jede Minute
    scheduler.add_job(scheduled_daily_processing_job, 'cron', hour='5' ,minute='0') #Um 5:00 Uhr
    scheduler.add_job(scheduled_leaderboard_processing_job, 'cron', minute='*/10') #Wenn Minuten teilbar durch 10

    scheduler.start()

    server.log.info("APScheduler wurde erfolgreich gestartet.")