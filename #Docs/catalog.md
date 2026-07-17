# PNKU3-mid-hashbrown — Tool Catalog

A small, bilingual (EN/ZH) puzzle-solving toolkit. Pure Python 3.7+ with no external dependencies. Each tool lives in its own directory with dual-language READMEs.

---

## Logic Puzzle

### 01Sudoku — Possibility-Matrix Solver
**File:** [solver.py](../Logic%20Puzzle/01Sudoku/solver.py)

Takes a Sudoku puzzle and outputs a **27×27 possibility matrix** — for every empty cell, it shows exactly which digits can appear there across *all* valid solutions. Instead of enumerating solutions (which can miss placements when many solutions exist), it tests each `(cell, digit)` pair individually via backtracking with the MRV heuristic.

- **Input:** 81-char traditional format or 729-char 27×27 grid (round-trip capable — output can be hand-edited and fed back in).
- **Output:** Formatted 27×27 grid with separators; live terminal progress bar.
- **Template:** `--template` flag generates an all-ones template for constraint editing.

| File | Role |
|---|---|
| `solver.py` | Main solver with backtracking + MRV, progress bar, dual-format I/O |
| `template_all.txt` | Pre-generated 27×27 all-ones template for hand-editing |
| `README.md` / `README_zh.md` | Bilingual documentation |

---

## Strategic Puzzle

### GraphMaze — Shortest Path (Dijkstra)
**File:** [maze.py](../Strategic%20Puzzle/GraphMaze/maze.py)

Computes the shortest path between two vertices in an **undirected weighted graph** using Dijkstra's algorithm with a binary heap (`O((V+E) log V)`). Supports labeled vertices and edges for letter-concatenation puzzle variants.

- **Input:** Plain-text edge lines (`<u> <v> <weight> [label]`), directives for vertex declarations and vertex labels, `#` comments.
- **Output:** Shortest path, total weight, and concatenated label string. Interactive mode when start/end are omitted.
- **Methodology:** The README documents a 5-step reduction for converting square-grid mazes into weighted graphs.

| File | Role |
|---|---|
| `maze.py` | Dijkstra solver with labeled edges/vertices, interactive + CLI mode |
| `example-input.txt` | Sample graph: 26 vertices (A–Y), 28 edges with labels |

### add\_one — Edge Weight Transformer
**File:** [add_one.py](../Strategic%20Puzzle/GraphMaze/add_one.py)

Reads a graph file and outputs a copy with every edge weight **incremented by a constant** (default `+1`, configurable via `--add N`; negative values subtract). Comments, blanks, and directives are preserved verbatim. Supports in-place overwrite.

| File | Role |
|---|---|
| `add_one.py` | Bulk weight adjustment utility preserving all formatting |

---

## Repository Layout

```
PNKU3-mid-hashbrown/
├── #Docs/                  ← AI agent & catalog metadata (this file)
│   ├── AGENT.md
│   └── catalog.md
├── Logic Puzzle/
│   └── 01Sudoku/           ← Possibility-matrix Sudoku solver
└── Strategic Puzzle/
    └── GraphMaze/          ← Dijkstra shortest-path + weight utility
```

---

*All tools are Python 3.7+, standard library only. Each component has English and Chinese (简体中文) documentation.*
