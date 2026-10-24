import sys
from pathlib import Path

# Add the project root to the path
PROJECT_ROOT = Path("/home/emadams/Projects/NFL-Pickem-App")
sys.path.insert(0, str(PROJECT_ROOT))

print("Path:", sys.path[0])
