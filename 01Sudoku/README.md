# 01Sudoku — Possibility-Matrix Solver

Takes a Sudoku puzzle and outputs a **27×27 matrix** showing, for every
original cell, exactly which digits can appear there in at least one valid
complete solution.

## How the 27×27 mapping works

```
Original 9×9 cell (row, col)         27×27 block starting at (row×3, col×3)
┌─────┬─────┬─────┐                  ┌──────────┬──────────┬──────────┐
│     │     │     │                  │ 1  2  3  │ 1  2  3  │ 1  2  3  │
│     │     │     │   ──────────▶    │ 4  5  6  │ 4  5  6  │ 4  5  6  │
│     │     │     │                  │ 7  8  9  │ 7  8  9  │ 7  8  9  │
├─────┼─────┼─────┤                  ├──────────┼──────────┼──────────┤
│     │  ?  │     │                  │ 1  2  3  │ 1  2  3  │ 1  2  3  │
│     │     │     │   ──────────▶    │ 4  5  6  │ 4  5  6  │ 4  5  6  │
│     │     │     │                  │ 7  8  9  │ 7  8  9  │ 7  8  9  │
├─────┼─────┼─────┤                  ├──────────┼──────────┼──────────┤
│     │     │     │                  │ 1  2  3  │ 1  2  3  │ 1  2  3  │
│     │     │     │   ──────────▶    │ 4  5  6  │ 4  5  6  │ 4  5  6  │
│     │     │     │                  │ 7  8  9  │ 7  8  9  │ 7  8  9  │
└─────┴─────┴─────┘                  └──────────┴──────────┴──────────┘
```

Each 3×3 block in the output represents one cell of the original puzzle.
Within that block, digits 1–9 are laid out row-major:

```
1 2 3
4 5 6
7 8 9
```

A digit is **shown** only if it appears in that original cell in at least one valid
complete solution. Digits that never appear are replaced with `.`.

## Usage

```bash
# From stdin
python solver.py < puzzle.txt

# From file
python solver.py puzzle.txt

# Generate a template (all digits on) for editing
python solver.py --template
```

### Output format

The solver always outputs a 27×27 grid with grid separators (35 characters
wide, properly aligned):

```
123|123|123|123|123|123|123|123|123
456|456|456|456|456|456|456|456|456
789|789|789|789|789|789|789|789|789
---+---+---+---+---+---+---+---+---
123|123|...
...
===+===+===+===+===+===+===+===+===
...
```

- **Rows** are 35 characters wide (27 digits + 8 `|` column separators).
- **Minor separators** (`---+`) appear every 3 rows between sub-bands.
- **Major separators** (`===+`) appear every 9 rows between 3×3 box bands.
- Only the matrix goes to **stdout**; all diagnostic messages go to **stderr**.

### Round-tripping

The output can be redirected to a file, edited, and fed back as input —
grid-drawing characters (`|`, `-`, `+`, `=`) are stripped automatically:

```bash
python solver.py puzzle.txt > result.txt
# … edit result.txt to add or remove digit constraints …
python solver.py result.txt
```

## Input formats

Two formats are accepted and **auto-detected** by character count:

| Characters | Format | Description |
|---|---|---|
| 81 | Traditional Sudoku string | `0` / `.` for empty, `1`–`9` for givens |
| 729 | 27×27 grid | Same format as the solver's own output |

### Traditional format (81 characters)

Whitespace is ignored — use any human-friendly layout:

```
5 3 0 0 7 0 0 0 0
6 0 0 1 9 5 0 0 0
0 9 8 0 0 0 0 6 0
8 0 0 0 6 0 0 0 3
4 0 0 8 0 3 0 0 1
7 0 0 0 2 0 0 0 6
0 6 0 0 0 0 2 8 0
0 0 0 4 1 9 0 0 5
0 0 0 0 8 0 0 7 9
```

Or as a single line:

```
530070000600195000098000060800060003400803001700020006060000280000419005000080079
```

### 27×27 grid format (729 characters)

The same format as the solver's output.  Each 3×3 block specifies which
digits **may** appear in that original cell:

- A digit shown (`1`–`9`) → the digit is allowed in that cell.
- A dot (`.`) → the digit is **not** allowed in that cell.
- A cell with only one digit → treated as a given (must be that digit).

Use `python solver.py --template` to generate a starting-point file
(`template_all.txt`) with all 729 digits enabled.

## Example

```bash
echo "530070000600195000098000060800060003400803001700020006060000280000419005000080079" | python solver.py
```

For a puzzle with a unique solution, the output shows exactly one digit per
3×3 block (the solution digit). For puzzles with multiple solutions, blocks
may show several possible digits.

## Progress bar

When stderr is a terminal, a live progress bar shows elapsed time and an
ETA for the current solve:

```
[==========>           ]  45% | 245/548 | 12.3s elapsed | 14.8s ETA
```

## How it works

Instead of enumerating all complete solutions (which can miss digit
placements when many solutions exist), the solver checks every empty cell
and each candidate digit individually: it places the digit, then tests
whether the resulting board is still solvable via backtracking with MRV
(Minimum Remaining Values heuristic).

A **node limit** (100,000 recursive calls per check) prevents the solver
from stalling on pathological "prove impossible" searches.  When the limit
is hit the solver conservatively assumes the digit *is* possible and warns
on stderr:

```
// Warning: search limit hit 3 time(s) — some digits may be shown as possible when they are not.
```

## File list

| File | Purpose |
|---|---|
| `solver.py` | Main solver script |
| `template_all.txt` | Template with all digits enabled (generated by `--template`) |
| `example_easy.txt` | Example puzzle (unique solution) |
| `input` | Sparse puzzle (7 givens, many solutions) |
| `input2` | Constrained puzzle |
| `input3-1` | Intermediate possibility matrix for iterative solving |
