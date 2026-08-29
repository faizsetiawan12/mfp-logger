import json
import os
from typing import Dict, Any, Optional

SENSITIVE_KEYS = {
    "cookie",
    "authorization",
    "password",
    "token",
    "bearer",
    "csrf",
    "session",
    "cf_clearance",
    "secret",
}

def sanitize_log_record(record: Dict[str, Any]) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {}
    for k, v in record.items():
        k_lower = k.lower()
        if any(secret_key in k_lower for secret_key in SENSITIVE_KEYS):
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = sanitize_log_record(v)
        elif isinstance(v, str):
            if "bearer " in v.lower() or "cf_clearance" in v.lower():
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = v
        else:
            sanitized[k] = v
    return sanitized

class AuditLogger:
    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file

    def log(self, event: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = sanitize_log_record(event)
        if self.log_file:
            os.makedirs(os.path.dirname(os.path.abspath(self.log_file)), exist_ok=True)
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(sanitized) + "\n")
        return sanitized
