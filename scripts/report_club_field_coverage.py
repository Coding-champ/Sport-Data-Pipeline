#!/usr/bin/env python3
"""Quick coverage report for scraped club fields.

Usage:
  python scripts/report_club_field_coverage.py reports/clubs_playwright.json
"""
import sys, json, pathlib
from collections import Counter, defaultdict

KEY_FIELDS = [
    'official_name','website','street_address','postal_code','city',
    'colors','stadium','stadium_capacity','founded_year','phone','email'
]

COLOR_SUBFIELDS = ['primary','secondary','tertiary']

def load(path):
    with open(path,'r',encoding='utf-8') as f:
        return json.load(f)

def main():
    if len(sys.argv) < 2:
        print('Provide path to clubs json (e.g. reports/clubs_playwright.json)')
        return 1
    data = load(sys.argv[1])
    clubs = data.get('clubs') or []
    total = len(clubs)
    field_counts = Counter()
    color_counts = Counter()
    anomalies = []
    # Detect suspicious duplication of a specific official_name across many clubs (Augsburg issue)
    off_name_freq = Counter()

    for c in clubs:
        for f in KEY_FIELDS:
            val = c.get(f)
            if f == 'colors':
                if isinstance(val, dict) and any(val.values()):
                    field_counts[f] += 1
                    for sub in COLOR_SUBFIELDS:
                        if val.get(sub):
                            color_counts[sub] += 1
            else:
                if val not in (None, '', {}):
                    field_counts[f] += 1
        if c.get('official_name'):
            off_name_freq[c['official_name']] += 1
    # Identify top duplicated official_name
    duplicates = [name for name,count in off_name_freq.items() if count > 1]
    print(f"Total clubs: {total}")
    print("Field coverage (present/total, %):")
    for f in KEY_FIELDS:
        cnt = field_counts[f]
        pct = (cnt/total*100) if total else 0
        print(f"  {f:16s} {cnt:2d}/{total}  ({pct:5.1f}%)")
    if color_counts:
        print("Color subfield coverage:")
        for sub in COLOR_SUBFIELDS:
            cnt = color_counts[sub]
            pct = (cnt/total*100) if total else 0
            print(f"  colors.{sub:8s} {cnt:2d}/{total}  ({pct:5.1f}%)")
    if duplicates:
        print("\nPotential duplication anomalies (official_name repeated):")
        for name in sorted(duplicates, key=lambda n: off_name_freq[n], reverse=True):
            print(f"  '{name}' -> {off_name_freq[name]} clubs")

    # Flag clubs whose stadium/colors/official_name all match the most frequent duplicated one
    if duplicates:
        top_name = max(off_name_freq.items(), key=lambda x:x[1])[0]
        for c in clubs:
            if c.get('official_name') == top_name:
                anomalies.append(c['name'])
        if anomalies:
            print(f"\nClubs sharing top duplicated official_name '{top_name}': {', '.join(anomalies)}")

    return 0

if __name__ == '__main__':
    raise SystemExit(main())
