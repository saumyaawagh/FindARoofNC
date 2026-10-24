import sys
from pathlib import Path

# Let tests `import config` / `import helpers` the same way the step scripts do.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
