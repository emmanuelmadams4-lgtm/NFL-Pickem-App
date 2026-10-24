import sys
sys.path.insert(0, ".")
from app_store.main import create_app
app = create_app()
print("App created OK")
print("Number of routes:", len(app.routes))
