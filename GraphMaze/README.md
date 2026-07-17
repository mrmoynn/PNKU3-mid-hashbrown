# GraphMaze — Shortest Path in an Undirected Weighted Graph

GraphMaze computes the shortest path between two vertices in an undirected weighted graph using Dijkstra's algorithm. It also includes a utility for transforming edge weights in bulk.

## Files

| File | Description |
|---|---|
| [maze.py](maze.py) | Main program — loads a graph, runs Dijkstra, prints the result. |
| [add_one.py](add_one.py) | Utility — adds a constant to every edge weight in a graph file. |
| [graph.txt](graph.txt) | Sample graph file (26 vertices, 28 edges). |

## Quick Start

```bash
python maze.py graph.txt A D        # Find the shortest path from A to D.
python maze.py                      # Interactive mode (auto-detects graph.txt).
```

## maze.py — Usage

```
python maze.py [file] [start] [end] [-v]
```

**Arguments:**

| Argument | Description |
|---|---|
| `file` | Path to a graph-definition file. Defaults to `graph.txt` in the same directory as `maze.py`. |
| `start` | Label of the start vertex. |
| `end` | Label of the end vertex. |
| `-v` | Verbose: print a graph summary (vertex/edge count) before the result. |

If `start` and `end` are omitted, the program enters interactive mode and prompts for them, listing all available vertices.

**Examples:**

```bash
python maze.py graph.txt A D
python maze.py my_map.txt X Y -v
python maze.py
```

## Graph File Format (`graph.txt`)

Lines starting with `#` are comments. Blank lines are ignored.

### Edge line format

```
<vertex> <vertex> <weight> [label]
```

**Example:**

```
A B 5 ab
B C 3 bc
```

The graph is **undirected** — each edge is added in both directions. The optional label is a string attached to the edge. When the path traverses an edge in the opposite direction, the label is automatically reversed.

### Optional directives (comment lines)

```python
# vertices: A B C D
```
Explicitly declare vertices so isolated vertices (no edges) are included.

```python
# vertex_labels: A=hello B=world
```
Attach a label string to each vertex. Format: `KEY=VALUE`, separated by whitespace.

Edge weights must be **non-negative** (integer or float).

## Output

```
Shortest path: A → B → C → D
Total weight: 10
Concatenated string: "abbccd"
```

The concatenated string is built by joining vertex labels and edge labels along the path:

```
vertex_label[0] + edge_label[0→1] + vertex_label[1] + ...
```

## Application: Square-Grid Mazes

While `maze.py` operates on abstract graphs, a common use case is finding the shortest path through a **square-grid maze** — a grid of cells where walls may be placed between any cell and its four neighbours (up, down, left, right). You can reduce such a maze to a weighted graph and feed it directly into the solver.

### The reduction method

**1. Wipe out dead-ends.** A dead-end is a cell with 0 or 1 open passages. These corridors cannot be part of an optimal route (unless the start or goal lies inside one). For each cell with 1 open passage, continue removing along the single passage it leads to until you meet a junction or the starting/ending cell — each removal may expose a new dead-end, so iterate until no dead-ends remain.

**2. Mark vertices.** After dead-end removal, mark the **starting cell**, the **ending cell**, and every **junction** (a cell with 3 or 4 open passages — crossroads, T-junctions) as the vertices of the graph.

**3. Measure corridors as weighted edges.** Walk each passage between two vertices. The edge weight is **"number of cells along the passage + 1"** (i.e., the edge covers both the corridor cells and the destination vertex). If the start or goal cell is not a junction, treat it as a vertex connected to the nearest junction(s). When multiple passages connect the same pair of vertices, keep only the one with the smallest weight.

**4. Write the graph file.** Encode the result in the format described above and run `maze.py`:

```
S A 1
A B 3
A B 1
B T 4
```

**5. Trace the shortest path.** Use the program output to read off the sequence of vertices. Always choose the passage with the minimum cell count between two vertices — for instance, preferring the 1-weight edge over the 3-weight edge between A and B.

This gives the *geodesic* (cell-count) shortest path through the original grid.

### Example

```
┌───┬───┬───┬───┐
│ S │ / │ 2   3 │
├   ┼   ┼   ┼   ┤
│ 1 | / | 1 | 4 │
├   ┼   ┼   ┼   ┤
│ A   1   B | T │
├   ┼───┼   ┼───┤
│ 1   2   3 | / │
└───┴───┴───┴───┘

```

A 4×2 grid with interior walls. To find the shortest path from S to T:
1. **Remove the dead ends**, including cells with 0 or 1 open passage. For each cell with 1 open passage, continue removing along the single passage it leads to until you meet a junction or the starting/ending cell. The dead-end cells in this example are marked with `/`s.
2. **Mark junctions, the starting cell and the ending cell as vertices**. Junctions include cells with 3 or 4 open passages. The vertices in this example are marked with uppercase letters `S`, `A`, `B`, and `T`.
3. **Count the number of cells in each passage between two arbitrary vertices, and add an undirected edge with weight "\# of cells + 1" as that passage**. The cell counts of each passage in this sample are marked with numbers.
4. **Write that graph as the input file**:

```
S A 1
A B 3
A B 1
B T 4
```

5. **Trace the shortest path using the program output.** The output of this example is `Shortest path: S → A → B → T`. Always choose one with minimum cell count among the passages between two vertices, like choosing the 1-weight edge over the 3-weight edge between A and B.

### Why this works

The reduction preserves shortest-path distances because dead-ends never host an optimal route (they must be entered and exited through the same cell, which is pure detour), and straight corridors between junctions have only one sensible traversal — walk through. The resulting graph is dramatically smaller than the original grid, letting Dijkstra run in milliseconds even on large mazes.

### Letter-concatenation puzzles

A common puzzle variant writes a **letter on each cell** of a square-grid maze and asks you to concatenate the letters along the shortest path to get the answer. The program's concatenated-string output handles this directly by encoding cell letters into the graph file:

- **Vertex labels** (`# vertex_labels:` directive) — assign a label to each junction cell and to the start/end cells. The program interleaves these between edge labels in the output.
- **Edge labels** (the optional fourth field on each edge line) — encode the sequence of letters found on the corridor cells between two vertices. If the path traverses an edge in the opposite direction to how it was written in the file, the label is automatically reversed — so corridor cell letters must be written in the order they appear from the first vertex to the second.

For example, given this reduced graph where cells along the top row spell `C`, `A`, `T` and the bottom row spells `D`, `O`, `G`:

```
# vertex_labels: J1=C J2=T J3=G
J1 J2 2 AT
J1 J3 3 DO
J2 J3 4 XG
```

The shortest path `J1 → J2 → J3` yields a concatenated string of `C` + `AT` + `T` + `XG` + `G` = `"CATTXGG"`. The vertex labels book-end each edge label, and the concatenation follows the path direction naturally — just walk the maze, read the letters, and the program assembles the answer.

## add_one.py — Usage

Adds a constant to every edge weight in a graph file. Comments, blank lines, directives, and non-edge lines are preserved verbatim.

```
python add_one.py <input> [output] [--add N]
```

**Arguments:**

| Argument | Description |
|---|---|
| `input` | Input graph file (required). |
| `output` | Output file. If omitted, prints to stdout. May be the same as input to overwrite in place. |
| `--add N` | Amount to add to each weight (default: `1`). Can be negative. |

**Examples:**

```bash
python add_one.py graph.txt                   # Print to stdout.
python add_one.py graph.txt out.txt           # Write to out.txt.
python add_one.py graph.txt graph.txt         # Overwrite in place.
python add_one.py graph.txt --add 5           # Add 5 instead of 1.
python add_one.py graph.txt --add -2          # Subtract 2 from all weights.
```

## Sample Graph (`graph.txt`)

The included `graph.txt` defines 26 vertices (A–Y) with 28 undirected edges, many with labels and pre-declared vertex labels. Try:

```bash
python maze.py graph.txt A Y
python maze.py graph.txt S T
python maze.py graph.txt           # interactive, try G→Y
```

## Algorithm

**Dijkstra's algorithm** with a binary heap (priority queue). Time complexity is **O((V + E) log V)** where V = vertices and E = edges. Edge weights must be non-negative; negative weights are warned about and may produce incorrect results.

## Requirements

**Python 3.7+** (standard library only — no external packages).
