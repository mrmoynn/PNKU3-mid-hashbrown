"""
GraphMaze/add_one — Add 1 to every edge weight in a graph file.

Reads a graph file and writes a copy where every edge weight is incremented
by 1.  Comments, blank lines, and the # vertices: directive are preserved
verbatim.  Non‑edge lines are passed through unchanged.

Usage:
    python add_one.py graph.txt                  — print to stdout
    python add_one.py graph.txt out.txt          — write to out.txt
    python add_one.py graph.txt graph.txt        — overwrite in place
    python add_one.py graph.txt --add N          — add N instead of 1
"""

import argparse
import sys


def transform(filepath: str, increment: float = 1.0) -> list[str]:
    """Read *filepath* and return a list of lines with every edge weight + *increment*."""
    out_lines: list[str] = []

    with open(filepath, "r", encoding="utf-8") as f:
        for raw_line in f:
            # Preserve trailing newline behaviour — strip only for inspection
            line = raw_line.rstrip("\n")
            stripped = line.strip()

            # Pass through blank lines and comments unchanged
            if not stripped or stripped.startswith("#"):
                out_lines.append(raw_line.rstrip("\n"))
                continue

            parts = stripped.split()
            if len(parts) < 3:
                # Not a valid edge line — pass through unchanged
                out_lines.append(line)
                continue

            # Try to parse the third field as a number
            try:
                old_weight = float(parts[2])
            except ValueError:
                # Third field isn't a number — pass through unchanged
                out_lines.append(line)
                continue

            new_weight = old_weight + increment
            # Format: keep as integer if it has no fractional part
            if new_weight == int(new_weight):
                parts[2] = str(int(new_weight))
            else:
                parts[2] = str(new_weight)

            out_lines.append(" ".join(parts))

    return out_lines


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add a constant to every edge weight in a graph file.",
    )
    parser.add_argument(
        "input", help="Input graph file.",
    )
    parser.add_argument(
        "output", nargs="?",
        help="Output file (default: print to stdout).  May be the same as input.",
    )
    parser.add_argument(
        "--add", type=float, default=1.0,
        help="Amount to add to each weight (default: 1).",
    )

    args = parser.parse_args()

    out_lines = transform(args.input, increment=args.add)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            for line in out_lines:
                f.write(line + "\n")
        if args.output == args.input:
            print(f"Updated {len([l for l in out_lines if l and not l.startswith('#') and len(l.split()) >= 3])} edge(s) in place: {args.input}")
        else:
            print(f"Written {args.output}")
    else:
        for line in out_lines:
            print(line)


if __name__ == "__main__":
    main()
