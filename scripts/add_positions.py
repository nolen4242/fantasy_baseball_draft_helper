#!/usr/bin/env python3
"""
Helper script to add positions to batter CSV file.
You can manually edit positions or use this as a starting point.
"""
import csv
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
batters_file = project_root / "data" / "batters" / "steamer-batters.csv"

if not batters_file.exists():
    print(f"File not found: {batters_file}")
    sys.exit(1)

# Read the file
rows = []
with open(batters_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for row in reader:
        rows.append(row)

# Add position column if it doesn't exist
if 'Position' not in fieldnames and 'position' not in fieldnames:
    fieldnames = list(fieldnames) + ['Position']
    print("Added 'Position' column to CSV")
else:
    print("Position column already exists")

# Write back with position column (empty for now, user can fill in)
output_file = batters_file
with open(output_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        if 'Position' not in row:
            row['Position'] = ''  # Empty - user can fill in
        writer.writerow(row)

print(f"\nUpdated {len(rows)} players in {output_file}")
print("\nNext steps:")
print("1. Open the CSV file in Excel or a text editor")
print("2. Fill in the Position column with: C, 1B, 2B, 3B, SS, OF, etc.")
print("3. Save the file")
print("4. Reload players in the app")

