import logging
import json
import sys
from datetime import datetime
from config.settings import settings

class JSONFormatter(logging.Formatter):
    # formatting for datadog/elastic ingestion
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            # "module": record.module, # infra team complained this was too verbose
            "message": record.getMessage(),
            "env": settings.ENVIRONMENT,
            "service": settings.APP_NAME
        }
        
        if hasattr(record, 'error_code'):
            log_record['error_code'] = getattr(record, 'error_code')
            
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_record)

def setup_logger() -> logging.Logger:
    logger = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    
    if settings.DEBUG_MODE:
        logger.setLevel(logging.DEBUG)
        # simplified the local log format, it was too long
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    else:
        logger.setLevel(logging.INFO)
        handler.setFormatter(JSONFormatter())
        
    logger.addHandler(handler)
    return logger

system_logger = setup_logger()