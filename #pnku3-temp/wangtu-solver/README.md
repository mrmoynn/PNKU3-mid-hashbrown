# Wangtu — King-Move Logic Puzzle Solver

Given an n×m grid with forbidden cells and king pieces (each annotated
with a step count), find **all** ways to move every king exactly that many
steps such that:

1. No two kings ever occupy the same cell (paths are disjoint).
2. No king ever steps on a forbidden cell.
3. At their final positions, no two kings **check** each other
   (Chebyshev distance ≤ 1 — adjacent in any of the 8 directions).

A king moves one cell per step in any of the 8 chess-king directions
(horizontal, vertical, diagonal).  A king cannot revisit a cell it has
already occupied during its own walk (self-avoiding path).

## Files

| File | Role |
|---|---|
| `wangtu.py` | Main solver — path enumeration, backtracking search, dual-format output |
| `example-input.txt` | Annotated 3×3 example with two 2-step kings |
| `example-input-2.txt` | 3×3 example with a 0-step king (stays in place) |
| `README.md` / `README_zh.md` | Bilingual documentation |

## Usage

```
python wangtu.py < input.txt
python wangtu.py puzzle.txt
python wangtu.py puzzle.txt --max-solutions 50
python wangtu.py puzzle.txt --compact
python wangtu.py puzzle.txt --no-progress
```

### Options

| Flag | Effect |
|---|---|
| `--max-solutions N` | Stop after finding N solutions (default: 1000) |
| `--compact` | Coordinates only; no step-by-step grid visualisation |
| `--progress` / `--no-progress` | Force progress reporting on or off (default: auto-detect TTY) |

## Input Format

A plain-text grid with space-separated values, one row per line.
Lines starting with `#` are comments; blank lines are ignored.

| Token | Meaning |
|---|---|
| `-1` or `#` | Forbidden cell — no king may enter |
| `.` | Empty traversable cell |
| `0` | 0-step king — stays in place (occupies its starting cell) |
| `1`, `2`, `3`, … | King that must move exactly that many steps |

**Example** (`example-input.txt`):

```
# 3×3 grid — two kings, centre forbidden
2 . 2
. # .
. . .
```

- King 0 starts at (0, 0) and must take 2 steps.
- King 1 starts at (0, 2) and must take 2 steps.
- Cell (1, 1) is forbidden.

**Example with a 0-step king** (`example-input-2.txt`):

```
# 3×3 grid — moving king + stationary king
2 . .
. # .
. . 0
```

- King 0 starts at (0, 0) and must take 2 steps.
- King 1 starts at (2, 2) with **0 steps** — stays in place.

## Output Format

### Full mode (default)

Each solution includes:

1. **Path listing** — coordinate sequences for each king.
2. **Step-by-step ASCII grid** — shows king positions at each step.

Grid symbols: `#` forbidden, `.` empty, `0`–`9` for kings 0–9,
`A`–`Z` for kings 10–35.

### Compact mode (`--compact`)

Coordinate sequences only, one king per line.  Machine-parseable.

```
=== Solution 1 ===
# King 0 (2 step(s), start r0c0)
(0,0) (0,1) (1,0)
# King 1 (2 step(s), start r0c2)
(0,2) (1,2) (2,2)
```

## Algorithm

1. **Parse** the input grid, identifying kings and forbidden cells.
2. **Enumerate** all valid self-avoiding paths for each king via DFS.
3. **Backtrack** with MRV ordering (fewest paths first) to find all
   path combinations satisfying the disjointness and no-check constraints.
4. **Output** each valid solution with optional step-by-step visualisation.

The search space is pruned incrementally: as soon as a candidate path
shares a cell with any already-placed king, it is rejected.  The
final-position check (no mutual check) is applied only when all kings
have been placed.

## Requirements

Python 3.7 or later.  Standard library only — no external dependencies.
