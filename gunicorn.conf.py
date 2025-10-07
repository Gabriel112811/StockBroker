# gunicorn.conf.py (KORRIGIERTE VERSION)
"""
Dieses Skript sorgt dafür, dass der gunicorn-Server Prozesse ausführt, die an die Uhrzeit geknüpft sind.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from backend.jobs import scheduled_order_processing_job
from backend.jobs import scheduled_leaderboard_processing_job
from backend.jobs import scheduled_daily_processing_job

# 1. Erstellen und konfigurieren Sie den Scheduler im globalen Bereich der Konfigurationsdatei.
#    Starten Sie ihn hier aber NICHT.
scheduler = BackgroundScheduler(daemon=True, timezone="Europe/Berlin")
scheduler.add_job(scheduled_order_processing_job, 'cron', minute='*')  # Jede Minute
scheduler.add_job(scheduled_daily_processing_job, 'cron', hour='5', minute='0')  # Um 5:00 Uhr
scheduler.add_job(scheduled_leaderboard_processing_job, 'cron', minute='*/10')  # Wenn Minuten teilbar durch 10


def post_fork(server, worker):
    """
    Dieser Hook wird in jedem Worker-Prozess aufgerufen, NACHDEM er erstellt wurde.
    Dies ist der sichere Ort, um den Scheduler zu starten.
    """
    # 2. Starten Sie den Scheduler erst HIER, innerhalb des Worker-Prozesses.
    #    Jeder Worker erhält so seinen eigenen, sauberen Scheduler-Thread.
    scheduler.start()
    worker.log.info("APScheduler wurde erfolgreich im Worker (PID: %s) gestartet.", worker.pid)

# Der 'when_ready' Hook wird für den Scheduler nicht mehr benötigt und sollte entfernt werden.
# def when_ready(server):
#    ... (dieser Teil ist falsch und sollte gelöscht werden)