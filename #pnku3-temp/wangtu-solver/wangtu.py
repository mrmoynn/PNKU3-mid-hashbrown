#!/usr/bin/env python3
"""
Wangtu — King-Move Logic Puzzle Solver

Given an n×m grid with forbidden cells and king pieces (each annotated
with a step count), find ALL ways to move every king exactly that many
steps such that:
  1. No two kings ever occupy the same cell (including along their paths).
  2. No king ever steps on a forbidden cell.
  3. At their final positions, no two kings check each other
     (Chebyshev distance ≤ 1 — adjacent in any of the 8 directions).

Usage:
    python wangtu.py < input.txt
    python wangtu.py puzzle.txt
    python wangtu.py puzzle.txt --max-solutions 50
    python wangtu.py puzzle.txt --compact
"""

import argparse
import sys
import time
from dataclasses import dataclass
from typing import List, Tuple, Set, Optional, Dict

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class King:
    """A king piece with its starting position and required step count."""
    kid: int                # 0-based unique identifier
    row: int
    col: int
    steps: int

# A path is a sequence of positions (row, col), length = steps + 1
Path = List[Tuple[int, int]]
# One solution: one path per king (in the same order as the kings list)
Solution = List[Path]
# Parsed integer grid: -1 = forbidden, 0 = empty, positive = king with N steps
Grid = List[List[int]]

# King move offsets (8-directional, Chebyshev neighbourhood)
_KING_MOVES: List[Tuple[int, int]] = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1),
]


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------

def _read_file(path: str) -> str:
    """
    Read *path* trying the most common encodings so the file can be
    created by any text editor or shell redirection and still be read
    back reliably.
    """
    for enc in ('utf-8', 'utf-8-sig', 'utf-16', 'latin-1'):
        try:
            with open(path, encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    with open(path, 'rb') as f:
        return f.read().decode('utf-8', errors='replace')


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_token(token: str) -> Tuple[int, Optional[int]]:
    """
    Convert a single input token to (grid_value, king_steps).

    Returns:
        (-1, None)   — forbidden cell  ('#' or '-1' token)
        ( 0, None)   — empty cell      ('.' token)
        ( 0, 0)      — 0-step king     ('0' token — stays in place)
        ( N, N)      — N-step king     (positive-integer token)

    Raises ValueError on unrecognised tokens.
    """
    if token == '#':
        return (-1, None)
    if token == '.':
        return (0, None)
    try:
        val = int(token)
        if val < -1:
            raise ValueError(f"Invalid grid value: {val}")
        if val == -1:
            return (-1, None)      # -1 = forbidden
        if val == 0:
            return (0, 0)          # 0 = 0-step king
        return (val, val)         # positive = king with that many steps
    except ValueError:
        raise ValueError(f"Unrecognised token: {token!r}")


def parse_grid(text: str) -> Tuple[Grid, int, int, List[King]]:
    """
    Parse the input text into grid data.

    Input format:
      - Lines starting with '#' are comments (ignored).
      - Blank lines are ignored.
      - Values are space-separated.
      - -1 or '#'  = forbidden cell
      -  '.'       = empty traversable cell
      -   0        = 0-step king (stays in place)
      -   N >= 1   = king that must move exactly N steps

    Returns:
        grid   — 2-D list of ints (-1 forbidden, 0 empty, >0 king at start)
        rows   — number of rows
        cols   — number of columns
        kings  — list of King objects, assigned kid in reading order

    Raises ValueError on malformed input.
    """
    raw_lines = text.splitlines()
    data_lines: List[str] = []
    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            continue
        # A line starting with '#' is a comment ONLY if its tokens
        # aren't all valid grid tokens.  If every token parses, it's a
        # data row where the first column happens to be forbidden.
        if stripped.startswith('#'):
            tokens = stripped.split()
            all_parse = True
            for t in tokens:
                try:
                    _parse_token(t)
                except ValueError:
                    all_parse = False
                    break
            if not all_parse:
                continue  # genuine comment
        data_lines.append(stripped)

    if not data_lines:
        raise ValueError("No data rows found in input.")

    grid: Grid = []
    kings: List[King] = []
    kid_counter = 0

    cols: Optional[int] = None

    for r, line in enumerate(data_lines):
        tokens = line.split()
        if cols is None:
            cols = len(tokens)
        elif len(tokens) != cols:
            raise ValueError(
                f"Row {r} has {len(tokens)} column(s), expected {cols}. "
                f"Line: {line!r}")

        row: List[int] = []
        for c, token in enumerate(tokens):
            cell_val, king_steps = _parse_token(token)
            row.append(cell_val)
            if king_steps is not None:
                kings.append(King(kid=kid_counter, row=r, col=c,
                                  steps=king_steps))
                kid_counter += 1
        grid.append(row)

    rows = len(grid)
    if cols is None:
        raise ValueError("Empty grid.")

    if not kings:
        raise ValueError("No kings found in input — nothing to solve.")

    return grid, rows, cols, kings


# ---------------------------------------------------------------------------
# Path enumeration
# ---------------------------------------------------------------------------

def _enumerate_paths(
    grid: Grid,
    start_row: int,
    start_col: int,
    steps: int,
    rows: int,
    cols: int,
) -> List[Path]:
    """
    Return all possible paths of exactly *steps* 8-directional king moves
    from the starting position.

    A path is a list of (row, col) positions of length *steps* + 1.
    The first element is always (start_row, start_col).

    A king cannot revisit any cell in its own path (self-avoiding walk).
    The path must never step on a forbidden cell (grid[r][c] == -1).

    Uses DFS recursion.
    """
    if steps == 0:
        return [[(start_row, start_col)]]

    paths: List[Path] = []
    start = (start_row, start_col)

    def dfs(r: int, c: int, remaining: int, path: List[Tuple[int, int]],
            visited: Set[Tuple[int, int]]) -> None:
        if remaining == 0:
            paths.append(list(path))
            return
        for dr, dc in _KING_MOVES:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue
            if grid[nr][nc] == -1:
                continue
            npos = (nr, nc)
            if npos in visited:
                continue
            path.append(npos)
            visited.add(npos)
            dfs(nr, nc, remaining - 1, path, visited)
            visited.discard(npos)
            path.pop()

    visited_start: Set[Tuple[int, int]] = {start}
    dfs(start_row, start_col, steps, [start], visited_start)
    return paths


# ---------------------------------------------------------------------------
# Constraint checking
# ---------------------------------------------------------------------------

def _kings_check(pos_a: Tuple[int, int], pos_b: Tuple[int, int]) -> bool:
    """
    Return True if two positions are within Chebyshev distance ≤ 1.
    Kings check each other if they are adjacent in any of the 8
    directions, including diagonally.
    """
    return max(abs(pos_a[0] - pos_b[0]), abs(pos_a[1] - pos_b[1])) <= 1


def _any_kings_check(positions: List[Tuple[int, int]]) -> bool:
    """
    Return True if ANY pair among the given positions are within
    Chebyshev distance ≤ 1.  O(K²) check — early-exits on first hit.
    """
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            if _kings_check(positions[i], positions[j]):
                return True
    return False


# ---------------------------------------------------------------------------
# Backtracking search
# ---------------------------------------------------------------------------

def _find_solutions(
    kings: List[King],
    all_paths: List[List[Path]],
    max_solutions: int,
    show_progress: bool = True,
) -> List[Solution]:
    """
    Find all combinations of paths (one per king) satisfying:
      1. No cell is visited by more than one king.
      2. No two kings check each other at their final positions.

    *kings* must be pre-sorted by MRV (fewest paths first).
    *all_paths* is indexed by King.kid.

    Uses depth-first backtracking with early pruning.
    Stops when *max_solutions* is reached.
    """
    solutions: List[Solution] = []
    start_time = time.time()
    nodes = [0]  # mutable counter
    max_step = max(k.steps for k in kings) if kings else 0

    def backtrack(ki: int, used_cells: Set[Tuple[int, int]],
                  current: List[Path]) -> None:
        if len(solutions) >= max_solutions:
            return

        if ki == len(kings):
            # All kings placed — check final-position constraint
            final_positions = [path[-1] for path in current]
            if not _any_kings_check(final_positions):
                solutions.append(list(current))
            return

        king = kings[ki]
        candidates = all_paths[king.kid]

        for path in candidates:
            path_set = set(path)
            if path_set & used_cells:
                continue  # overlaps with a previously placed king

            used_cells |= path_set
            current.append(path)

            nodes[0] += 1
            if show_progress and nodes[0] % 50000 == 0:
                elapsed = time.time() - start_time
                sys.stderr.write(
                    f"\r  searched {nodes[0]} nodes, "
                    f"found {len(solutions)} solutions, "
                    f"{elapsed:.1f}s elapsed   ")
                sys.stderr.flush()

            backtrack(ki + 1, used_cells, current)

            current.pop()
            used_cells -= path_set

            if len(solutions) >= max_solutions:
                return

    backtrack(0, set(), [])

    if show_progress:
        elapsed = time.time() - start_time
        sys.stderr.write(
            f"\r  searched {nodes[0]} nodes, "
            f"found {len(solutions)} solutions, "
            f"{elapsed:.1f}s elapsed   \n")
        sys.stderr.flush()

    return solutions


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def _kid_to_char(kid: int) -> str:
    """Convert a king ID (0-based) to a single display character."""
    if kid < 10:
        return str(kid)
    elif kid < 36:
        return chr(ord('A') + kid - 10)
    else:
        return '?'  # fallback for > 35 kings


def _build_display_grid(
    grid: Grid, rows: int, cols: int,
    positions: Dict[int, Tuple[int, int]],
) -> List[str]:
    """Build a list of strings representing the grid at a given step."""
    result: List[str] = []
    for r in range(rows):
        chars: List[str] = []
        for c in range(cols):
            if grid[r][c] == -1:
                chars.append('#')
                continue
            occupant: Optional[int] = None
            for kid, (pr, pc) in positions.items():
                if pr == r and pc == c:
                    occupant = kid
                    break
            if occupant is not None:
                chars.append(_kid_to_char(occupant))
            else:
                chars.append('.')
        result.append('  ' + ''.join(chars))
    return result


def _print_solution_compact(
    grid: Grid, rows: int, cols: int,
    kings: List[King],
    solution: Solution,
    index: int,
) -> None:
    """Print a solution in compact mode (coordinates only)."""
    print(f"=== Solution {index} ===")
    for ki, (king, path) in enumerate(zip(kings, solution)):
        coords = " ".join(f"({r},{c})" for r, c in path)
        print(f"# King {king.kid} ({king.steps} step(s), "
              f"start r{king.row}c{king.col})")
        print(coords)
    print()


def _print_solution_full(
    grid: Grid, rows: int, cols: int,
    kings: List[King],
    solution: Solution,
    index: int,
) -> None:
    """Print a solution with coordinate paths AND step-by-step ASCII
    visualisation."""
    print(f"=== Solution {index} ===")
    print()

    # --- Path listing ---
    print("Paths:")
    for king, path in zip(kings, solution):
        arrow = " → ".join(f"({r},{c})" for r, c in path)
        print(f"  King {king.kid} ({king.steps} step(s), "
              f"start r{king.row}c{king.col}):")
        print(f"    {arrow}")
    print()

    # --- Step-by-step visualisation ---
    max_step = max(k.steps for k in kings) if kings else 0

    # Build a mapping from kid → full path for quick step lookup
    kid_paths: Dict[int, Path] = {}
    for king, path in zip(kings, solution):
        kid_paths[king.kid] = path

    print("Step-by-step:")
    print()

    # Initial state
    print("  Initial:")
    init_positions: Dict[int, Tuple[int, int]] = {}
    for king, path in zip(kings, solution):
        init_positions[king.kid] = path[0]
    for line in _build_display_grid(grid, rows, cols, init_positions):
        print(line)
    print()

    # After each step
    for step in range(1, max_step + 1):
        print(f"  After step {step}:")
        step_positions: Dict[int, Tuple[int, int]] = {}
        for king in kings:
            path = kid_paths[king.kid]
            idx = min(step, len(path) - 1)  # king stays if done
            step_positions[king.kid] = path[idx]
        for line in _build_display_grid(grid, rows, cols, step_positions):
            print(line)
        print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Wangtu — King-Move Logic Puzzle Solver",
    )
    parser.add_argument(
        "input", nargs="?",
        help="Input puzzle file (default: read from stdin).",
    )
    parser.add_argument(
        "--max-solutions", type=int, default=1000,
        help="Maximum number of solutions to find (default: 1000).",
    )
    parser.add_argument(
        "--compact", action="store_true",
        help="Compact output: coordinates only, no step-by-step visuals.",
    )
    parser.add_argument(
        "--progress", dest="progress", action="store_true", default=None,
        help="Force progress reporting on.",
    )
    parser.add_argument(
        "--no-progress", dest="progress", action="store_false", default=None,
        help="Force progress reporting off.",
    )

    args = parser.parse_args()

    if args.max_solutions < 1:
        print("Error: --max-solutions must be >= 1.", file=sys.stderr)
        sys.exit(1)

    # --- Read input ---
    if args.input:
        text = _read_file(args.input)
    else:
        text = sys.stdin.read()

    # Strip BOM if present (PowerShell pipes may prepend one)
    text = text.lstrip('﻿')

    if not text.strip():
        print("Error: empty input.", file=sys.stderr)
        sys.exit(1)

    # --- Parse ---
    try:
        grid, rows, cols, kings = parse_grid(text)
    except ValueError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        sys.exit(1)

    forbidden_count = sum(
        1 for r in range(rows) for c in range(cols) if grid[r][c] == -1)
    print(f"// Grid: {rows}×{cols}, {len(kings)} king(s), "
          f"{forbidden_count} forbidden cell(s)",
          file=sys.stderr)

    for king in kings:
        print(f"//   King {king.kid}: ({king.row}, {king.col}), "
              f"{king.steps} step(s)", file=sys.stderr)

    # --- Progress detection ---
    if args.progress is None:
        show_progress = sys.stderr.isatty()
    else:
        show_progress = args.progress

    # --- Enumerate paths for each king ---
    all_paths: List[List[Path]] = []
    total_paths = 0

    for ki, king in enumerate(kings):
        if show_progress:
            sys.stderr.write(
                f"\r// Enumerating paths for king {king.kid} "
                f"({ki + 1}/{len(kings)}, steps={king.steps})...")
            sys.stderr.flush()
        paths = _enumerate_paths(
            grid, king.row, king.col, king.steps, rows, cols)
        all_paths.append(paths)
        total_paths += len(paths)

    if show_progress:
        sys.stderr.write(
            f"\r// Enumerated {total_paths} total path(s) "
            f"across {len(kings)} king(s)          \n")
        sys.stderr.flush()

    # --- Early exit: any king with zero paths? ---
    for king in kings:
        if len(all_paths[king.kid]) == 0:
            print(f"// King {king.kid} (at ({king.row},{king.col}), "
                  f"{king.steps} steps) has no valid paths.",
                  file=sys.stderr)
            print("No solution exists.", file=sys.stderr)
            sys.exit(1)

    # --- MRV sort (fewest paths first) ---
    kings_sorted = sorted(kings, key=lambda k: len(all_paths[k.kid]))
    if show_progress:
        path_counts = [len(all_paths[k.kid]) for k in kings_sorted]
        sys.stderr.write(f"// Path counts (MRV order): {path_counts}\n")
        sys.stderr.flush()

    # --- Warn about large path counts ---
    for king in kings:
        if len(all_paths[king.kid]) > 10000:
            print(f"// Warning: King {king.kid} has "
                  f"{len(all_paths[king.kid])} paths — search may be slow.",
                  file=sys.stderr)

    # --- Search ---
    if show_progress:
        sys.stderr.write("// Searching...\n")
        sys.stderr.flush()

    search_start = time.time()
    solutions = _find_solutions(
        kings_sorted, all_paths,
        max_solutions=args.max_solutions,
        show_progress=show_progress,
    )
    search_elapsed = time.time() - search_start

    # --- Output results ---
    if not solutions:
        print("No solution exists.", file=sys.stderr)
        sys.exit(1)

    print_fn = _print_solution_compact if args.compact else _print_solution_full
    for i, sol in enumerate(solutions):
        print_fn(grid, rows, cols, kings_sorted, sol, i + 1)

    # --- Summary to stderr ---
    capped = " (capped)" if len(solutions) >= args.max_solutions else ""
    unique = "unique" if len(solutions) == 1 else ""
    print(f"// Found {len(solutions)}{capped} solution(s) "
          f"in {search_elapsed:.1f}s {unique}",
          file=sys.stderr)


if __name__ == '__main__':
    main()
