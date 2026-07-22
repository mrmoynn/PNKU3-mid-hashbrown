#!/usr/bin/env python3
"""
Yajilin Logic Puzzle Solver
============================
Solves Yajilin puzzles — a Nikoli logic puzzle where you shade some cells
and draw a single closed loop through all remaining unshaded cells.

Rules:
  1. Shade (blacken) some cells on the grid. Shaded cells cannot share an
     edge (no orthogonal adjacency), but may touch diagonally.
  2. Draw a single continuous, non-intersecting closed loop through ALL
     remaining unshaded cells. The loop moves orthogonally from cell
     center to cell center. No branches, no dead ends.
  3. Numbered arrow clues in grey cells indicate exactly how many shaded
     cells exist in that direction (along the row or column, all the way
     to the grid edge). Clue cells are never shaded and the loop never
     passes through them.
  4. Question marks (?) in clue cells replace the number — the count is
     unknown and must be deduced. The arrow direction still applies.

Input format:
  - One line per grid row
  - Space-separated cell tokens:
      .        = empty cell (to be determined)
      Nn       = clue: N shaded cells above (north / up)
      Ns       = clue: N shaded cells below (south / down)
      Nw       = clue: N shaded cells to the left (west)
      Ne       = clue: N shaded cells to the right (east)
      ?n ?s ?w ?e = question-mark clue (unknown count, given direction)
      #        = pre-shaded cell (optional, rare in puzzles)

Output:
  - Visual grid showing the solution:
      # = shaded cell
      ═ ║ ╔ ╗ ╚ ╝ ╠ ╣ ╦ ╩ ╬ = loop segments (box-drawing)
      Number+arrow = clue cell (shown as in input)

Algorithm:
  Backtracking search with constraint propagation. Deduction rules:
    1. Black adjacency: BLACK cells force all orthogonal neighbors to be WHITE
    2. Arrow clues: count BLACK cells in arrow direction, constrain unknowns
    3. Loop degree: each WHITE cell needs exactly 2 loop connections
    4. Edge agreement: connections between adjacent WHITE cells must be mutual
    5. Connectivity: prevent premature loop closure
"""

import sys
import os
import time
from copy import deepcopy
from enum import IntEnum


# ---------------------------------------------------------------------------
# Progress tracker
# ---------------------------------------------------------------------------

class Progress:
    """Tracks search progress with periodic display."""
    def __init__(self, enabled=True, interval=2.0):
        self.enabled = enabled
        self.interval = interval      # seconds between updates
        self.nodes = 0                # backtrack calls
        self.solutions = 0            # solutions found so far
        self.start_time = time.time()
        self.last_print = self.start_time
        self.max_depth_seen = 0

    def tick(self, depth, sol_count):
        self.nodes += 1
        self.solutions = sol_count
        if depth > self.max_depth_seen:
            self.max_depth_seen = depth
        if not self.enabled:
            return
        now = time.time()
        if now - self.last_print >= self.interval:
            self._print(now, depth)

    def _print(self, now, depth):
        elapsed = now - self.start_time
        rate = self.nodes / elapsed if elapsed > 0 else 0
        if self.solutions > 0:
            sol_msg = f"  solutions: {self.solutions}"
        else:
            sol_msg = ""
        print(f"\r  nodes: {self.nodes:,}  depth: {depth}  "
              f"max_depth: {self.max_depth_seen}  "
              f"elapsed: {elapsed:.1f}s  rate: {rate:.0f} n/s{sol_msg}  ",
              end='', flush=True, file=sys.stderr)
        self.last_print = now

    def done(self):
        if not self.enabled:
            return
        elapsed = time.time() - self.start_time
        rate = self.nodes / elapsed if elapsed > 0 else 0
        print(f"\r  nodes: {self.nodes:,}  max_depth: {self.max_depth_seen}  "
              f"elapsed: {elapsed:.1f}s  rate: {rate:.0f} n/s  "
              f"solutions: {self.solutions}  "
              f"done.                    \n",
              file=sys.stderr)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class CellType(IntEnum):
    UNKNOWN = 0   # Not yet determined (will be BLACK or WHITE)
    BLACK = 1     # Shaded cell
    WHITE = 2     # Loop/path cell (part of the loop or path segment)
    CLUE = 3      # Clue cell (grey, not shaded, not in loop)
    ENDPOINT = 4  # Endpoint cell (!) — start/end of a path segment, degree 1


# Direction indices
UP = 0
DOWN = 1
LEFT = 2
RIGHT = 3

DIR_VECTORS = [(-1, 0), (1, 0), (0, -1), (0, 1)]
DIR_NAMES = ['n', 's', 'w', 'e']
OPPOSITE_DIR = [DOWN, UP, RIGHT, LEFT]

# Maximum grid size for safety
MAX_ROWS = 50
MAX_COLS = 50


# ---------------------------------------------------------------------------
# Contradiction exception — raised when propagation finds an impossible state
# ---------------------------------------------------------------------------

class Contradiction(Exception):
    """Raised when constraint propagation detects an impossible state."""
    pass


# ---------------------------------------------------------------------------
# State representation
# ---------------------------------------------------------------------------

class SolverState:
    """Encapsulates the mutable state of the puzzle during solving."""

    def __init__(self, rows, cols, clues, pre_black=None, endpoints=None,
                 v_barriers=None, h_barriers=None):
        self.rows = rows
        self.cols = cols
        self.clues = clues          # dict: (r, c) -> (num_or_None, direction)
        self.endpoints = endpoints or set()  # set of (r, c) for ! cells
        self.v_barriers = v_barriers or set()  # (r, after_col)
        self.h_barriers = h_barriers or set()  # (after_row, c)

        # cell_type[r][c]: CellType
        self.cell_type = [[CellType.UNKNOWN] * cols for _ in range(rows)]

        # Mark clue cells
        for (r, c) in clues:
            self.cell_type[r][c] = CellType.CLUE

        # Mark endpoint cells
        for (r, c) in self.endpoints:
            self.cell_type[r][c] = CellType.ENDPOINT

        # Mark pre-blackened cells
        if pre_black:
            for (r, c) in pre_black:
                self.cell_type[r][c] = CellType.BLACK

        # Edge tracking — for each cell, which directions have confirmed loop edges
        # confirmed[r][c] = set of direction indices that are confirmed connections
        self.confirmed = [[set() for _ in range(cols)] for _ in range(rows)]

        # blocked[r][c] = set of direction indices that CANNOT be loop connections
        self.blocked = [[set() for _ in range(cols)] for _ in range(rows)]

        # Pre-block edges for BLACK and CLUE cells
        for r in range(rows):
            for c in range(cols):
                if self.cell_type[r][c] in (CellType.BLACK, CellType.CLUE):
                    self.blocked[r][c] = {UP, DOWN, LEFT, RIGHT}

    def copy(self):
        """Deep copy this state for backtracking."""
        new = SolverState.__new__(SolverState)
        new.rows = self.rows
        new.cols = self.cols
        new.clues = self.clues  # immutable, no need to copy
        new.endpoints = self.endpoints  # immutable
        new.v_barriers = self.v_barriers  # immutable
        new.h_barriers = self.h_barriers  # immutable
        new.cell_type = [row[:] for row in self.cell_type]
        new.confirmed = [[set(s) for s in row] for row in self.confirmed]
        new.blocked = [[set(s) for s in row] for row in self.blocked]
        return new

    def cells_in_arrow_direction(self, r, c, direction):
        """Yield cells in the arrow direction, stopping at barriers.
        v_barriers: (r, after_col) = barrier between col and col+1 in row r.
        h_barriers: (after_row, c) = barrier between row and row+1 in col c."""
        dr, dc = DIR_VECTORS[direction]
        cr, cc = r + dr, c + dc
        while self.in_bounds(cr, cc):
            yield (cr, cc)
            # Check for barrier between this cell and the next one
            if direction == RIGHT:
                # barrier between cc and cc+1 is at (cr, cc)
                if (cr, cc) in self.v_barriers:
                    break
            elif direction == LEFT:
                # barrier between cc-1 and cc is at (cr, cc-1)
                if (cr, cc - 1) in self.v_barriers:
                    break
            elif direction == DOWN:
                # barrier between cr and cr+1 is at (cr, cc)
                if (cr, cc) in self.h_barriers:
                    break
            elif direction == UP:
                # barrier between cr-1 and cr is at (cr-1, cc)
                if (cr - 1, cc) in self.h_barriers:
                    break
            cr += dr
            cc += dc

    def in_bounds(self, r, c):
        return 0 <= r < self.rows and 0 <= c < self.cols

    def neighbor(self, r, c, d):
        """Return (nr, nc) of neighbor in direction d, or None if out of bounds."""
        dr, dc = DIR_VECTORS[d]
        nr, nc = r + dr, c + dc
        if self.in_bounds(nr, nc):
            return (nr, nc)
        return None

    def can_be_path(self, r, c):
        """Cell could be part of the path/loop (WHITE, ENDPOINT, or UNKNOWN)."""
        return self.cell_type[r][c] in (CellType.WHITE, CellType.ENDPOINT, CellType.UNKNOWN)

    def is_path_cell(self, r, c):
        """Cell is confirmed to be part of the path/loop (WHITE or ENDPOINT)."""
        return self.cell_type[r][c] in (CellType.WHITE, CellType.ENDPOINT)

    def is_white(self, r, c):
        return self.cell_type[r][c] == CellType.WHITE

    def is_endpoint(self, r, c):
        return self.cell_type[r][c] == CellType.ENDPOINT

    def is_black(self, r, c):
        return self.cell_type[r][c] == CellType.BLACK

    def is_clue(self, r, c):
        return self.cell_type[r][c] == CellType.CLUE

    def required_degree(self, r, c):
        """Return (min, max) connections this cell must have in the solution.
        ENDPOINT cells: 0–2 (segment endpoints have degree 1, pass-throughs
        have degree 2, unused endpoints have degree 0).
        WHITE cells: exactly 2 (intermediate path cells)."""
        ct = self.cell_type[r][c]
        if ct == CellType.WHITE:
            return (2, 2)
        elif ct == CellType.ENDPOINT:
            return (0, 2)
        else:
            return (0, 0)  # BLACK, CLUE, UNKNOWN

    def available_edges(self, r, c):
        """Return set of directions that could still become loop edges."""
        if self.cell_type[r][c] in (CellType.BLACK, CellType.CLUE):
            return set()
        all_dirs = {UP, DOWN, LEFT, RIGHT}
        return all_dirs - self.confirmed[r][c] - self.blocked[r][c]

    def total_possible_edges(self, r, c):
        """Total number of edges that are or could be loop connections."""
        return len(self.confirmed[r][c]) + len(self.available_edges(r, c))

    def all_path_cells(self):
        """Yield (r, c) of all confirmed WHITE and ENDPOINT cells."""
        for r in range(self.rows):
            for c in range(self.cols):
                if self.is_path_cell(r, c):
                    yield (r, c)


# ---------------------------------------------------------------------------
# Constraint propagation
# ---------------------------------------------------------------------------

def propagate(state, verbose=False):
    """
    Apply deduction rules repeatedly until fixed point.
    Raises Contradiction if an impossible state is detected.
    Returns True if any changes were made, False if no more deductions possible.
    """
    changed_overall = False

    while True:
        changed = False

        # --- Rule 1: BLACK adjacency ---
        # If a cell is BLACK (or ENDPOINT with no possible edges), all
        # orthogonal neighbors must be WHITE.
        for r in range(state.rows):
            for c in range(state.cols):
                if state.cell_type[r][c] == CellType.BLACK:
                    for d in range(4):
                        nb = state.neighbor(r, c, d)
                        if nb is None:
                            continue
                        nr, nc = nb
                        if state.cell_type[nr][nc] == CellType.BLACK:
                            raise Contradiction(
                                f"Adjacent BLACK cells at ({r},{c}) and ({nr},{nc})"
                            )
                        if state.is_endpoint(nr, nc) and state.total_possible_edges(nr, nc) == 0:
                            raise Contradiction(
                                f"Adjacent BLACK/shaded cells at ({r},{c}) and ({nr},{nc})"
                            )
                        if state.cell_type[nr][nc] == CellType.UNKNOWN:
                            if verbose:
                                print(f"  Rule 1: ({nr},{nc}) → WHITE (adjacent to BLACK {r},{c})")
                            state.cell_type[nr][nc] = CellType.WHITE
                            changed = True

        # --- Rule 2: Arrow clues ---
        # A clue (r, c) with number N and direction d means exactly N BLACK cells
        # in that direction from (r, c) until a barrier or the grid edge.
        # Question-mark clues (clue_num=None, clue_dir=None) have no direction
        # and impose no counting constraint — skip them.
        for (r, c), (clue_num, clue_dir) in state.clues.items():
            if clue_dir is None:
                continue  # ? clue: no direction, no constraint
            # Collect cells in the arrow direction (stops at barriers)
            cells_in_dir = list(state.cells_in_arrow_direction(r, c, clue_dir))

            black_count = sum(1 for (rr, cc) in cells_in_dir
                              if state.cell_type[rr][cc] == CellType.BLACK
                              or (state.is_endpoint(rr, cc)
                                  and state.total_possible_edges(rr, cc) == 0))
            unknown_count = sum(1 for (rr, cc) in cells_in_dir
                                if state.cell_type[rr][cc] == CellType.UNKNOWN)
            white_count = sum(1 for (rr, cc) in cells_in_dir
                              if state.cell_type[rr][cc] in (CellType.WHITE, CellType.CLUE)
                              or (state.is_endpoint(rr, cc)
                                  and state.total_possible_edges(rr, cc) > 0))

            # Known number clue
            if black_count > clue_num:
                raise Contradiction(
                    f"Clue at ({r},{c}) expects {clue_num} blacks in "
                    f"dir {DIR_NAMES[clue_dir]}, but found {black_count}"
                )
            # If exactly reached, all remaining unknowns must be WHITE
            if black_count == clue_num:
                for (rr, cc) in cells_in_dir:
                    if state.cell_type[rr][cc] == CellType.UNKNOWN:
                        if verbose:
                            print(f"  Rule 2a: ({rr},{cc}) → WHITE "
                                  f"(clue {r},{c} already has {clue_num} blacks)")
                        state.cell_type[rr][cc] = CellType.WHITE
                        changed = True
            # If unknowns must all be BLACK to reach the number
            if black_count + unknown_count == clue_num:
                for (rr, cc) in cells_in_dir:
                    if state.cell_type[rr][cc] == CellType.UNKNOWN:
                        if verbose:
                            print(f"  Rule 2b: ({rr},{cc}) → BLACK "
                                  f"(clue {r},{c} needs {clue_num} blacks)")
                        state.cell_type[rr][cc] = CellType.BLACK
                        changed = True

        # --- Rule 3: Update edge availability ---
        # For each cell, edges to BLACK or CLUE neighbors are blocked.
        # Also edges that go out of bounds.
        for r in range(state.rows):
            for c in range(state.cols):
                if not state.can_be_path(r, c):
                    continue

                for d in range(4):
                    if d in state.blocked[r][c]:
                        continue
                    nb = state.neighbor(r, c, d)
                    if nb is None:
                        # Edge of grid — block
                        state.blocked[r][c].add(d)
                        changed = True
                        continue
                    nr, nc = nb
                    if state.cell_type[nr][nc] in (CellType.BLACK, CellType.CLUE):
                        # Can't connect to BLACK or CLUE
                        state.blocked[r][c].add(d)
                        changed = True

        # --- Rule 4: Path degree constraints ---
        # WHITE needs exactly 2; ENDPOINT needs 1–2 (at least 1, at most 2).
        for r in range(state.rows):
            for c in range(state.cols):
                if not state.is_path_cell(r, c):
                    continue

                need_min, need_max = state.required_degree(r, c)
                available = state.available_edges(r, c)
                n_confirmed = len(state.confirmed[r][c])
                n_available = len(available)
                total_possible = n_confirmed + n_available

                # Must have at least `need_min` total connections
                if total_possible < need_min:
                    raise Contradiction(
                        f"Path cell ({r},{c}) has only {total_possible} "
                        f"possible edges (need at least {need_min})"
                    )

                # If only `need_min` possible, confirm them all
                if n_confirmed < need_min and total_possible == need_min:
                    for d in list(available):
                        if verbose:
                            print(f"  Rule 4a: ({r},{c}) edge {DIR_NAMES[d]} → CONFIRMED "
                                  f"(only {total_possible} possible, need ≥{need_min})")
                        state.confirmed[r][c].add(d)
                        changed = True

                # If already at max, block all remaining
                if n_confirmed == need_max and n_available > 0:
                    for d in list(available):
                        state.blocked[r][c].add(d)
                        changed = True

        # --- Rule 5: Edge agreement (symmetry) ---
        # If cell A confirms connection to cell B, cell B must also confirm
        # connection to cell A (and vice versa).
        for r in range(state.rows):
            for c in range(state.cols):
                if not state.is_path_cell(r, c):
                    continue
                for d in list(state.confirmed[r][c]):
                    nb = state.neighbor(r, c, d)
                    if nb is None:
                        raise Contradiction(
                            f"Confirmed edge from ({r},{c}) goes out of bounds (dir {DIR_NAMES[d]})"
                        )
                    nr, nc = nb
                    op = OPPOSITE_DIR[d]

                    # Neighbor must be able to be part of path
                    if not state.can_be_path(nr, nc):
                        raise Contradiction(
                            f"Confirmed edge from path cell ({r},{c}) to non-path ({nr},{nc})"
                        )

                    # If neighbor is a path cell, ensure reciprocal connection
                    if state.is_path_cell(nr, nc):
                        if op in state.blocked[nr][nc]:
                            raise Contradiction(
                                f"Edge ({r},{c})→({nr},{nc}) confirmed but "
                                f"({nr},{nc}) blocks the reverse edge"
                            )
                        if op not in state.confirmed[nr][nc]:
                            state.confirmed[nr][nc].add(op)
                            if verbose:
                                print(f"  Rule 5: ({nr},{nc}) edge {DIR_NAMES[op]} → CONFIRMED "
                                      f"(reciprocal to ({r},{c}))")
                            changed = True

                    # If neighbor is UNKNOWN, make it WHITE (it's connected to path)
                    if state.cell_type[nr][nc] == CellType.UNKNOWN:
                        if verbose:
                            print(f"  Rule 5b: ({nr},{nc}) → WHITE "
                                  f"(connected to path from ({r},{c}))")
                        state.cell_type[nr][nc] = CellType.WHITE
                        changed = True

        # --- Rule 6: Block propagation ---
        # If cell A blocks connection to cell B, cell B cannot connect to A either.
        for r in range(state.rows):
            for c in range(state.cols):
                if not state.can_be_path(r, c):
                    continue
                for d in list(state.blocked[r][c]):
                    nb = state.neighbor(r, c, d)
                    if nb is None:
                        continue
                    nr, nc = nb
                    if state.can_be_path(nr, nc):
                        op = OPPOSITE_DIR[d]
                        if op not in state.blocked[nr][nc]:
                            state.blocked[nr][nc].add(op)
                            if verbose:
                                print(f"  Rule 6: ({nr},{nc}) edge {DIR_NAMES[op]} → BLOCKED "
                                      f"(reciprocal to ({r},{c}) block)")
                            changed = True

        # --- Rule 7: Forced connections ---
        # If a path cell is one short of its minimum degree and only 1 edge
        # is available, that edge must be confirmed.
        for r in range(state.rows):
            for c in range(state.cols):
                if not state.is_path_cell(r, c):
                    continue
                need_min, need_max = state.required_degree(r, c)
                n_confirmed = len(state.confirmed[r][c])
                if need_min > 0 and n_confirmed == need_min - 1:
                    available = state.available_edges(r, c)
                    if len(available) == 1:
                        d = next(iter(available))
                        state.confirmed[r][c].add(d)
                        if verbose:
                            print(f"  Rule 7: ({r},{c}) edge {DIR_NAMES[d]} → CONFIRMED "
                                  f"(forced: 1 short of min {need_min})")
                        changed = True

        # --- Rule 8: Connectivity — prevent premature component closure ---
        # Build union-find over all path cells (WHITE + ENDPOINT) connected
        # by confirmed edges. If a component is "closed" (all cells at their
        # required degree) but doesn't include all path cells, it's a
        # contradiction — no more edges can join it.
        parent = {}
        comp_size = {}

        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x, y):
            rx, ry = find(x), find(y)
            if rx != ry:
                if comp_size[rx] < comp_size[ry]:
                    rx, ry = ry, rx
                parent[ry] = rx
                comp_size[rx] += comp_size[ry]

        # Initialize union-find with all path cells
        path_cells = list(state.all_path_cells())
        for cell in path_cells:
            parent[cell] = cell
            comp_size[cell] = 1

        # Union cells connected by confirmed edges
        for (rr, cc) in path_cells:
            for d in state.confirmed[rr][cc]:
                nb = state.neighbor(rr, cc, d)
                if nb is None:
                    continue
                nr, nc = nb
                if state.is_path_cell(nr, nc) and (nr, nc) in parent:
                    union((rr, cc), (nr, nc))

        # Check for premature component closure:
        # If a component has ALL cells at their required degree,
        # it is "closed" — nothing else can connect to it.
        # If there are still path cells outside this closed component,
        # it's a contradiction.
        total_path = len(path_cells)
        if total_path > 0:
            comps = {}
            for cell in path_cells:
                root = find(cell)
                if root not in comps:
                    comps[root] = []
                comps[root].append(cell)

            for root, members in comps.items():
                comp_total = len(members)
                if comp_total < total_path:
                    # Check if ALL members have reached their max degree (closed)
                    all_satisfied = all(
                        len(state.confirmed[rr][cc]) == state.required_degree(rr, cc)[1]
                        for (rr, cc) in members
                    )
                    if all_satisfied:
                        # Count endpoints in this component
                        ep_count = sum(1 for (rr, cc) in members
                                       if state.is_endpoint(rr, cc))
                        raise Contradiction(
                            f"Premature component closure: {comp_total} path cells "
                            f"(with {ep_count} endpoints) are closed but "
                            f"{total_path} total path cells exist"
                        )

        # --- Rule 9: Unused ENDPOINT cells become BLACK ---
        # An ENDPOINT with no possible edges (all blocked) cannot be part
        # of any segment — it must be shaded.
        for r in range(state.rows):
            for c in range(state.cols):
                if not state.is_endpoint(r, c):
                    continue
                if state.total_possible_edges(r, c) == 0:
                    if verbose:
                        print(f"  Rule 9: ({r},{c}) ENDPOINT → BLACK (no possible edges)")
                    state.cell_type[r][c] = CellType.BLACK
                    state.blocked[r][c] = {UP, DOWN, LEFT, RIGHT}
                    changed = True

        if not changed:
            break
        changed_overall = True

    return changed_overall


# ---------------------------------------------------------------------------
# Solution verification
# ---------------------------------------------------------------------------

def verify_solution(state):
    """
    Verify that the current state is a valid complete solution.
    Returns (is_valid, message).
    """
    # Build effective-BLACK set: actual BLACK cells + degree-0 ENDPOINT cells.
    # An ENDPOINT with no connections is effectively shaded.
    def is_effective_black(r, c):
        ct = state.cell_type[r][c]
        if ct == CellType.BLACK:
            return True
        if ct == CellType.ENDPOINT and len(state.confirmed[r][c]) == 0:
            return True
        return False

    # Check 1: No UNKNOWN cells remain
    for r in range(state.rows):
        for c in range(state.cols):
            if state.cell_type[r][c] == CellType.UNKNOWN:
                return False, f"Cell ({r},{c}) is still UNKNOWN"

    # Check 2: No adjacent effective-BLACK cells
    for r in range(state.rows):
        for c in range(state.cols):
            if is_effective_black(r, c):
                for d in range(4):
                    nb = state.neighbor(r, c, d)
                    if nb:
                        nr, nc = nb
                        if is_effective_black(nr, nc):
                            return False, (
                                f"Adjacent shaded cells at ({r},{c}) and ({nr},{nc})"
                            )

    # Check 3: Arrow clues satisfied (counting stops at barriers).
    # Degree-0 ENDPOINT cells count as shaded.
    for (r, c), (clue_num, clue_dir) in state.clues.items():
        if clue_dir is None:
            continue  # ? clue: no direction to check
        black_count = 0
        for (cr, cc) in state.cells_in_arrow_direction(r, c, clue_dir):
            if is_effective_black(cr, cc):
                black_count += 1
        if black_count != clue_num:
            return False, (
                f"Clue at ({r},{c}) expects {clue_num} blacks in "
                f"dir {DIR_NAMES[clue_dir]}, but found {black_count}"
            )

    # Check 4: Every path cell has its required degree.
    # WHITE must have degree 2. ENDPOINT may have degree 0, 1, or 2.
    # Every degree-1 cell MUST be an ENDPOINT (no dead ends at non-! cells).
    path_cells = list(state.all_path_cells())
    has_endpoints = any(state.is_endpoint(r, c) for (r, c) in path_cells)

    for (r, c) in path_cells:
        need_min, need_max = state.required_degree(r, c)
        actual = len(state.confirmed[r][c])
        if actual < need_min or actual > need_max:
            cell_type = "ENDPOINT" if state.is_endpoint(r, c) else "WHITE"
            return False, (
                f"{cell_type} cell ({r},{c}) has {actual} "
                f"connections (need {need_min}–{need_max})"
            )
        # Degree-1 cells must be at ! positions
        if actual == 1 and not state.is_endpoint(r, c):
            return False, (
                f"WHITE cell ({r},{c}) has degree 1 — segments may only "
                f"end at ! cells"
            )

    # Check 5: Connectivity — ignore isolated cells (degree 0).
    # Connected components with edges must form valid segments.
    active_cells = [(r, c) for (r, c) in path_cells
                    if len(state.confirmed[r][c]) > 0]
    if active_cells:
        graph = {cell: set() for cell in active_cells}
        for (r, c) in active_cells:
            for d in state.confirmed[r][c]:
                nb = state.neighbor(r, c, d)
                if nb and state.is_path_cell(nb[0], nb[1]):
                    graph[(r, c)].add(nb)

        unvisited = set(active_cells)
        while unvisited:
            start = unvisited.pop()
            queue = [start]
            comp = []
            while queue:
                cell = queue.pop(0)
                comp.append(cell)
                for nb in graph[cell]:
                    if nb in unvisited:
                        unvisited.remove(nb)
                        queue.append(nb)

            # Count degree-1 cells in this component
            deg1_cells = [(r, c) for (r, c) in comp
                          if len(state.confirmed[r][c]) == 1]
            deg1_endpoints = [(r, c) for (r, c) in deg1_cells
                              if state.is_endpoint(r, c)]
            deg1_non_endpoints = [(r, c) for (r, c) in deg1_cells
                                  if not state.is_endpoint(r, c)]

            if deg1_non_endpoints:
                return False, (
                    f"Component has {len(deg1_non_endpoints)} degree-1 "
                    f"non-! cell(s): {deg1_non_endpoints}"
                )

            if has_endpoints:
                # In path mode, each connected component must be a simple
                # path with exactly 2 degree-1 endpoints (both at ! cells),
                # or a closed cycle (0 degree-1 cells) which is also fine.
                if len(deg1_cells) not in (0, 2):
                    return False, (
                        f"Component with {len(comp)} cells has "
                        f"{len(deg1_cells)} endpoint(s) — expected 0 or 2"
                    )
            else:
                # Loop mode: no degree-1 cells allowed (closed cycle)
                if len(deg1_cells) != 0:
                    return False, (
                        f"Loop mode: component has {len(deg1_cells)} "
                        f"degree-1 cell(s) — expected 0 (closed cycle)"
                    )

    return True, "Valid solution"


# ---------------------------------------------------------------------------
# Backtracking search
# ---------------------------------------------------------------------------

def find_branch_cell(state):
    """
    Find the most constrained undecided cell or endpoint edge to branch on.
    Returns ('cell', r, c), ('endpoint_edge', r, c, d), or None.

    ENDPOINT cells with exactly 1 available edge are treated as branch
    points: either confirm the edge (degree 1) or block it (degree 0).
    This ensures the solver considers both pure-cycle and segment solutions.
    """
    best = None
    best_score = float('inf')

    # --- UNKNOWN cells: branch BLACK vs WHITE ---
    for r in range(state.rows):
        for c in range(state.cols):
            if state.cell_type[r][c] != CellType.UNKNOWN:
                continue

            # Count how many arrow clues constrain this cell
            arrow_constraints = 0
            for (cr, cc), (clue_num, clue_dir) in state.clues.items():
                if clue_dir is None:
                    continue
                dr, dc = DIR_VECTORS[clue_dir]
                if dr != 0:
                    if c == cc and (r - cr) * dr > 0:
                        arrow_constraints += 1
                if dc != 0:
                    if r == cr and (c - cc) * dc > 0:
                        arrow_constraints += 1

            has_black_neighbor = False
            for d in range(4):
                nb = state.neighbor(r, c, d)
                if nb and state.is_black(nb[0], nb[1]):
                    has_black_neighbor = True
                    break

            options = 1 if has_black_neighbor else 2
            score = options * 100 - arrow_constraints * 10
            edge_distance = min(r, state.rows - 1 - r, c, state.cols - 1 - c)
            score -= edge_distance

            if score < best_score:
                best_score = score
                best = ('cell', r, c)

    # --- ENDPOINT cells with 1 available edge: branch confirm vs block ---
    # Score 50 = higher priority than UNKNOWN cells (which score >= ~80)
    for r in range(state.rows):
        for c in range(state.cols):
            if not state.is_endpoint(r, c):
                continue
            need_min, need_max = state.required_degree(r, c)
            n_confirmed = len(state.confirmed[r][c])
            if n_confirmed >= need_max:
                continue
            available = state.available_edges(r, c)
            if len(available) != 1:
                continue  # only branch when exactly 1 edge is available
            d = next(iter(available))
            # Verify neighbor can accept the connection
            nb = state.neighbor(r, c, d)
            if nb and state.can_be_path(nb[0], nb[1]):
                score = 50  # high priority
                if score < best_score:
                    best_score = score
                    best = ('endpoint_edge', r, c, d)

    return best


def find_branch_edge(state):
    """
    Find a path cell (WHITE or ENDPOINT) with ambiguous edges to branch on.
    Returns (r, c, direction) or None if all path cells have determined edges.

    This is used when all UNKNOWN cells are resolved but edge choices remain.
    """
    best = None
    best_score = float('inf')

    for r in range(state.rows):
        for c in range(state.cols):
            if not state.is_path_cell(r, c):
                continue
            need_min, need_max = state.required_degree(r, c)
            if len(state.confirmed[r][c]) >= need_max:
                continue

            available = state.available_edges(r, c)
            if not available:
                continue

            # Score: prefer cells with fewer available edges
            score = len(available)
            if score < best_score:
                best_score = score
                # Pick the first available edge
                best = (r, c, next(iter(available)))

    return best


def backtrack(state, depth=0, max_depth=10000, verbose=False,
              max_solutions=1, solutions=None, _solution_signatures=None,
              progress=None):
    """
    Recursive backtracking search.

    Args:
        state: Current solver state
        depth: Current search depth
        max_depth: Maximum backtracking depth
        verbose: Print progress
        max_solutions: Stop after finding this many solutions (default 1)
        solutions: Output list to collect solution states
        _solution_signatures: Set of solution hashes to detect duplicates
        progress: Progress tracker instance

    Returns:
        The solved state (if max_solutions=1), or None.
        When max_solutions > 1, solutions are collected in the `solutions` list.
    """
    if solutions is None:
        solutions = []
    if _solution_signatures is None:
        _solution_signatures = set()
    if progress is None:
        progress = Progress(enabled=False)

    if depth > max_depth:
        return None

    progress.tick(depth, len(solutions))

    # Run propagation
    try:
        propagate(state, verbose=False)
    except Contradiction:
        return None

    # Check if solved
    is_valid, msg = verify_solution(state)
    if is_valid:
        # Create a signature for this solution to detect duplicates
        sig = _solution_signature(state)
        if sig not in _solution_signatures:
            _solution_signatures.add(sig)
            solutions.append(state.copy())
        if len(solutions) >= max_solutions:
            return solutions[0] if max_solutions == 1 else None
        # Continue searching for more solutions
        if max_solutions > 1:
            return None

    # Find branch point: cells first, then endpoint edges, then other edges
    branch = find_branch_cell(state)

    if branch is not None:
        btype = branch[0]

        if btype == 'cell':
            _, r, c = branch

            # Option 1: Try BLACK
            if verbose and depth < 3:
                print(f"  [depth {depth}] Trying ({r},{c}) = BLACK")
            state_black = state.copy()
            state_black.cell_type[r][c] = CellType.BLACK
            try:
                propagate(state_black, verbose=False)
                result = backtrack(state_black, depth + 1, max_depth, verbose,
                                  max_solutions, solutions, _solution_signatures,
                                  progress)
                if result is not None and max_solutions == 1:
                    return result
            except Contradiction:
                pass

            if max_solutions > 1 and len(solutions) >= max_solutions:
                return None

            # Option 2: Try WHITE
            if verbose and depth < 3:
                print(f"  [depth {depth}] Trying ({r},{c}) = WHITE")
            state_white = state.copy()
            state_white.cell_type[r][c] = CellType.WHITE
            try:
                propagate(state_white, verbose=False)
                result = backtrack(state_white, depth + 1, max_depth, verbose,
                                  max_solutions, solutions, _solution_signatures,
                                  progress)
                if result is not None and max_solutions == 1:
                    return result
            except Contradiction:
                pass

            if max_solutions > 1 and len(solutions) >= max_solutions:
                return None

            return None

        elif btype == 'endpoint_edge':
            _, r, c, d = branch

            # Option 1: Block the edge → ENDPOINT degree 0 (unused/shaded)
            if verbose and depth < 3:
                print(f"  [depth {depth}] ENDPOINT ({r},{c}) edge "
                      f"{DIR_NAMES[d]} = BLOCKED (→ degree 0)")
            state_block = state.copy()
            state_block.blocked[r][c].add(d)
            try:
                propagate(state_block, verbose=False)
                result = backtrack(state_block, depth + 1, max_depth, verbose,
                                  max_solutions, solutions, _solution_signatures,
                                  progress)
                if result is not None and max_solutions == 1:
                    return result
            except Contradiction:
                pass

            if max_solutions > 1 and len(solutions) >= max_solutions:
                return None

            # Option 2: Confirm the edge → ENDPOINT degree 1 (segment endpoint)
            if verbose and depth < 3:
                print(f"  [depth {depth}] ENDPOINT ({r},{c}) edge "
                      f"{DIR_NAMES[d]} = CONFIRMED (→ degree 1)")
            state_conf = state.copy()
            state_conf.confirmed[r][c].add(d)
            try:
                propagate(state_conf, verbose=False)
                result = backtrack(state_conf, depth + 1, max_depth, verbose,
                                  max_solutions, solutions, _solution_signatures,
                                  progress)
                if result is not None and max_solutions == 1:
                    return result
            except Contradiction:
                pass

            if max_solutions > 1 and len(solutions) >= max_solutions:
                return None

            return None

    # No cell/endpoint decisions left — try edge decisions on WHITE cells
    branch_edge = find_branch_edge(state)
    if branch_edge is not None:
        r, c, d = branch_edge

        # Option 1: Confirm this edge
        if verbose and depth < 3:
            print(f"  [depth {depth}] Trying edge ({r},{c}) {DIR_NAMES[d]} = CONFIRMED")
        state_conf = state.copy()
        state_conf.confirmed[r][c].add(d)
        try:
            propagate(state_conf, verbose=False)
            result = backtrack(state_conf, depth + 1, max_depth, verbose,
                              max_solutions, solutions, _solution_signatures,
                              progress)
            if result is not None and max_solutions == 1:
                return result
        except Contradiction:
            pass

        if max_solutions > 1 and len(solutions) >= max_solutions:
            return None

        # Option 2: Block this edge
        if verbose and depth < 3:
            print(f"  [depth {depth}] Trying edge ({r},{c}) {DIR_NAMES[d]} = BLOCKED")
        state_block = state.copy()
        state_block.blocked[r][c].add(d)
        try:
            propagate(state_block, verbose=False)
            result = backtrack(state_block, depth + 1, max_depth, verbose,
                              max_solutions, solutions, _solution_signatures,
                              progress)
            if result is not None and max_solutions == 1:
                return result
        except Contradiction:
            pass

        if max_solutions > 1 and len(solutions) >= max_solutions:
            return None

        return None

    # No branch points but not solved — should not happen
    return None


def _solution_signature(state):
    """Create a hashable signature for a solution to detect duplicates."""
    # Tuple of (cell_type, tuple(sorted(confirmed_edges))) for each cell
    sig = []
    for r in range(state.rows):
        for c in range(state.cols):
            ct = state.cell_type[r][c]
            if ct in (CellType.WHITE, CellType.ENDPOINT):
                edges = tuple(sorted(state.confirmed[r][c]))
                sig.append((int(ct), edges))
            else:
                sig.append((int(ct), ()))
    return tuple(sig)


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def display_solution(state):
    """
    Render the solved grid as a string using box-drawing characters
    for the loop and # for shaded cells.
    """
    rows, cols = state.rows, state.cols
    lines = []

    for r in range(rows):
        row_chars = []
        for c in range(cols):
            ct = state.cell_type[r][c]

            if ct == CellType.ENDPOINT:
                conn = state.confirmed[r][c]
                if len(conn) == 0:
                    row_chars.append(' # ')  # unused → shaded
                    continue
                elif len(conn) == 1:
                    d = next(iter(conn))
                    markers = {UP: '!↑', DOWN: '!↓', LEFT: '!←', RIGHT: '!→'}
                    token = markers.get(d, '! ')
                    row_chars.append(token.ljust(3))
                    continue
                # degree 2: fall through to WHITE rendering below

            if ct == CellType.CLUE:
                clue_num, clue_dir = state.clues.get((r, c), ('?', None))
                if clue_dir is None:
                    token = '?'  # question-mark: no direction
                else:
                    token = f"{clue_num}{DIR_NAMES[clue_dir]}"
                row_chars.append(token.ljust(3))
                continue

            if ct == CellType.BLACK:
                row_chars.append(' # ')
                continue

            if ct == CellType.WHITE or ct == CellType.ENDPOINT:
                # WHITE cell, or ENDPOINT with degree 2 (pass-through) —
                # render with ordinary corner/line symbols.
                conn = state.confirmed[r][c]
                up = UP in conn
                down = DOWN in conn
                left = LEFT in conn
                right = RIGHT in conn

                # Map to box-drawing character (all 3 chars wide)
                if up and down and not left and not right:
                    ch = ' ║ '
                elif left and right and not up and not down:
                    ch = '═══'
                elif up and right and not down and not left:
                    ch = ' ╚ '
                elif up and left and not down and not right:
                    ch = ' ╝ '
                elif down and right and not up and not left:
                    ch = ' ╔ '
                elif down and left and not up and not right:
                    ch = ' ╗ '
                elif len(conn) == 0:
                    ch = ' ○ '  # isolated WHITE cell (shouldn't happen in valid solution)
                elif len(conn) == 1:
                    # Dead end (shouldn't happen)
                    d = next(iter(conn))
                    markers = {UP: ' ╨ ', DOWN: ' ╥ ', LEFT: ' ╡ ', RIGHT: ' ╞ '}
                    ch = markers.get(d, ' ? ')
                else:
                    ch = ' + '
                row_chars.append(ch)
                continue

            if ct == CellType.UNKNOWN:
                row_chars.append(' . ')
                continue

        lines.append(''.join(row_chars))

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_grid(text):
    """
    Parse a Yajilin puzzle from text.

    Format:
      - One line per grid row
      - Spaces are optional (stripped before parsing)
      - Each cell is represented as:
          .              = empty cell (1 char)
          ?              = question-mark cell (1 char)
          !              = endpoint cell (1 char)
          #              = pre-shaded cell (1 char)
          Nn / Ns / Nw / Ne = numbered clue (2+ chars: digits + direction)
      - Barriers:
          |              = vertical barrier between cells in a row
          -- (whole row) = horizontal barrier between rows (line of dashes)
      - Barriers only affect arrow counting (stop at barrier).
        The loop can pass through them freely.

    Returns (rows, cols, clues, pre_black, endpoints,
             v_barriers, h_barriers).
      v_barriers: set of (r, after_col) — barrier in row r between
                  columns after_col and after_col+1.
      h_barriers: set of (after_row, c) — barrier in column c between
                  rows after_row and after_row+1.
    """
    raw_lines = [line.rstrip('\n\r') for line in text.split('\n')]
    raw_lines = [l for l in raw_lines if l.strip() and not l.strip().startswith('#')]

    if not raw_lines:
        raise ValueError("Empty input")

    dir_map = {'n': UP, 's': DOWN, 'w': LEFT, 'e': RIGHT}

    # --- First pass: separate barrier rows from data rows ---
    h_barrier_after_rows = set()  # row indices after which a -- barrier sits
    data_lines = []
    data_row_idx = 0
    for line in raw_lines:
        stripped = line.replace(' ', '')
        # A line consisting only of dashes is a horizontal barrier
        if len(stripped) > 0 and all(c == '-' for c in stripped):
            # Barrier between the previous data row and the next one
            if data_row_idx > 0:
                h_barrier_after_rows.add(data_row_idx - 1)
        else:
            data_lines.append(line)
            data_row_idx += 1

    # --- Second pass: parse data lines character-by-character ---
    parsed_rows = []
    v_barriers = set()  # (r, after_col)

    for r, line in enumerate(data_lines):
        chars = line.replace(' ', '')
        row_cells = []
        i = 0
        while i < len(chars):
            c = chars[i]
            if c == '|':
                # Vertical barrier between previous cell and next cell
                v_barriers.add((r, len(row_cells) - 1))
                i += 1
            elif c == '.':
                row_cells.append(None)  # empty cell
                i += 1
            elif c == '?':
                row_cells.append(('?', None, None))  # question-mark clue
                i += 1
            elif c == '!':
                row_cells.append(('!',))  # endpoint cell
                i += 1
            elif c == '#':
                row_cells.append(('#',))  # pre-shaded cell
                i += 1
            elif c == '-':
                # Inline -- barrier between cells
                if i + 1 < len(chars) and chars[i + 1] == '-':
                    v_barriers.add((r, len(row_cells) - 1))
                    i += 2
                else:
                    raise ValueError(
                        f"Unexpected '-' at position {i} in row "
                        f"\"{line}\" (use -- for inline barrier)"
                    )
            elif c.isdigit():
                # Read all consecutive digits
                j = i
                while j < len(chars) and chars[j].isdigit():
                    j += 1
                num_str = chars[i:j]
                if j >= len(chars) or chars[j] not in 'nswe':
                    raise ValueError(
                        f"Invalid clue at position {i} in row "
                        f"\"{line}\": expected direction after '{num_str}'"
                    )
                dir_char = chars[j]
                num = int(num_str)
                row_cells.append(('clue', num, dir_map[dir_char]))
                i = j + 1
            else:
                raise ValueError(
                    f"Unexpected character '{c}' at position {i} in row "
                    f"\"{line}\" (after stripping spaces: \"{chars}\")"
                )
        parsed_rows.append(row_cells)

    rows = len(parsed_rows)
    cols = len(parsed_rows[0]) if rows > 0 else 0

    if rows == 0 or cols == 0:
        raise ValueError("Empty grid")

    # Validate consistent row lengths
    for i, row in enumerate(parsed_rows):
        if len(row) != cols:
            raise ValueError(
                f"Row {i} has {len(row)} cells, expected {cols}. "
                f"Row content: \"{data_lines[i]}\""
            )

    # --- Build h_barriers for all columns ---
    h_barriers = set()
    for after_row in h_barrier_after_rows:
        for c in range(cols):
            h_barriers.add((after_row, c))

    # --- Build cell data ---
    clues = {}
    pre_black = []
    endpoints = set()

    for r in range(rows):
        for c in range(cols):
            cell = parsed_rows[r][c]
            if cell is None:
                continue  # empty cell
            if cell[0] == 'clue':
                _, num, direction = cell
                clues[(r, c)] = (num, direction)
            elif cell[0] == '?':
                clues[(r, c)] = (None, None)
            elif cell[0] == '!':
                endpoints.add((r, c))
            elif cell[0] == '#':
                pre_black.append((r, c))

    return rows, cols, clues, pre_black, endpoints, v_barriers, h_barriers


# ---------------------------------------------------------------------------
# Main solver
# ---------------------------------------------------------------------------

def solve_yajilin(grid_text, verbose=False, max_depth=10000, check_unique=False,
                  find_all=False):
    """
    Solve a Yajilin puzzle.

    Args:
        grid_text: String containing the puzzle in text format
        verbose: If True, print deduction steps
        max_depth: Maximum backtracking depth
        check_unique: If True, search for up to 2 solutions to verify uniqueness
        find_all: If True, search for ALL solutions (no limit)

    Returns:
        (first_solution, solution_count, is_unique, all_solutions) tuple.
        all_solutions is populated when find_all=True.
    """
    rows, cols, clues, pre_black, endpoints, v_barriers, h_barriers = parse_grid(grid_text)

    if verbose:
        print(f"Grid: {rows}x{cols}")
        print(f"Clues: {len(clues)}")
        print(f"Endpoints: {len(endpoints)}")
        print(f"V-barriers: {len(v_barriers)}")
        print(f"H-barriers: {len(h_barriers)}")
        print(f"Pre-black: {len(pre_black)}")

    state = SolverState(rows, cols, clues, pre_black, endpoints,
                        v_barriers, h_barriers)

    # Initial propagation
    if verbose:
        print("\nInitial propagation...")
    try:
        propagate(state, verbose=verbose)
    except Contradiction as e:
        if verbose:
            print(f"Contradiction during initial propagation: {e}")
        return None, 0, False, []

    if verbose:
        print(f"After initial propagation:")
        print(format_state_summary(state))

    # Check if already solved
    is_valid, msg = verify_solution(state)
    if is_valid:
        if verbose:
            print("Solved by propagation alone!")
        return state, 1, True, [state]

    # Backtracking search
    if verbose:
        print("\nStarting backtracking search...")

    if find_all:
        max_sol = 1000000  # effectively unlimited
    elif check_unique:
        max_sol = 2
    else:
        max_sol = 1

    solutions = []

    # Progress indicator (always on, quieter when verbose is off)
    progress = Progress(enabled=True, interval=2.0)

    backtrack(state, depth=0, max_depth=max_depth, verbose=verbose,
              max_solutions=max_sol, solutions=solutions,
              progress=progress)

    progress.done()

    count = len(solutions)
    is_unique = (count == 1)

    if count > 0:
        return solutions[0], count, is_unique, solutions
    else:
        return None, 0, False, []


def format_state_summary(state):
    """Return a brief text summary of the state."""
    unknown = sum(1 for r in range(state.rows) for c in range(state.cols)
                  if state.cell_type[r][c] == CellType.UNKNOWN)
    black = sum(1 for r in range(state.rows) for c in range(state.cols)
                if state.cell_type[r][c] == CellType.BLACK)
    white = sum(1 for r in range(state.rows) for c in range(state.cols)
                if state.cell_type[r][c] == CellType.WHITE)
    endpoint = sum(1 for r in range(state.rows) for c in range(state.cols)
                   if state.cell_type[r][c] == CellType.ENDPOINT)
    clue = sum(1 for r in range(state.rows) for c in range(state.cols)
               if state.cell_type[r][c] == CellType.CLUE)

    lines = [
        f"  UNKNOWN:  {unknown}",
        f"  BLACK:    {black}",
        f"  WHITE:    {white}",
        f"  ENDPOINT: {endpoint}",
        f"  CLUE:     {clue}",
    ]
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_input = os.path.join(script_dir, "example.txt")

    verbose = '-v' in sys.argv or '--verbose' in sys.argv
    check_unique = '-u' in sys.argv or '--unique' in sys.argv
    find_all = '-a' in sys.argv or '--all' in sys.argv

    # --all implies --unique behavior but without the 2-solution cap
    if find_all:
        check_unique = False

    # Filter out flag arguments to find the input path
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    if len(args) > 0:
        input_path = args[0]
    else:
        input_path = default_input

    print(f"Yajilin Solver")
    print(f"==============")
    print(f"Reading input from: {input_path}")
    print()

    with open(input_path, 'r', encoding='utf-8') as f:
        grid_text = f.read()

    print("Input grid:")
    print(grid_text)
    print()

    result, count, is_unique, all_solutions = solve_yajilin(
        grid_text, verbose=verbose,
        check_unique=check_unique, find_all=find_all)

    if result is None:
        print("No solution found.")
        return 1

    if find_all:
        print(f"{count} solution(s) found.")
        print()
    else:
        print("Solution found!")
        print()

    # Report solution count / uniqueness
    if find_all:
        if count == 1:
            print(f"  *** Solution is UNIQUE ***")
        else:
            print(f"  *** {count} total solutions ***")
        print()
    elif check_unique:
        if is_unique:
            print(f"  *** Solution is UNIQUE ***")
        else:
            print(f"  *** WARNING: {count} solutions found! Puzzle is NOT unique. ***")
        print()

    # Count ? clues and endpoints
    q_count = sum(1 for (clue_num, _) in result.clues.values() if clue_num is None)
    ep_count = sum(1 for r in range(result.rows) for c in range(result.cols)
                   if result.is_endpoint(r, c))
    if q_count > 0:
        print(f"  {q_count} question-mark cell(s) (excluded from loop and shading)")
    if ep_count > 0:
        # Count segments = endpoints / 2
        segments = ep_count // 2
        print(f"  {ep_count} endpoint(s) → {segments} path segment(s)")
    if q_count > 0 or ep_count > 0:
        print()

    if find_all:
        # Display all solutions
        for i, sol in enumerate(all_solutions):
            print(f"--- Solution #{i + 1} ---")
            print()
            print("  Box-drawing:")
            for line in display_solution(sol).split('\n'):
                print(f"  {line}")
            print()
            # Verify
            is_valid, msg = verify_solution(sol)
            print(f"  Verification: {msg}")
            print()
    else:
        print("Solution (box-drawing):")
        print(display_solution(result))

        # Verify
        is_valid, msg = verify_solution(result)
        print()
        print(f"Verification: {msg}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
