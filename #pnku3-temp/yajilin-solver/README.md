# Yajilin Solver

Solves **Yajilin** logic puzzles — a Nikoli puzzle genre combining cell shading
with loop drawing. Supports the **question mark (?)** variant.

## Rules

Yajilin is played on a rectangular grid. Some cells contain **numbered arrows**
(clue cells) on a grey background. The objective:

1. **Shade (blacken)** some cells. Shaded cells cannot share an edge
   (no orthogonal adjacency), but may touch diagonally.
2. **Draw a single closed loop** through **all** remaining unshaded, non-clue
   cells. The loop moves orthogonally from cell center to cell center — no
   branches, crossings, or dead ends.
3. **Numbered arrows** indicate exactly how many shaded cells exist in that
   direction (along the row or column, all the way to the grid edge).
   Clue cells are never shaded and the loop never passes through them.
4. **Question marks (?)** mark a cell that is excluded from both shading and
   the loop (like other clue cells), but provide no number or direction
   constraint. The direction is irrelevant — `?` simply means "this cell is
   not part of the loop and cannot be shaded."

Not every shaded cell needs to be counted by an arrow.

## Input Format

One line per grid row, space-separated cell tokens:

| Token | Meaning |
|-------|---------|
| `.` | Empty cell (to be determined) |
| `Nn` | Clue: N shaded cells **n**orth (↑ / above) |
| `Ns` | Clue: N shaded cells **s**outh (↓ / below) |
| `Nw` | Clue: N shaded cells **w**est (← / left) |
| `Ne` | Clue: N shaded cells **e**ast (→ / right) |
| `?` | Question-mark cell (excluded from loop and shading, no constraint) |
| `#` | Pre-shaded cell (optional) |

### Example (`example.txt`)

```
1s . . . .
.  . . . .
.  ?  . . .
.  . . . .
.  . . . 2w
```

This 5×5 puzzle has three special cells:
- `1s` at (0,0): exactly 1 shaded cell below in column 0
- `?` at (2,1): excluded from loop and shading (no further constraint)
- `2w` at (4,4): exactly 2 shaded cells to the left in row 4

## Usage

```bash
# Solve the default example
python solver.py

# Solve a specific puzzle file
python solver.py path/to/puzzle.txt

# Verbose mode — show deduction steps and backtracking progress
python solver.py puzzle.txt -v
```

## Output

The solver displays:
1. The input grid
2. Count of question-mark cells
3. The solution in two formats:
   - **Box-drawing** (Unicode): uses `╔ ╗ ╚ ╝ ║ ═` for loop, `#` for shaded cells
   - **ASCII**: uses `, - '` `. for loop, `#` for shaded cells
4. Verification result

### Example Output

```
Solution (ASCII):
1s  #  ,-----.
 ,-----'  #  |
 | ?   #  ,--'
 `--.  ,--'  #
 #  `--'  # 2w
```

## Algorithm

The solver uses **backtracking search with constraint propagation**:

### Deduction Rules
1. **Black adjacency**: If a cell is shaded, all four orthogonal neighbors
   must be loop cells (cannot be adjacent black).
2. **Arrow clues**: If the required number of shaded cells is reached in an
   arrow's direction, remaining unknowns become loop cells. If unknowns must
   all be shaded to reach the required count, they become shaded.
   Question-mark cells are skipped — they provide no directional constraint.
3. **Loop degree**: Each loop cell needs exactly 2 connections. If only 2
   edges are possible, both are confirmed and others blocked.
4. **Edge symmetry**: Loop connections between adjacent cells must be mutual.
5. **Forced connections**: A loop cell with 1 confirmed edge and only 1
   remaining possible edge must use it.
6. **Premature loop closure**: If a subset of loop cells forms a closed cycle
   without including all loop cells, the state is rejected.

### Search Strategy
When propagation reaches a fixed point without solving the puzzle:
- Find the most constrained undecided cell (preferring cells in arrow paths,
  near edges, or adjacent to shaded cells)
- Branch by trying **shaded** first, then **loop cell**
- If all cells are decided but edge choices remain, branch on individual edges

No external dependencies — uses only the Python standard library.

## Files

- `solver.py` — Main solver (~1000 lines)
- `example.txt` — Example 5×5 puzzle with a question-mark cell
- `README.md` — This file
