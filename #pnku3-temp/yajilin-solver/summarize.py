#!/usr/bin/env python3
"""
Edge-pattern summarizer for Yajilin solver output.

Reads a solver output file (produced by solver.py with -a or -u) and
extracts the four edges (top row, bottom row, left column, right column)
from every solution.  Deduplicates edge patterns, assigns each unique
pattern an index, and prints a summary of how many solutions occur for
each combination of the four edge indices.

Usage:
    python summarize.py blue-variant-out.txt
"""

import sys
import os
from collections import defaultdict


def parse_solutions(text):
    """
    Parse a solver output file and yield each solution's ASCII grid rows.

    Yields: list of strings, each a full grid row (with 3-char-wide cells,
            no leading indentation).
    """
    lines = text.split('\n')
    solutions = []
    in_ascii = False
    current_grid = []
    solution_num = 0

    for line in lines:
        # Detect start of a new solution
        if line.startswith('--- Solution #'):
            in_ascii = False
            if current_grid:
                solutions.append(current_grid)
                current_grid = []
            continue

        # Detect start of ASCII section
        if line.strip() == 'Box-drawing:':
            in_ascii = True
            current_grid = []
            continue

        # Detect end of ASCII section (next section or next solution)
        if in_ascii and (line.strip().startswith('Verification:') or
                         line.strip().startswith('Box-drawing:')):
            in_ascii = False
            continue

        # Collect ASCII grid lines
        if in_ascii and line.startswith('  ') and len(line.strip()) > 0:
            # Strip the 2-space indent
            grid_line = line[2:]
            current_grid.append(grid_line)

    # Don't forget the last solution
    if current_grid:
        solutions.append(current_grid)

    return solutions


def extract_edges(grid):
    """
    Extract the four edge patterns from a grid.

    Returns (top, bottom, left, right) where each is a string:
      - top: the first row
      - bottom: the last row
      - left: the first cell of each row, concatenated
      - right: the last cell of each row, concatenated
    """
    if not grid:
        return '', '', '', ''

    rows = len(grid)

    # Top and bottom rows
    top = grid[0]
    bottom = grid[-1]

    # Left and right columns (each cell is 3 chars wide)
    left_cells = []
    right_cells = []
    for row in grid:
        # Last cell is the last 3 characters
        left_cells.append(row[:3])
        right_cells.append(row[-3:])

    left = ''.join(left_cells)
    right = ''.join(right_cells)

    return top, bottom, left, right


def build_catalog(patterns):
    """
    Given a list of patterns (strings), return a dict mapping pattern -> index
    and a list of patterns in index order.
    """
    unique = []
    index = {}
    for p in patterns:
        if p not in index:
            index[p] = len(unique)
            unique.append(p)
    return index, unique


def read_file(path):
    """Read a file trying UTF-8 first, then UTF-16."""
    for enc in ['utf-8', 'utf-16-le', 'utf-16-be', 'utf-16']:
        try:
            with open(path, 'r', encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    # Last resort: read as bytes and decode
    with open(path, 'rb') as f:
        raw = f.read()
    # Strip BOM if present
    if raw.startswith(b'\xff\xfe'):
        return raw[2:].decode('utf-16-le')
    if raw.startswith(b'\xfe\xff'):
        return raw[2:].decode('utf-16-be')
    raise ValueError(f"Cannot decode file: {path}")


def summarize(input_path):
    text = read_file(input_path)

    solutions = parse_solutions(text)

    if not solutions:
        print("No solutions found in input file.")
        return

    print(f"Parsed {len(solutions)} solution(s) from {input_path}")
    print()

    # Extract edges from all solutions
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

    # Build unique catalogs
    top_idx, top_catalog = build_catalog(all_tops)
    bot_idx, bot_catalog = build_catalog(all_bottoms)
    left_idx, left_catalog = build_catalog(all_lefts)
    right_idx, right_catalog = build_catalog(all_rights)

    # --- Print unique edge patterns ---
    print("=" * 60)
    print("UNIQUE EDGE PATTERNS")
    print("=" * 60)

    def print_row_catalog(name, catalog):
        """Print a catalog of row patterns (horizontal display)."""
        print(f"\n--- {name} ({len(catalog)} unique) ---")
        for i, pattern in enumerate(catalog):
            print(f"  [{i}] {pattern}")

    def print_col_catalog(name, catalog):
        """Print a catalog of column patterns as a matrix.
        Each unique case is a column; indices form the header row."""
        print(f"\n--- {name} ({len(catalog)} unique) ---")
        if not catalog:
            return
        # Split each pattern into 3-char cells
        all_cells = []
        max_rows = 0
        for pattern in catalog:
            cells = [pattern[j:j+3] for j in range(0, len(pattern), 3)]
            all_cells.append(cells)
            max_rows = max(max_rows, len(cells))
        # Zero-padded index width based on total count
        n = len(catalog)
        idx_w = max(len(str(n - 1)), 1)  # digits needed for max index
        # Header format: "[00]" = idx_w + 3 chars (brackets + digits)
        hdr_fmt = f"[{{:0{idx_w}d}}]"
        # Column width: at least the header width, at least 3 for cell data
        col_w = max(len(hdr_fmt.format(0)), 3)
        # Row label gutter width
        row_label_w = len(str(max_rows - 1)) + 2  # " N:"
        # Index header row
        header = " " * (row_label_w + 1)
        for i in range(n):
            header += hdr_fmt.format(i).ljust(col_w + 1)
        print(header)
        # Separator line
        sep = " " * (row_label_w + 1)
        for i in range(n):
            sep += "-" * col_w + " "
        print(sep)
        # Data rows
        for row_idx in range(max_rows):
            line = f"  {row_idx:>{len(str(max_rows-1))}}:"  # row label
            for col_idx in range(n):
                if row_idx < len(all_cells[col_idx]):
                    cell = all_cells[col_idx][row_idx]
                else:
                    cell = ""
                line += " " + cell.ljust(col_w)
            print(line)

    print_row_catalog("TOP rows", top_catalog)
    print_row_catalog("BOTTOM rows", bot_catalog)
    print_col_catalog("LEFT columns", left_catalog)
    print_col_catalog("RIGHT columns", right_catalog)

    # --- Count combinations ---
    print()
    print("=" * 60)
    print("COMBINATION COUNTS")
    print("=" * 60)

    combo_counts = defaultdict(int)
    for i in range(len(solutions)):
        combo = (top_idx[all_tops[i]], bot_idx[all_bottoms[i]],
                 left_idx[all_lefts[i]], right_idx[all_rights[i]])
        combo_counts[combo] += 1

    # Sort by count descending, then by indices
    sorted_combos = sorted(combo_counts.items(),
                           key=lambda x: (-x[1], x[0]))

    # Determine zero-padding width for each edge
    max_top = max((c[0] for c in combo_counts), default=0)
    max_bot = max((c[1] for c in combo_counts), default=0)
    max_lft = max((c[2] for c in combo_counts), default=0)
    max_rgt = max((c[3] for c in combo_counts), default=0)

    def zw(val, max_val):
        """Zero-padded string: width = number of digits in max_val."""
        w = max(len(str(max_val)), 1)
        return f"{val:0{w}d}"

    # Column widths: at least header width, at most needed for zero-padded data
    w_top = max(3, len(zw(max_top, max_top)))
    w_bot = max(3, len(zw(max_bot, max_bot)))
    w_lft = max(3, len(zw(max_lft, max_lft)))
    w_rgt = max(3, len(zw(max_rgt, max_rgt)))

    print(f"\n{'Top':>{w_top}} {'Bot':>{w_bot}} {'Lft':>{w_lft}} {'Rgt':>{w_rgt}}  {'Count':>6}")
    print(f"{'─'*w_top} {'─'*w_bot} {'─'*w_lft} {'─'*w_rgt}  {'─'*6}")
    for (ti, bi, li, ri), count in sorted_combos:
        print(f"{zw(ti, max_top):>{w_top}} {zw(bi, max_bot):>{w_bot}} "
              f"{zw(li, max_lft):>{w_lft}} {zw(ri, max_rgt):>{w_rgt}}  "
              f"{count:>6}")

    total_combos = len(combo_counts)
    print(f"\n{total_combos} unique edge combination(s) across "
          f"{len(solutions)} solution(s).")

    if len(solutions) == 1:
        print("Solution is UNIQUE.")
    elif total_combos == 1:
        print("All solutions share the same four edges "
              "(edges are uniquely determined).")
    else:
        print(f"Edges vary across solutions.")


def main():
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        input_path = os.path.join(script_dir, "blue-variant-out.txt")

    if not os.path.exists(input_path):
        print(f"File not found: {input_path}")
        return 1

    summarize(input_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
