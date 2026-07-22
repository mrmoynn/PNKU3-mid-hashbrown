"""
Braille Logic Puzzle Solver
============================
Takes a 6x6 binary array (dots and spaces). The grid is partitioned two ways:

  Partition A: 3 rows × 2 cols of 2×3 parts  (each part is 2 rows × 3 cols)
  Partition B: 2 rows × 3 cols of 3×2 parts  (each part is 3 rows × 2 cols)

For each 2×3 part in partition A, we choose one of 4 transformations:
  0. Identity
  1. Rotate 180°
  2. Flip horizontal
  3. Flip vertical
This yields 4^6 = 4096 possible grid states.

We filter for states where every partition B part is a valid Braille letter,
then decode the 6-letter string read in zigzag order over the B parts.
"""

from itertools import product
from typing import List, Tuple, FrozenSet


# ---------------------------------------------------------------------------
# Braille alphabet: dot numbering in a 3×2 cell
#
#   (0,0)=1   (0,1)=4
#   (1,0)=2   (1,1)=5
#   (2,0)=3   (2,1)=6
#
# Each letter is defined by the set of raised dot numbers.
# ---------------------------------------------------------------------------

BRAILLE_DOTS_TO_LETTER: dict = {
    frozenset({1}):                'a',
    frozenset({1, 2}):             'b',
    frozenset({1, 4}):             'c',
    frozenset({1, 4, 5}):          'd',
    frozenset({1, 5}):             'e',
    frozenset({1, 2, 4}):          'f',
    frozenset({1, 2, 4, 5}):       'g',
    frozenset({1, 2, 5}):          'h',
    frozenset({2, 4}):             'i',
    frozenset({2, 4, 5}):          'j',
    frozenset({1, 3}):             'k',
    frozenset({1, 2, 3}):          'l',
    frozenset({1, 3, 4}):          'm',
    frozenset({1, 3, 4, 5}):       'n',
    frozenset({1, 3, 5}):          'o',
    frozenset({1, 2, 3, 4}):       'p',
    frozenset({1, 2, 3, 4, 5}):    'q',
    frozenset({1, 2, 3, 5}):       'r',
    frozenset({2, 3, 4}):          's',
    frozenset({2, 3, 4, 5}):       't',
    frozenset({1, 3, 6}):          'u',
    frozenset({1, 2, 3, 6}):       'v',
    frozenset({2, 4, 5, 6}):       'w',
    frozenset({1, 3, 4, 6}):       'x',
    frozenset({1, 3, 4, 5, 6}):    'y',
    frozenset({1, 3, 5, 6}):       'z',
}

# Reverse map for display
LETTER_TO_DOTS = {v: k for k, v in BRAILLE_DOTS_TO_LETTER.items()}


# ---------------------------------------------------------------------------
# Grid helpers
# ---------------------------------------------------------------------------

Grid = List[List[int]]  # 6x6, 1 = dot, 0 = space


def parse_grid(text: str) -> Grid:
    """Parse a 6-line string of dots and spaces into a 6x6 binary grid."""
    lines = [line for line in text.split('\n') if line.strip('\r') != '' or line.startswith((' ', '.'))]
    # Filter to exactly the 6 content lines (may include cat -n prefix from Read tool)
    clean_lines = []
    for line in lines:
        # Handle cat -n format: "<N>\t<content>" — strip the prefix
        # The prefix is digits followed by a tab
        if '\t' in line:
            prefix, content = line.split('\t', 1)
            if prefix.strip().isdigit():
                line = content
        clean_lines.append(line)

    # Keep only lines that look like grid content (exactly 6 chars of dots/spaces)
    clean_lines = [l for l in clean_lines if len(l) == 6 and all(c in '. ' for c in l)]

    if len(clean_lines) != 6:
        # Debug: show what we got
        for i, l in enumerate(clean_lines):
            print(f"  line {i}: {l!r} (len={len(l)})")
        raise ValueError(f"Expected 6 content lines of 6 chars each, got {len(clean_lines)}")

    grid = []
    for line in clean_lines:
        row = [1 if ch == '.' else 0 for ch in line]
        if len(row) != 6:
            raise ValueError(f"Each line must have exactly 6 characters, got {len(row)}: {line!r}")
        grid.append(row)

    if len(grid) != 6:
        raise ValueError(f"Expected 6 lines, got {len(grid)}")

    return grid


def print_grid(grid: Grid) -> str:
    """Render a 6x6 grid as dots and spaces."""
    return '\n'.join(''.join('.' if c else ' ' for c in row) for row in grid)


# ---------------------------------------------------------------------------
# Partition definitions
# ---------------------------------------------------------------------------

# Partition A: 3 rows × 2 cols of 2×3 parts
# A-part (ai, aj) covers rows [2*ai, 2*ai+1], cols [3*aj, 3*aj+2]
A_ROWS, A_COLS = 3, 2  # arrangement of parts
A_H, A_W = 2, 3         # size of each part

# Partition B: 2 rows × 3 cols of 3×2 parts
# B-part (bi, bj) covers rows [3*bi, 3*bi+2], cols [2*bj, 2*bj+1]
B_ROWS, B_COLS = 2, 3  # arrangement of parts
B_H, B_W = 3, 2         # size of each part


# ---------------------------------------------------------------------------
# Transformations on a 2×3 part (local coordinates)
# ---------------------------------------------------------------------------

def transform_identity(lr: int, lc: int) -> Tuple[int, int]:
    return (lr, lc)


def transform_rotate180(lr: int, lc: int) -> Tuple[int, int]:
    """180-degree rotation of a 2×3 grid."""
    return (1 - lr, 2 - lc)


def transform_flip_h(lr: int, lc: int) -> Tuple[int, int]:
    """Horizontal flip (mirror left-right) of a 2×3 grid."""
    return (lr, 2 - lc)


def transform_flip_v(lr: int, lc: int) -> Tuple[int, int]:
    """Vertical flip (mirror top-bottom) of a 2×3 grid."""
    return (1 - lr, lc)


# All 4 transformations. Each maps a local coordinate to the source local
# coordinate (i.e. where the value should be taken from in the original part).
# Since each is an involution, the inverse is the same as the forward mapping.
TRANSFORMS = [
    transform_identity,   # 0: no change
    transform_rotate180,  # 1: rotate 180°
    transform_flip_h,     # 2: flip horizontally
    transform_flip_v,     # 3: flip vertically
]

TRANSFORM_NAMES = ["identity", "rotate180", "flip-h", "flip-v"]


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def apply_combination(grid: Grid, combo: Tuple[int, ...]) -> Grid:
    """
    Apply the chosen transformations (one per A-part, in row-major order
    over the 3×2 arrangement) to build the output 6×6 grid.

    combo[i] ∈ {0,1,2,3} for i = 0..5, corresponding to A-parts:
      A[0][0], A[0][1], A[1][0], A[1][1], A[2][0], A[2][1]
    """
    output = [[0] * 6 for _ in range(6)]

    for r in range(6):
        for c in range(6):
            # Which A-part does this output cell belong to?
            ai = r // A_H   # 0, 1, or 2
            aj = c // A_W   # 0 or 1
            part_idx = ai * A_COLS + aj
            tfn = TRANSFORMS[combo[part_idx]]

            # Local coords within this A-part
            lr = r % A_H
            lc = c % A_W

            # Where does the value come from in the original part?
            src_lr, src_lc = tfn(lr, lc)

            # Global source coords
            src_r = ai * A_H + src_lr
            src_c = aj * A_W + src_lc

            output[r][c] = grid[src_r][src_c]

    return output


def extract_braille_dots(grid: Grid, bi: int, bj: int) -> FrozenSet[int]:
    """
    Extract the set of raised dot numbers from a 3×2 Braille cell at
    B-part position (bi, bj).

    Dot numbering:
      (0,0)=1  (0,1)=4
      (1,0)=2  (1,1)=5
      (2,0)=3  (2,1)=6
    """
    dot_map = {
        (0, 0): 1, (0, 1): 4,
        (1, 0): 2, (1, 1): 5,
        (2, 0): 3, (2, 1): 6,
    }

    dots = set()
    for lr in range(B_H):
        for lc in range(B_W):
            if grid[bi * B_H + lr][bj * B_W + lc]:
                dots.add(dot_map[(lr, lc)])

    return frozenset(dots)


def decode_zigzag(grid: Grid) -> str | None:
    """
    Try to decode the 6 Braille cells in zigzag order.
    Zigzag: B[0][0], B[0][1], B[0][2], B[1][2], B[1][1], B[1][0]

    Returns the 6-letter string, or None if any cell is not a valid letter.
    """
    # Zigzag order of B-parts
    zigzag_order = [
        (0, 0), (0, 1), (0, 2),  # top row left→right
        (1, 2), (1, 1), (1, 0),  # bottom row right→left
    ]

    letters = []
    for bi, bj in zigzag_order:
        dots = extract_braille_dots(grid, bi, bj)
        letter = BRAILLE_DOTS_TO_LETTER.get(dots)
        if letter is None:
            return None
        letters.append(letter)

    return ''.join(letters)


def solve(grid: Grid, verbose: bool = False) -> List[Tuple[Tuple[int, ...], str]]:
    """
    Find all valid transformation combinations and their resulting strings.

    Returns a list of (combination_tuple, decoded_string) pairs.
    """
    results = []

    # Each of the 6 A-parts can have 1 of 4 transforms → 4^6 = 4096 combos
    for combo in product(range(4), repeat=6):
        transformed = apply_combination(grid, combo)
        decoded = decode_zigzag(transformed)

        if decoded is not None:
            results.append((combo, decoded))
            if verbose:
                names = [TRANSFORM_NAMES[t] for t in combo]
                print(f"  combo: {names}")
                print(f"  string: {decoded}")
                print(f"  grid:")
                print(print_grid(transformed))
                print()

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import sys
    import os

    # Determine input file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_input = os.path.join(script_dir, "example.txt")

    if len(sys.argv) > 1:
        input_path = sys.argv[1]
    else:
        input_path = default_input

    print(f"Reading input from: {input_path}")
    print()

    with open(input_path, 'r') as f:
        text = f.read()

    print("Input grid:")
    print(text)
    print()

    grid = parse_grid(text)

    print("Parsed grid (1=dot, 0=space):")
    for row in grid:
        print(row)
    print()

    results = solve(grid, verbose=False)

    print(f"Found {len(results)} valid combination(s):")
    print()

    # Collect unique strings (different combos may produce the same string)
    seen_strings = set()
    unique_results = []
    for combo, s in results:
        if s not in seen_strings:
            seen_strings.add(s)
            unique_results.append((combo, s))

    for i, (combo, s) in enumerate(unique_results):
        print(f"  [{i+1}] {s}")
        print(f"      transforms: {[TRANSFORM_NAMES[t] for t in combo]}")
        # Show the transformed grid
        transformed = apply_combination(grid, combo)
        print(f"      grid:")
        for row in print_grid(transformed).split('\n'):
            print(f"      |{row}|")
        print()

    if not results:
        print("  (none)")
        print()
        print("No valid Braille strings found. Double-check the input or transform definitions.")

    return results


if __name__ == "__main__":
    main()
