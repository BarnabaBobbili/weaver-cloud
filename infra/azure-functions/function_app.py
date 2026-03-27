"""
Azure Function: Synapse Daily ETL

Runs daily at midnight UTC to export data from PostgreSQL to Synapse Data Lake.
Triggered by a timer schedule.
"""
import os
import logging
import httpx
import azure.functions as func

app = func.FunctionApp()

# Get backend URL from environment
BACKEND_URL = os.environ.get("BACKEND_URL", "https://weaver-backend.whitehill-eea76820.centralindia.azurecontainerapps.io")
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "")  # Set this in Function App settings


@app.schedule(schedule="0 0 0 * * *", arg_name="mytimer", run_on_startup=False,
              use_monitor=False) 
def synapse_daily_export(mytimer: func.TimerRequest) -> None:
    """
    Runs daily at midnight UTC.
    
    Schedule format: {second} {minute} {hour} {day} {month} {day-of-week}
    "0 0 0 * * *" = Every day at midnight
    """
    if mytimer.past_due:
        logging.info('The timer is past due!')

    logging.info('Starting Synapse daily ETL export...')

    try:
        # Call the backend export endpoint
        headers = {}
        if ADMIN_API_KEY:
            headers["Authorization"] = f"Bearer {ADMIN_API_KEY}"

        response = httpx.post(
            f"{BACKEND_URL}/api/analytics/synapse/export",
            headers=headers,
            timeout=300.0  # 5 minute timeout
        )
        
        response.raise_for_status()
        result = response.json()
        
        logging.info(f"Synapse export completed: {result}")
        logging.info(f"Status: {result.get('status')}")
        logging.info(f"Message: {result.get('message')}")
        
    except httpx.HTTPError as e:
        logging.error(f"HTTP error during Synapse export: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error during Synapse export: {e}")
        raise

    logging.info('Synapse daily ETL export finished')
