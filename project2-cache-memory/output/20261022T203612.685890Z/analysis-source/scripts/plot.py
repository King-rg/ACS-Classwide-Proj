"""Compatibility entry point; use make plots for the public interface."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'shared'))
from report_pipeline import execute
if __name__ == '__main__':
    execute(Path(__file__).resolve().parents[1], 2, 'plots', sys.argv[1] if len(sys.argv)>1 else None)
