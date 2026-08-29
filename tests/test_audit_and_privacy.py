import pytest
import os
import tempfile
from mfp_logger.audit import AuditLogger, sanitize_log_record
from mfp_logger.storage import ImageStorage

def test_audit_logs_redact_sensitive_headers_and_tokens():
    raw_event = {
        "action": "submit_diary_entry",
        "user_id": "user123",
        "cookie": "session_id=SECRET123; cf_clearance=SECRET_CF",
        "authorization": "Bearer SECRET_BEARER",
        "food_id": "98765",
        "status": "success",
    }
    sanitized = sanitize_log_record(raw_event)
    assert "SECRET123" not in str(sanitized)
    assert "SECRET_CF" not in str(sanitized)
    assert "SECRET_BEARER" not in str(sanitized)
    assert "cookie" not in sanitized or sanitized["cookie"] == "[REDACTED]"
    assert "authorization" not in sanitized or sanitized["authorization"] == "[REDACTED]"
    assert sanitized["food_id"] == "98765"

def test_image_cleanup_after_verification():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = ImageStorage(base_dir=tmpdir)
        # Create a temporary meal photo
        img_path = os.path.join(tmpdir, "meal_123.jpg")
        with open(img_path, "w") as f:
            f.write("fake-image-bytes")

        # Cleanup un-retained photo
        storage.cleanup_image(img_path, retain_for_recipe=False)
        assert not os.path.exists(img_path)

        # Retained photo should not be deleted
        img_path2 = os.path.join(tmpdir, "meal_recipe.jpg")
        with open(img_path2, "w") as f:
            f.write("fake-recipe-bytes")
        storage.cleanup_image(img_path2, retain_for_recipe=True)
        assert os.path.exists(img_path2)
