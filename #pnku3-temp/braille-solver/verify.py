"""Verification script for braille-solver transforms and Braille mapping."""
from solver import *

# ---------------------------------------------------------------------------
# Verify: the 4 transforms on a 2x3 part are all distinct
# ---------------------------------------------------------------------------
part = [
    [1, 0, 0],
    [0, 1, 1],
]

def apply_to_part(part, tfn):
    result = [[0]*3 for _ in range(2)]
    for r in range(2):
        for c in range(3):
            sr, sc = tfn(r, c)
            result[r][c] = part[sr][sc]
    return result

print('=== Transform verification ===')
print('Original:')
for row in part:
    print(f'  {row}')

results = {}
for i, tfn in enumerate(TRANSFORMS):
    result = apply_to_part(part, tfn)
    results[i] = result
    print(f'{TRANSFORM_NAMES[i]}:')
    for row in result:
        print(f'  {row}')

# Check all 4 are distinct
from itertools import combinations
for (i1, r1), (i2, r2) in combinations(results.items(), 2):
    if r1 == r2:
        print(f'ERROR: {TRANSFORM_NAMES[i1]} == {TRANSFORM_NAMES[i2]}')
    else:
        print(f'OK: {TRANSFORM_NAMES[i1]} != {TRANSFORM_NAMES[i2]}')

# Verify each transform composed with itself = identity (involution)
print()
print('=== Involution check ===')
for i, tfn in enumerate(TRANSFORMS):
    once = apply_to_part(part, tfn)
    twice = apply_to_part(once, tfn)
    if twice == part:
        print(f'OK: {TRANSFORM_NAMES[i]} is an involution')
    else:
        print(f'ERROR: {TRANSFORM_NAMES[i]} is NOT an involution')

# ---------------------------------------------------------------------------
# Verify Braille mapping
# ---------------------------------------------------------------------------
print()
print('=== Braille verification ===')

# Manually check 's' = {2,3,4}
# In a 3x2 cell: dot 2=(1,0), dot 3=(2,0), dot 4=(0,1)
dot_map = {(0,0):1, (0,1):4, (1,0):2, (1,1):5, (2,0):3, (2,1):6}
grid_3x2 = [[0,1],[1,0],[1,0]]
dots_test = set()
for r in range(3):
    for c in range(2):
        if grid_3x2[r][c]:
            dots_test.add(dot_map[(r,c)])
print(f'  s-cell dots: {dots_test} -> {BRAILLE_DOTS_TO_LETTER.get(frozenset(dots_test), "?")}')
print(f'  expected: {{2,3,4}} -> s')

# Check known letters
test_cases = [
    ('a', {1},           [[1,0],[0,0],[0,0]]),
    ('b', {1,2},         [[1,0],[1,0],[0,0]]),
    ('c', {1,4},         [[1,1],[0,0],[0,0]]),
    ('k', {1,3},         [[1,0],[0,0],[1,0]]),
    ('u', {1,3,6},       [[1,0],[0,0],[1,1]]),
    ('w', {2,4,5,6},     [[0,1],[1,1],[0,1]]),
    ('z', {1,3,5,6},     [[1,0],[0,1],[1,1]]),
]
all_ok = True
for letter, expected_dots, expected_grid in test_cases:
    dots = set()
    for r in range(3):
        for c in range(2):
            if expected_grid[r][c]:
                dots.add(dot_map[(r,c)])
    decoded = BRAILLE_DOTS_TO_LETTER.get(frozenset(dots), "?")
    status = "OK" if (dots == expected_dots and decoded == letter) else "FAIL"
    if status == "FAIL":
        all_ok = False
    print(f'  {status}: letter={letter}, dots={dots}, decoded={decoded}')

# Check all 26 letters have unique dot patterns
print()
print(f'  Total letter mappings: {len(BRAILLE_DOTS_TO_LETTER)}')
all_letters = set(BRAILLE_DOTS_TO_LETTER.values())
print(f'  Unique letters: {len(all_letters)}')
if len(all_letters) == 26:
    print('  OK: all 26 letters mapped')
else:
    missing = set('abcdefghijklmnopqrstuvwxyz') - all_letters
    print(f'  MISSING: {missing}')

# ---------------------------------------------------------------------------
# End-to-end: verify one combination produces the expected string
# ---------------------------------------------------------------------------
print()
print('=== End-to-end verification ===')
with open('example.txt') as f:
    text = f.read()
grid = parse_grid(text)

# Test the first result: combo with all identity
combo_all_identity = (0, 0, 0, 0, 0, 0)
transformed = apply_combination(grid, combo_all_identity)
decoded = decode_zigzag(transformed)
print(f'All-identity combo: {combo_all_identity}')
print(f'Decoded: {decoded}')
if decoded:
    # Show each B-part as a Braille cell
    zigzag_order = [(0,0),(0,1),(0,2),(1,2),(1,1),(1,0)]
    for idx, (bi, bj) in enumerate(zigzag_order):
        dots = extract_braille_dots(transformed, bi, bj)
        letter = BRAILLE_DOTS_TO_LETTER.get(dots, "?")
        cell_str = ""
        for r in range(3):
            row_str = ""
            for c in range(2):
                row_str += "." if transformed[bi*3+r][bj*2+c] else " "
            cell_str += row_str + "\n"
        print(f'  B[{bi}][{bj}] = {letter} dots={set(dots)}')
        print(f'    {cell_str.replace(chr(10), chr(10)+"    ").strip()}')

print()
print('All verifications complete!')
