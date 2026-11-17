import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["META_APP_SECRET"] = "testsecret"
os.environ["META_VERIFY_TOKEN"] = "vt"
os.environ["ADMIN_TOKEN"] = "adm"
os.environ["ENCRYPTION_KEY"] = "_-69gdd8xq8HCsxhwtbIFsZI8dJ3Rz4F7d0haNhi_Uo="
os.environ["HUMANIZER_ENABLED"] = "false"
os.environ["DEBOUNCE_SECONDS"] = "0"
os.environ["RUN_MAINTENANCE"] = "false"
if os.path.exists("test.db"):
    os.remove("test.db")
