# backend/app/gst.py
# Relaxed GST validation ONLY:
# - Must start with "GST"
# - Must have at least one more character after GST
# No regex/checksum.

def is_valid_gstin(gstin: str) -> bool:
    gstin = (gstin or "").strip()
    return gstin.upper().startswith("GST") and len(gstin) > 3
