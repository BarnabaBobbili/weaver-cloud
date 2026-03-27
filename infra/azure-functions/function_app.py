"""
Azure Function: Synapse Incremental ETL

Runs on a frequent timer to export PostgreSQL data to Synapse Data Lake.
Triggered by a timer schedule.
"""
import os
import logging
import httpx
import azure.functions as func

app = func.FunctionApp()

# Get backend URL from environment
BACKEND_URL = os.environ.get("BACKEND_URL", "https://weaver-backend.whitehill-eea76820.centralindia.azurecontainerapps.io")
SYNAPSE_SYNC_API_KEY = os.environ.get("SYNAPSE_SYNC_API_KEY", "")


@app.schedule(schedule="0 */5 * * * *", arg_name="mytimer", run_on_startup=False,
              use_monitor=False) 
def synapse_daily_export(mytimer: func.TimerRequest) -> None:
    """
    Runs every 5 minutes.
    
    Schedule format: {second} {minute} {hour} {day} {month} {day-of-week}
    "0 */5 * * * *" = Every 5 minutes
    """
    if mytimer.past_due:
        logging.info('The timer is past due!')

    logging.info('Starting Synapse incremental ETL export...')

    try:
        if not SYNAPSE_SYNC_API_KEY:
            raise ValueError("SYNAPSE_SYNC_API_KEY is not configured")

        headers = {"X-Synapse-Sync-Key": SYNAPSE_SYNC_API_KEY}

        response = httpx.post(
            f"{BACKEND_URL}/api/analytics/synapse/export/internal?include_daily_rollup=false",
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

    logging.info('Synapse incremental ETL export finished')
