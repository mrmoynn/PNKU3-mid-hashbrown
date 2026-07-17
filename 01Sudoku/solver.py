#!/usr/bin/env python3
"""
Sudoku Possibility-Matrix Solver

Takes a Sudoku puzzle and outputs a 27×27 matrix showing, for every
original cell, exactly which digits can appear there in at least one
valid complete solution.

Two input formats are accepted (auto-detected by character count):
  1. Traditional 81-character string  (0 / . for empty, 1-9 for givens)
  2. 27×27 grid  (the same format as the solver's own output; redirected
     STDOUT can be used directly as input — grid-drawing characters are
     stripped automatically)

Usage:
    python solver.py < input.txt
    python solver.py puzzle.txt
    python solver.py --template           create template_all.txt
    echo "530070000600195000098000060800060003400803001700020006060000280000419005000080079" | python solver.py
"""

import sys
import time
from typing import List, Set, Tuple, Dict, Optional

# Characters stripped when reading any input file.
# Includes whitespace and the grid-drawing characters used in the output
# format, so that redirected STDOUT can be used directly as input.
_STRIP_CHARS = ' \t\n\r|-+='


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------

def _read_file(path: str) -> str:
    """
    Read *path* trying the most common encodings so that the file can be
    created by shell redirection (cmd.exe, PowerShell, bash) or any text
    editor and still be read back reliably.
    """
    for enc in ('utf-8', 'utf-8-sig', 'utf-16', 'latin-1'):
        try:
            with open(path, encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    # Last resort: read as raw bytes and decode replacing errors
    with open(path, 'rb') as f:
        return f.read().decode('utf-8', errors='replace')


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_grid(text: str) -> Tuple[List[List[int]],
                                     List[List[Optional[Set[int]]]]]:
    """
    Parse an 81-character Sudoku string into a 9x9 grid of ints plus
    per-cell allowed-digit constraints.

    Returns:
        grid           – 9x9, 0 = empty, 1-9 = given
        allowed_digits – 9x9, None = all 1-9 allowed, or a set of digits
                         (for given cells this is a single-element set)
    """
    chars = [ch for ch in text if ch not in _STRIP_CHARS]
    if len(chars) != 81:
        raise ValueError(f"Expected 81 non-whitespace characters, got {len(chars)}")

    grid: List[List[int]] = []
    allowed: List[List[Optional[Set[int]]]] = []

    for i in range(9):
        row: List[int] = []
        arow: List[Optional[Set[int]]] = []
        for j in range(9):
            ch = chars[i * 9 + j]
            if ch in ('0', '.'):
                row.append(0)
                arow.append(None)          # all 1-9 are candidates
            elif '1' <= ch <= '9':
                d = int(ch)
                row.append(d)
                arow.append({d})           # only this digit allowed
            else:
                raise ValueError(
                    f"Invalid character '{ch}' at position {i * 9 + j}")
        grid.append(row)
        allowed.append(arow)
    return grid, allowed


def parse_27x27(text: str) -> Tuple[List[List[int]],
                                      List[List[Optional[Set[int]]]]]:
    """
    Parse a 27×27 dense possibility matrix (same format as --dense output).

    Returns:
        grid           – 9x9, cells with exactly one allowed digit are
                         pre-filled; others are 0.
        allowed_digits – 9x9, set of allowed digits for each cell.
                         None means the input had no constraint for that
                         cell (equivalent to all 1-9).
    """
    chars = [ch for ch in text if ch not in _STRIP_CHARS]
    if len(chars) != 729:
        raise ValueError(
            f"Expected 729 non-whitespace characters for 27×27 format, "
            f"got {len(chars)}")

    # Interpret the 27×27 character grid
    matrix: List[List[str]] = []
    for big_r in range(27):
        row: List[str] = []
        for big_c in range(27):
            row.append(chars[big_r * 27 + big_c])
        matrix.append(row)

    # Extract per-cell allowed digit sets
    grid: List[List[int]] = []
    allowed: List[List[Optional[Set[int]]]] = []

    for orig_r in range(9):
        g_row: List[int] = []
        a_row: List[Optional[Set[int]]] = []
        for orig_c in range(9):
            digits: Set[int] = set()
            base_r = orig_r * 3
            base_c = orig_c * 3
            for dr in range(3):
                for dc in range(3):
                    ch = matrix[base_r + dr][base_c + dc]
                    if ch not in ('.', '0'):
                        try:
                            digits.add(int(ch))
                        except ValueError:
                            raise ValueError(
                                f"Invalid character '{ch}' at 27×27 position "
                                f"({base_r + dr}, {base_c + dc})")
            if not digits:
                # No digits allowed – unsolvable
                a_row.append(set())
                g_row.append(0)
            elif len(digits) == 1:
                # Exactly one digit – treat as a given
                d = next(iter(digits))
                g_row.append(d)
                a_row.append({d})
            else:
                # Multiple digits – constraint, no pre-fill
                g_row.append(0)
                a_row.append(digits)
        grid.append(g_row)
        allowed.append(a_row)
    return grid, allowed


# ---------------------------------------------------------------------------
# Core solving utilities
# ---------------------------------------------------------------------------

def _candidates(g: List[List[int]], r: int, c: int,
                allowed: Optional[Set[int]] = None) -> List[int]:
    """
    Return the list of digits that can legally be placed at (r, c).

    If *allowed* is given, the result is further restricted to that set
    (per-cell constraints from a 27×27 input).
    """
    used = [False] * 10
    # Row
    for j in range(9):
        used[g[r][j]] = True
    # Column
    for i in range(9):
        used[g[i][c]] = True
    # Box
    br, bc = (r // 3) * 3, (c // 3) * 3
    for i in range(br, br + 3):
        for j in range(bc, bc + 3):
            used[g[i][j]] = True

    cands = [d for d in range(1, 10) if not used[d]]

    if allowed is not None:
        cands = [d for d in cands if d in allowed]

    return cands


def is_solvable(grid: List[List[int]],
                allowed: Optional[List[List[Optional[Set[int]]]]] = None,
                node_limit: int = 100_000,
                limit_hits: Optional[List[int]] = None,
                ) -> bool:
    """
    Return True if the grid can be completed to at least one valid
    Sudoku solution respecting optional per-cell *allowed* constraints.
    Uses backtracking with MRV and stops at the first solution found.

    *node_limit* caps the number of recursive calls.  When the limit is
    hit the function conservatively returns **True** (assume solvable)
    and increments ``limit_hits[0]`` if provided.  This prevents the
    solver from stalling on pathological "prove impossible" searches
    while erring on the safe side (showing extra digits rather than
    missing genuine ones).
    """
    g = [row[:] for row in grid]
    empty = [(r, c) for r in range(9) for c in range(9) if g[r][c] == 0]

    if not empty:
        return True  # already complete

    nodes = [0]                                    # mutable counter

    def solve() -> bool:
        nodes[0] += 1
        if nodes[0] > node_limit:
            # Conservative: assume a solution exists
            if limit_hits is not None:
                limit_hits[0] += 1
            return True

        # Find the empty cell with the fewest candidates (MRV)
        best_r = best_c = -1
        best_cands: List[int] = []
        for r, c in empty:
            if g[r][c] == 0:
                al = allowed[r][c] if allowed else None
                cands = _candidates(g, r, c, al)
                if not cands:
                    return False  # dead end – no legal digit for this cell
                if best_r == -1 or len(cands) < len(best_cands):
                    best_r, best_c = r, c
                    best_cands = cands
                    if len(cands) == 1:
                        break  # can't do better than 1 candidate

        if best_r == -1:
            return True  # all cells filled

        for d in best_cands:
            g[best_r][best_c] = d
            if solve():
                return True
            g[best_r][best_c] = 0

        return False

    return solve()


def _count_solutions(grid: List[List[int]],
                     max_solutions: int = 500,
                     allowed: Optional[List[List[Optional[Set[int]]]]] = None
                     ) -> int:
    """
    Count complete solutions up to *max_solutions*.
    Returns the actual count (may be capped at max_solutions).
    """
    g = [row[:] for row in grid]
    empty = [(r, c) for r in range(9) for c in range(9) if g[r][c] == 0]
    count = [0]

    def mrv_order():
        """Return (r,c), candidates for the most constrained empty cell."""
        best = None
        best_cands = None
        for r, c in empty:
            if g[r][c] == 0:
                al = allowed[r][c] if allowed else None
                cands = _candidates(g, r, c, al)
                if not cands:
                    return (r, c), []
                if best is None or len(cands) < len(best_cands):
                    best = (r, c)
                    best_cands = cands
        return best, best_cands if best else (None, None)

    def backtrack(filled: int):
        if count[0] >= max_solutions:
            return

        if filled == len(empty):
            count[0] += 1
            return

        (r, c), cands = mrv_order()
        if r is None:
            return

        for d in cands:
            g[r][c] = d
            backtrack(filled + 1)
            g[r][c] = 0
            if count[0] >= max_solutions:
                return

    backtrack(0)
    return count[0]


# ---------------------------------------------------------------------------
# Progress display
# ---------------------------------------------------------------------------

def _format_duration(seconds: float) -> str:
    """Format a duration in seconds as  M:SS  or  M:SS.S."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(int(seconds), 60)
    return f"{m:d}:{s:02d}"


# ---------------------------------------------------------------------------
# Possibility discovery
# ---------------------------------------------------------------------------

def find_all_possibilities(
        grid: List[List[int]],
        max_solutions: int = 500,
        allowed: Optional[List[List[Optional[Set[int]]]]] = None,
        show_progress: bool = True,
) -> Tuple[Set[Tuple[int, int, int]], int]:
    """
    Find all digits that can appear in each cell in at least one valid
    complete solution.

    Checks every (empty-cell, candidate-digit) pair individually: place
    the digit, then test whether the resulting partial board is still
    solvable.  This finds ALL possible digit placements regardless of
    how many solutions exist.

    If *allowed* is provided it carries per-cell digit constraints (from
    a 27×27-format input).

    Returns:
        possibilities  – set of (row, col, digit) tuples
        solution_count – number of complete solutions (may hit max_solutions)
    """
    g = [row[:] for row in grid]
    possibilities: Set[Tuple[int, int, int]] = set()

    # --- Record given / single-digit cells ---
    for r in range(9):
        for c in range(9):
            if g[r][c] != 0:
                possibilities.add((r, c, g[r][c]))

    # --- Pre-count total checks for the progress bar ---
    total_checks = 0
    for r in range(9):
        for c in range(9):
            if grid[r][c] != 0:
                continue
            al = allowed[r][c] if allowed else None
            cands = _candidates(g, r, c, al)
            total_checks += len(cands)

    # --- Check each (cell, digit) pair ---
    start_time = time.time()
    completed = 0
    limit_hits: List[int] = [0]               # incremented when search limit hit
    show_bar = show_progress and sys.stderr.isatty() and total_checks > 0

    for r in range(9):
        for c in range(9):
            if grid[r][c] != 0:
                continue
            al = allowed[r][c] if allowed else None
            cands = _candidates(g, r, c, al)
            for d in cands:
                g[r][c] = d
                if is_solvable(g, allowed, limit_hits=limit_hits):
                    possibilities.add((r, c, d))
                g[r][c] = 0
                completed += 1

                # --- Progress bar update (to stderr, overwrites in place) ---
                if show_bar and completed % max(1, total_checks // 200) == 0:
                    elapsed = time.time() - start_time
                    if completed > 0:
                        eta = elapsed / completed * (total_checks - completed)
                    else:
                        eta = 0.0

                    pct = completed * 100 // total_checks
                    bar_width = 30
                    filled = bar_width * completed // total_checks
                    if filled < bar_width:
                        bar = '=' * filled + '>' + '.' * (bar_width - filled - 1)
                    else:
                        bar = '=' * bar_width

                    sys.stderr.write(
                        f"\r[{bar}] {pct:3d}% | {completed}/{total_checks} "
                        f"| {_format_duration(elapsed)} elapsed "
                        f"| {_format_duration(eta)} ETA   ")
                    sys.stderr.flush()

    # Final progress update
    if show_bar:
        elapsed = time.time() - start_time
        sys.stderr.write(
            f"\r[{'=' * 30}] 100% | {completed}/{total_checks} "
            f"| {_format_duration(elapsed)} elapsed "
            f"| 0.0s ETA   \n")
        sys.stderr.flush()

    # Warn if the search limit was ever hit (conservative fallback)
    if limit_hits[0] > 0:
        print(f"// Warning: search limit hit {limit_hits[0]} time(s) — "
              f"some digits may be shown as possible when they are not.",
              file=sys.stderr)

    # --- Count solutions for the summary report ---
    solution_count = _count_solutions(grid, max_solutions, allowed)

    return possibilities, solution_count


# ---------------------------------------------------------------------------
# 27×27 output
# ---------------------------------------------------------------------------

def build_27x27(possibilities: Set[Tuple[int, int, int]]) -> List[List[str]]:
    """
    Build a 27×27 character matrix.

    Mapping:
      output[big_r][big_c] corresponds to:
        original row    = big_r // 3
        original col    = big_c // 3
        digit           = (big_r % 3) * 3 + (big_c % 3) + 1

    The cell shows the digit if it is possible; otherwise '.'.
    """
    # Convert possibilities to a fast lookup: dict (r,c) -> set of digits
    cell_digits: Dict[Tuple[int, int], Set[int]] = {}
    for r in range(9):
        for c in range(9):
            cell_digits[(r, c)] = set()
    for r, c, d in possibilities:
        cell_digits[(r, c)].add(d)

    matrix: List[List[str]] = []
    for big_r in range(27):
        orig_r = big_r // 3
        dr = big_r % 3
        row: List[str] = []
        for big_c in range(27):
            orig_c = big_c // 3
            dc = big_c % 3
            digit = dr * 3 + dc + 1
            if digit in cell_digits[(orig_r, orig_c)]:
                row.append(str(digit))
            else:
                row.append('.')
        matrix.append(row)
    return matrix


def format_matrix(matrix: List[List[str]]) -> str:
    """
    Format the 27×27 matrix with grid separators.

    The output uses 27 characters per row (no spaces — the "dense" format),
    with ``|`` between 3×3 sub-blocks.  Horizontal separator lines
    (``---+`` for sub-bands, ``===+`` for major bands) are exactly the same
    width so the grid aligns perfectly.

    This is the canonical output format and is also accepted as input
    (grid-drawing characters are stripped when reading).
    """
    # Row width: 27 cells + 8 column separators = 35 characters.
    # Minor separator between 3-row sub-bands  (every 3 rows)
    # Major separator between 9-row bands       (every 9 rows)
    _MINOR_SEP = '---+---+---+---+---+---+---+---+---'   # 35 chars
    _MAJOR_SEP = '===+===+===+===+===+===+===+===+==='   # 35 chars

    lines: List[str] = []

    for big_r in range(27):
        if big_r > 0:
            if big_r % 9 == 0:
                lines.append(_MAJOR_SEP)
            elif big_r % 3 == 0:
                lines.append(_MINOR_SEP)

        row_parts: List[str] = []
        for big_c in range(27):
            if big_c > 0:
                if big_c % 9 == 0:
                    row_parts.append('|')
                elif big_c % 3 == 0:
                    row_parts.append('|')
            row_parts.append(matrix[big_r][big_c])

        lines.append(''.join(row_parts))

    return '\n'.join(lines)


def _all_possibilities() -> Set[Tuple[int, int, int]]:
    """Return the set of all 9×9×9 = 729 (row, col, digit) triples."""
    result: Set[Tuple[int, int, int]] = set()
    for r in range(9):
        for c in range(9):
            for d in range(1, 10):
                result.add((r, c, d))
    return result


def build_all_on_template() -> str:
    """
    Return the canonical-format 27×27 grid string for a template where
    every digit (1-9) is shown as possible in every cell — a completely
    unconstrained Sudoku.  Goes through :func:`format_matrix` so the
    template has the exact same format as normal solver output.
    """
    return format_matrix(build_27x27(_all_possibilities()))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # --template flag: write template file and exit
    if '--template' in sys.argv:
        template_path = 'template_all.txt'
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(build_all_on_template())
        print(f"// Wrote template to {template_path}", file=sys.stderr)
        return

    # Read input
    if len(sys.argv) > 1 and not sys.argv[1].startswith('--'):
        text = _read_file(sys.argv[1])
    else:
        text = sys.stdin.read()

    if not text.strip():
        print("Error: empty input.", file=sys.stderr)
        print("Provide an 81-character Sudoku string or a 27×27 grid.",
              file=sys.stderr)
        sys.exit(1)

    # Detect format by character count (after stripping whitespace + grid chars)
    chars_only = [ch for ch in text if ch not in _STRIP_CHARS]
    n_chars = len(chars_only)

    if n_chars == 81:
        try:
            grid, allowed = parse_grid(text)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        input_type = "81-character"
    elif n_chars == 729:
        try:
            grid, allowed = parse_27x27(text)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        input_type = "27×27 matrix"
    else:
        print(
            f"Error: expected 81 or 729 non-whitespace characters, "
            f"got {n_chars}.",
            file=sys.stderr)
        print("Provide either an 81-char Sudoku string (0/./1-9) or "
              "a 27×27 grid (the solver's own output format).",
              file=sys.stderr)
        sys.exit(1)

    # Quick sanity check: any cell with zero allowed digits → unsolvable
    for r in range(9):
        for c in range(9):
            if allowed[r][c] is not None and len(allowed[r][c]) == 0:
                print("Error: cell ({},{}) has no allowed digits — "
                      "puzzle is unsolvable.".format(r, c),
                      file=sys.stderr)
                sys.exit(1)

    # Check whether every non-given cell has all 9 digits allowed.
    # If so, pass allowed=None to skip unnecessary constraint filtering.
    all_unconstrained = True
    for r in range(9):
        for c in range(9):
            a = allowed[r][c]
            if a is not None and a != {1, 2, 3, 4, 5, 6, 7, 8, 9}:
                all_unconstrained = False
                break
        if not all_unconstrained:
            break
    if all_unconstrained:
        allowed = None   # no per-cell constraints needed

    # Solve
    print(f"// Input: {input_type} — solving...", file=sys.stderr)
    possibilities, count = find_all_possibilities(grid, allowed=allowed)

    if count == 0:
        print("No solution exists.", file=sys.stderr)
        sys.exit(1)

    # Build and output the 27×27 matrix (ONLY the matrix goes to stdout)
    matrix = build_27x27(possibilities)
    print(format_matrix(matrix))

    # Summary to stderr
    unique = "unique" if count == 1 else f"{count}+"
    print(f"// Found {unique} solution(s) — "
          f"{len(possibilities)} digit placements possible.",
          file=sys.stderr)


if __name__ == '__main__':
    main()
