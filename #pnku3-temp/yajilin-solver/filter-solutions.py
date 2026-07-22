#!/usr/bin/env python3
"""
Filter solver output by edge pattern indices.

Given a solver output file and filter criteria like LEFT=4, BOTTOM=6,
outputs only the solutions whose edge patterns match the given indices.

Edge indices correspond to those shown by summarize.py.

Usage:
    python filter-solutions.py blue-variant-out.txt LEFT=4 BOTTOM=0
    python filter-solutions.py red-variant-out.txt TOP=2 RIGHT=3
    python filter-solutions.py blue-variant-out.txt LEFT=4,RIGHT=6  (comma optional)
"""

import sys
import os
from collections import defaultdict


# ---------------------------------------------------------------------------
# Shared parsing (same logic as summarize.py)
# ---------------------------------------------------------------------------

def read_file(path):
    """Read a file trying UTF-8 first, then UTF-16."""
    for enc in ['utf-8', 'utf-16-le', 'utf-16-be', 'utf-16']:
        try:
            with open(path, 'r', encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    with open(path, 'rb') as f:
        raw = f.read()
    if raw.startswith(b'\xff\xfe'):
        return raw[2:].decode('utf-16-le')
    if raw.startswith(b'\xfe\xff'):
        return raw[2:].decode('utf-16-be')
    raise ValueError(f"Cannot decode file: {path}")


def parse_solutions(text):
    """Parse solver output and yield each solution's ASCII grid rows."""
    lines = text.split('\n')
    solutions = []
    in_ascii = False
    current_grid = []

    for line in lines:
        if line.startswith('--- Solution #'):
            in_ascii = False
            if current_grid:
                solutions.append(current_grid)
                current_grid = []
            continue

        if line.strip() == 'Box-drawing:':
            in_ascii = True
            current_grid = []
            continue

        if in_ascii and (line.strip().startswith('Verification:') or
                         line.strip().startswith('Box-drawing:')):
            in_ascii = False
            continue

        if in_ascii and line.startswith('  ') and len(line.strip()) > 0:
            current_grid.append(line[2:])

    if current_grid:
        solutions.append(current_grid)

    return solutions


def extract_edges(grid):
    """Extract the four edge patterns from a grid."""
    if not grid:
        return '', '', '', ''
    top = grid[0]
    bottom = grid[-1]
    left_cells = [row[:3] for row in grid]
    right_cells = [row[-3:] for row in grid]
    left = ''.join(left_cells)
    right = ''.join(right_cells)
    return top, bottom, left, right


def build_catalog(patterns):
    """Return dict mapping pattern -> index."""
    idx = {}
    for p in patterns:
        if p not in idx:
            idx[p] = len(idx)
    return idx


# ---------------------------------------------------------------------------
# Filter logic
# ---------------------------------------------------------------------------

EDGE_NAMES = {'TOP': 'top', 'BOTTOM': 'bottom', 'LEFT': 'left', 'RIGHT': 'right'}
EDGE_ABBREV = {'T': 'TOP', 'B': 'BOTTOM', 'L': 'LEFT', 'R': 'RIGHT'}


def parse_filters(args):
    """Parse filter criteria like LEFT=4, BOTTOM=6 from CLI args.

    Returns dict mapping edge name ('top', 'bottom', 'left', 'right')
    to required index (int).
    """
    filters = {}
    for arg in args:
        # Allow comma-separated: LEFT=4,RIGHT=6
        for part in arg.split(','):
            part = part.strip()
            if '=' not in part:
                continue
            key, val = part.split('=', 1)
            key = key.strip().upper()
            val = val.strip()
            # Resolve abbreviations
            if key in EDGE_ABBREV:
                key = EDGE_ABBREV[key]
            if key not in EDGE_NAMES:
                print(f"Warning: unknown edge '{key}'. "
                      f"Use TOP, BOTTOM, LEFT, RIGHT (or T, B, L, R).",
                      file=sys.stderr)
                continue
            try:
                filters[EDGE_NAMES[key]] = int(val)
            except ValueError:
                print(f"Warning: invalid index '{val}' for {key}.",
                      file=sys.stderr)
    return filters


def filter_solutions(output_path, filters):
    """Read output file and yield grids matching all filter criteria."""
    text = read_file(output_path)
    solutions = parse_solutions(text)

    if not solutions:
        return

    # Build edge catalogs from all solutions
    all_tops = []
    all_bottoms = []
    all_lefts = []
    all_rights = []

    for grid in solutions:
        t, b, l, r = extract_edges(grid)
        all_tops.append(t)
        all_bottoms.append(b)
        all_lefts.append(l)
        all_rights.append(r)

    top_idx = build_catalog(all_tops)
    bot_idx = build_catalog(all_bottoms)
    left_idx = build_catalog(all_lefts)
    right_idx = build_catalog(all_rights)

    idx_maps = {
        'top': top_idx,
        'bottom': bot_idx,
        'left': left_idx,
        'right': right_idx,
    }
    all_edges = {
        'top': all_tops,
        'bottom': all_bottoms,
        'left': all_lefts,
        'right': all_rights,
    }

    # Print active filters
    print(f"Filters:", file=sys.stderr)
    for edge, target in sorted(filters.items()):
        total = len(idx_maps[edge])
        print(f"  {edge.upper()} = {target} (of {total} unique patterns)",
              file=sys.stderr)
    print(file=sys.stderr)

    # Yield matching solutions
    matched = 0
    for i, grid in enumerate(solutions):
        match = True
        for edge, target in filters.items():
            pattern = all_edges[edge][i]
            actual = idx_maps[edge][pattern]
            if actual != target:
                match = False
                break
        if match:
            matched += 1
            yield i + 1, grid  # 1-based solution number

    print(f"Matched {matched} of {len(solutions)} solution(s).",
          file=sys.stderr)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

# ANSI color codes
BLUE = '\033[34m'
RED = '\033[31m'
RESET = '\033[0m'

# Box-drawing characters that indicate a line/path cell
LINE_CHARS = set('╔╗╚╝║═╠╣╦╩╬╞╡╥╨╧╤╪╫')


def colorize_row(row):
    """Wrap line cells in blue and endpoint markers in red.
    Each cell is 3 chars wide."""
    result = []
    for i in range(0, len(row), 3):
        cell = row[i:i+3]
        stripped = cell.strip()
        if stripped and stripped[0] == '!':
            # Endpoint marker: red
            result.append(f"{RED}{cell}{RESET}")
        elif any(c in LINE_CHARS for c in cell):
            # Line/path cell: blue
            result.append(f"{BLUE}{cell}{RESET}")
        else:
            result.append(cell)
    return ''.join(result)


def print_solution(num, grid, use_color=False):
    """Print a single solution in box-drawing grid format."""
    print(f"--- Solution #{num} ---")
    print()
    print("  Box-drawing:")
    for row in grid:
        line = f"  {colorize_row(row)}" if use_color else f"  {row}"
        print(line)
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    use_color = False
    filters_args = []

    for a in args:
        if a == '--color':
            use_color = True
        else:
            filters_args.append(a)

    if len(filters_args) < 1:
        print("Usage: python filter-solutions.py <output-file> [FILTER...] [--color]",
              file=sys.stderr)
        print("  FILTER:  LEFT=4  BOTTOM=0  TOP=2  RIGHT=3", file=sys.stderr)
        print("  --color: colorize output (blue=lines, red=endpoints)", file=sys.stderr)
        return 1

    output_path = filters_args[0]
    if not os.path.exists(output_path):
        print(f"File not found: {output_path}", file=sys.stderr)
        return 1

    filters = parse_filters(filters_args[1:])
    if not filters:
        print("No valid filters given. Use e.g. LEFT=4 BOTTOM=0",
              file=sys.stderr)
        return 1

    for num, grid in filter_solutions(output_path, filters):
        print_solution(num, grid, use_color)

    return 0


if __name__ == "__main__":
    sys.exit(main())
