import os
import sys
import time
import logging

from app import app, run_due_monitoring_checks

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO")
)

log = logging.getLogger("cyberlord-monitor")


def run_once():
    log.info("Starting scheduled monitoring check")

    with app.app_context():
        run_due_monitoring_checks(batch_size=10)

    log.info("Monitoring check completed")


if __name__ == "__main__":

    if "--once" in sys.argv:
        try:
            run_once()
        except Exception:
            log.exception("Monitoring check failed")
            sys.exit(1)

    else:
        log.info("CyberLord monitoring worker started")

        while True:
            try:
                run_once()
            except Exception:
                log.exception("Monitoring worker loop failed")

            time.sleep(
                max(30, int(os.getenv("MONITOR_POLL_SECONDS", "60")))
            )