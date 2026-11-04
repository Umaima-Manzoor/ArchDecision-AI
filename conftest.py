import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))      # insert the root directory at the beginning of the search path so that tests can import modules from the app package