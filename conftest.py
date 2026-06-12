import sys
from pathlib import Path

# Allow "from scripts.X import Y" in both pytest and direct-run contexts
sys.path.insert(0, str(Path(__file__).parent))
