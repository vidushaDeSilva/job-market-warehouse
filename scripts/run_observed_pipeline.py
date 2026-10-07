"""
run_observed_pipeline.py

Backward-compatible wrapper for the Sprint 13 orchestrator.

The real orchestration logic now lives in:

    scripts/orchestrate_pipeline.py
"""

from scripts.orchestrate_pipeline import main

if __name__ == "__main__":
    main()
