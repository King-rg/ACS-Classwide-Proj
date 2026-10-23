"""Compatibility entry point for the complete shared-style figure set."""
from plot import execute
from pathlib import Path
import sys
if __name__ == '__main__':
    execute(Path(__file__).resolve().parents[1], 2, 'plots', sys.argv[1] if len(sys.argv)>1 else None)
