#!/usr/bin/env python3
"""
Rename subtitle files (.srt) to 1.srt, 2.srt, ... according to episode order.

The script extracts season and episode numbers from filenames using the pattern
'S<season>E<episode>' (case‑insensitive). Files are sorted by season then episode,
and renamed sequentially.

If any target file (e.g., 1.srt) already exists, the script aborts to prevent
accidental overwrites. Run with --dry-run to see what would be done.
"""

import os
import re
import argparse
import sys
from pathlib import Path

def extract_season_episode(filename):
    """
    Extract season and episode numbers from a filename.
    Returns (season, episode) as integers, or (None, None) if not found.
    """
    match = re.search(r'S(\d+)E(\d+)', filename, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None

def main():
    parser = argparse.ArgumentParser(
        description="Rename .srt files to numbered order based on SxxExx pattern."
    )
    parser.add_argument(
        'directory', nargs='?', default='.',
        help="Directory containing the .srt files (default: current directory)"
    )
    parser.add_argument(
        '--dry-run', '-n', action='store_true',
        help="Show what would be renamed without actually doing it"
    )
    args = parser.parse_args()

    dir_path = Path(args.directory).resolve()
    if not dir_path.is_dir():
        print(f"Error: '{dir_path}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    # Gather all .srt files (including .en.srt, .hi.srt, etc.)
    srt_files = list(dir_path.glob("*.srt"))
    if not srt_files:
        print("No .srt files found.")
        return

    # Extract season/episode for each file
    episodes = []
    for f in srt_files:
        season, episode = extract_season_episode(f.name)
        if season is None or episode is None:
            print(f"Warning: Skipping '{f.name}' – no SxxExx pattern found.")
            continue
        episodes.append((season, episode, f))

    if not episodes:
        print("No files with a valid SxxExx pattern found.")
        return

    # Sort by season, then episode
    episodes.sort(key=lambda x: (x[0], x[1]))

    # Check for existing target files that would be overwritten
    existing_targets = []
    for idx, (_, _, old_path) in enumerate(episodes, start=1):
        new_name = f"{idx}.srt"
        new_path = dir_path / new_name
        if new_path.exists() and new_path != old_path:  # different file with same name
            existing_targets.append(new_name)

    if existing_targets:
        print("Error: The following target file(s) already exist and would be overwritten:",
              file=sys.stderr)
        for name in existing_targets:
            print(f"  {name}", file=sys.stderr)
        print("Aborting. Please remove or rename those files first.", file=sys.stderr)
        sys.exit(1)

    # Perform renaming
    for idx, (_, _, old_path) in enumerate(episodes, start=1):
        new_name = f"{idx}.srt"
        new_path = dir_path / new_name
        if args.dry_run:
            print(f"Would rename: '{old_path.name}' -> '{new_name}'")
        else:
            print(f"Renaming: '{old_path.name}' -> '{new_name}'")
            old_path.rename(new_path)

    if args.dry_run:
        print("\nDry run completed. No files were changed.")

if __name__ == "__main__":
    main()