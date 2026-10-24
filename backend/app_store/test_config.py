import sys
sys.path.insert(0, ".")
from app_store.config import get_settings, Settings

s = Settings()
print("Config OK:", s.database_url, "| passkey_rp_id:", s.passkey_rp_id)
