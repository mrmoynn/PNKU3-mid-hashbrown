"""
GraphMaze — Shortest path in an undirected weighted graph.

Given an undirected weighted graph and two vertices (start and end),
this program computes and prints the shortest path between them using
Dijkstra's algorithm.  Edge weights must be non‑negative.

Usage:
    python maze.py graph.txt A D       — shortest path from A to D
    python maze.py graph.txt           — interactive mode (prompts for vertices)

Input file format (plain text):
    # Lines starting with # are comments; blank lines are ignored.
    # Format:  <vertex> <vertex> <weight> [label]
    # The graph is undirected — each edge is added in both directions.
    # Weights must be non‑negative numbers (integer or float).
    # The optional label is a string attached to the edge.  When the path
    # traverses an edge in the opposite direction, the label is reversed.

    # Optional: declare vertices explicitly so isolated vertices are included:
    #   # vertices: A B C D E

    A B 5 ab
    B C 3 bc
    A C 8 ac
    C D 2 cd

Output:
    Shortest path and total weight, with concatenated edge labels, e.g.:
        Shortest path: A → B → C → D
        Total weight: 10
        Concatenated string: "abbccd"
"""

import argparse
import heapq
import math
import os
import re
import sys
from collections import defaultdict


# ── Edge-file loader ──────────────────────────────────────────────────────

def load_graph(filepath: str) -> tuple[list[str], dict[str, dict[str, tuple[float, str]]], dict[str, str]]:
    """Parse a weighted-graph file.

    Returns (vertices, adjacency, vertex_labels) where *vertices* is a sorted
    list of unique vertex labels, *adjacency* is a dict of dicts:
        adjacency[u][v] = (weight, label)
    and *vertex_labels* maps vertex names to their label strings (empty string
    for vertices without a declared label).

    An optional label string may appear after the weight on each edge line.
    For the direction opposite to the one in the file, the label is reversed.

    Supports optional comment directives:
        # vertices: A B C D
        # vertex_labels: A=hello B=world C=foo bar
    Otherwise vertices are inferred from the edge list.
    """
    adjacency: dict[str, dict[str, tuple[float, str]]] = defaultdict(dict)
    vertex_set: set[str] = set()
    declared_vertices: list[str] | None = None
    vertex_labels: dict[str, str] = {}

    with open(filepath, "r", encoding="utf-8") as f:
        for lineno, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                stripped = line.lstrip("#").strip()
                if stripped.startswith("vertices:"):
                    declared_vertices = stripped[len("vertices:"):].strip().split()
                elif stripped.startswith("vertex_labels:"):
                    # Format:  # vertex_labels: A=hello B=world C=foo bar
                    # Split on whitespace before each KEY= pattern
                    raw = stripped[len("vertex_labels:"):].strip()
                    for part in re.split(r"\s+(?=\w+=)", raw):
                        if "=" in part:
                            k, v = part.split("=", 1)
                            vertex_labels[k] = v
                continue
            parts = line.split()
            if len(parts) < 3:
                print(f"  [skip] line {lineno}: expected 3 fields, got {len(parts)} — {line!r}",
                      file=sys.stderr)
                continue
            u, v = parts[0], parts[1]
            try:
                w = float(parts[2])
            except ValueError:
                print(f"  [skip] line {lineno}: invalid weight {parts[2]!r} — {line!r}",
                      file=sys.stderr)
                continue
            if w < 0:
                print(f"  [warn] line {lineno}: negative weight {w} — {line!r}",
                      file=sys.stderr)
            # Optional label string — empty if not present
            label = " ".join(parts[3:]) if len(parts) > 3 else ""
            adjacency[u][v] = (w, label)
            adjacency[v][u] = (w, label[::-1])
            vertex_set.add(u)
            vertex_set.add(v)

    if declared_vertices:
        # Merge: ensure all declared vertices are present (even if isolated),
        # then append any extra vertices inferred from edges, in sorted order.
        for v in declared_vertices:
            vertex_set.add(v)
        declared_set = set(declared_vertices)
        extra = sorted(v for v in vertex_set if v not in declared_set)
        vertices = declared_vertices + extra
    else:
        vertices = sorted(vertex_set)
    return vertices, dict(adjacency), vertex_labels


# ── Dijkstra ──────────────────────────────────────────────────────────────

def shortest_path(vertices: list[str],
                  adjacency: dict[str, dict[str, tuple[float, str]]],
                  start: str,
                  end: str,
                  vertex_labels: dict[str, str] | None = None) -> tuple[float, list[str], str]:
    """Return (total_weight, path, concatenated_label) of the shortest path.

    Uses Dijkstra's algorithm.  Returns (math.inf, [], "") if no path exists.
    The concatenated label is built as:
        v_label[0] + edge_label[0→1] + v_label[1] + edge_label[1→2] + ...
    Vertex labels (from # vertex_labels:) are interleaved between edge labels.
    When the path direction is opposite to the file's specification the edge
    label is reversed automatically (handled at load time).
    """
    if vertex_labels is None:
        vertex_labels = {}
    # Gather every vertex — declared list plus any reachable via adjacency.
    all_vertices: set[str] = set(vertices)
    for u, targets in adjacency.items():
        all_vertices.add(u)
        all_vertices.update(targets.keys())

    # Distance from start to each vertex
    dist: dict[str, float] = {v: math.inf for v in all_vertices}
    dist[start] = 0.0

    # Predecessor for path reconstruction
    prev: dict[str, str | None] = {v: None for v in all_vertices}

    # Priority queue: (distance, vertex)
    pq: list[tuple[float, str]] = [(0.0, start)]
    visited: set[str] = set()

    while pq:
        d, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)

        if u == end:
            break

        for v, (w, _) in adjacency.get(u, {}).items():
            if v in visited:
                continue
            new_dist = d + w
            if new_dist < dist[v]:
                dist[v] = new_dist
                prev[v] = u
                heapq.heappush(pq, (new_dist, v))

    if math.isinf(dist[end]):
        return math.inf, [], ""

    # Reconstruct path
    path: list[str] = []
    cur: str | None = end
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()

    # Concatenate labels: vertex[0] + edge[0→1] + vertex[1] + edge[1→2] + ...
    concat = vertex_labels.get(path[0], "")
    for i in range(len(path) - 1):
        _, label = adjacency[path[i]][path[i + 1]]
        concat += label
        concat += vertex_labels.get(path[i + 1], "")

    return dist[end], path, concat


# ── Output ────────────────────────────────────────────────────────────────

def print_result(total_weight: float, path: list[str], concat: str = "") -> None:
    """Print the shortest path, total weight, and concatenated edge string."""
    if not path:
        print("No path exists between the specified vertices.")
        return
    print(f"Shortest path: {' → '.join(path)}")
    # Print weight as integer if it has no fractional part
    if total_weight == int(total_weight):
        print(f"Total weight: {int(total_weight)}")
    else:
        print(f"Total weight: {total_weight}")
    if concat:
        print(f"Concatenated string: \"{concat}\"")


# ── Interactive input ─────────────────────────────────────────────────────

def interactive_prompt(vertices: list[str]) -> tuple[str, str]:
    """Prompt the user for start and end vertices."""
    print("Available vertices:", " ".join(vertices))
    print()
    start = input("Start vertex: ").strip()
    end = input("End   vertex: ").strip()
    if not start or not end:
        print("Both start and end vertices are required.", file=sys.stderr)
        sys.exit(1)
    if start not in vertices:
        print(f"Vertex {start!r} is not in the graph.", file=sys.stderr)
        sys.exit(1)
    if end not in vertices:
        print(f"Vertex {end!r} is not in the graph.", file=sys.stderr)
        sys.exit(1)
    return start, end


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Shortest path in an undirected weighted graph (Dijkstra).",
    )
    parser.add_argument(
        "file", nargs="?",
        help="Graph-definition file (default: auto-detect graph.txt in script directory).",
    )
    parser.add_argument(
        "start", nargs="?",
        help="Start vertex.",
    )
    parser.add_argument(
        "end", nargs="?",
        help="End vertex.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Print the graph summary (vertices and edges) before the result.",
    )

    args = parser.parse_args()

    # ── Resolve filepath ──────────────────────────────────────────────
    if args.file:
        filepath = args.file
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        candidate = os.path.join(script_dir, "graph.txt")
        if os.path.isfile(candidate):
            filepath = candidate
        else:
            filepath = None

    if not filepath:
        print("No graph file specified and no graph.txt found in script directory.",
              file=sys.stderr)
        sys.exit(1)

    # ── Load graph ────────────────────────────────────────────────────
    if not os.path.isfile(filepath):
        print(f"File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    vertices, adjacency, vertex_labels = load_graph(filepath)

    if not vertices:
        print("Graph has no vertices.", file=sys.stderr)
        sys.exit(1)

    edge_count = sum(len(targets) for targets in adjacency.values()) // 2

    if args.verbose:
        print(f"Graph: {len(vertices)} vertices, {edge_count} undirected edges")
        print(f"Vertices: {vertices}")
        print("-" * 40)

    # ── Resolve start/end ─────────────────────────────────────────────
    if args.start and args.end:
        start, end = args.start, args.end
    elif args.start or args.end:
        print("Both start and end vertices must be provided, or neither for interactive mode.",
              file=sys.stderr)
        sys.exit(1)
    else:
        start, end = interactive_prompt(vertices)

    if start not in vertices:
        print(f"Vertex {start!r} is not in the graph.", file=sys.stderr)
        sys.exit(1)
    if end not in vertices:
        print(f"Vertex {end!r} is not in the graph.", file=sys.stderr)
        sys.exit(1)

    if start == end:
        print_result(0.0, [start], vertex_labels.get(start, ""))
        return

    # ── Compute & print ───────────────────────────────────────────────
    weight, path, concat = shortest_path(vertices, adjacency, start, end, vertex_labels)
    print_result(weight, path, concat)


if __name__ == "__main__":
    main()
