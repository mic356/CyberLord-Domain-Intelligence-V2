"""CyberLord scheduled monitoring worker; deploy as a persistent worker service."""
import os, time, logging
from app import app, run_due_monitoring_checks
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("cyberlord-monitor")
if __name__ == "__main__":
    log.info("CyberLord monitoring worker started")
    while True:
        try:
            with app.app_context():
                run_due_monitoring_checks(batch_size=10)
        except Exception:
            log.exception("Monitoring worker loop failed")
        time.sleep(max(30, int(os.getenv("MONITOR_POLL_SECONDS", "60"))))
