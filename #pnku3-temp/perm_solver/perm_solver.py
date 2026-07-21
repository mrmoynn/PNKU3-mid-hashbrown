#!/usr/bin/env python3
"""
Permutation Solver

Reads an input file containing:
  - m words (one per line, tab-separated from an index prefix)
  - a blank line
  - a comma-separated list of m numbers (a_1, ..., a_m)

For each permutation of the number list (m! total), takes the p_i-th letter
(1-indexed) from the i-th word, producing a string.
A number 0 means "skip" — no letter is taken from the corresponding word.
All resulting strings are written to the output file, one per line, sorted.
"""

import sys
import itertools
import os

def solve(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Parse: split into words section and numbers section by blank line
    words = []
    numbers = []
    past_blank = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            past_blank = True
            continue
        if not past_blank:
            # Format: "1\tpirate" — take the part after tab
            parts = stripped.split('\t')
            word = parts[1] if len(parts) > 1 else parts[0]
            words.append(word)
        else:
            # Comma-separated numbers
            numbers = [int(x.strip()) for x in stripped.split(',')]

    m = len(words)
    if len(numbers) != m:
        print(f"Warning: {len(words)} words but {len(numbers)} numbers", file=sys.stderr)

    results = []
    for perm in itertools.permutations(numbers):
        chars = []
        for i, p in enumerate(perm):
            if p == 0:
                continue  # 0 means skip this word
            word = words[i]
            if 1 <= p <= len(word):
                chars.append(word[p - 1])
            else:
                chars.append('?')  # out of bounds fallback
        results.append(''.join(chars))

    # Sort for deterministic output
    results.sort()

    with open(output_path, 'w', encoding='utf-8') as f:
        for r in results:
            f.write(r + '\n')

    print(f"Done. {len(results)} strings written to {output_path}")

if __name__ == '__main__':
    if len(sys.argv) >= 3:
        solve(sys.argv[1], sys.argv[2])
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        input_path = os.path.join(script_dir, 'example.txt')
        output_path = os.path.join(script_dir, 'example-out.txt')
        solve(input_path, output_path)
