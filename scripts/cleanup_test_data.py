#!/usr/bin/env python3
"""Script to clean up test data - team rosters and draft files."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.cleanup_service import CleanupService


def main():
    """Clean up all test data."""
    cleanup = CleanupService()
    
    print("Cleaning up test data...")
    print(f"Teams directory: {cleanup.teams_dir}")
    print(f"Drafts directory: {cleanup.drafts_dir}")
    
    # Clean up all team rosters
    print("\nCleaning up team rosters...")
    cleanup.cleanup_all_team_rosters()
    print("✓ All team rosters cleaned")
    
    # Clean up all draft files (keep latest)
    print("\nCleaning up draft files (keeping latest)...")
    cleanup.cleanup_all_drafts(keep_latest=True)
    print("✓ Old draft files removed")
    
    print("\n✓ Cleanup complete!")


if __name__ == "__main__":
    main()

