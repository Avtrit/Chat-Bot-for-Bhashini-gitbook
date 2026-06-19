import itertools

def count_inversions(p):
    inv = 0
    n = len(p)
    for i in range(n):
        for j in range(i + 1, n):
            if p[i] > p[j]:
                inv += 1
    return inv

def is_valid_matching(remaining_values, remaining_reqs):
    # Hall's condition check for matching
    # Since we need to match remaining_values to remaining_reqs such that val >= req.
    # We can sort both and check if val[k] >= req[k] for all k.
    if len(remaining_values) != len(remaining_reqs):
        return False
    sorted_vals = sorted(remaining_values)
    sorted_reqs = sorted(remaining_reqs)
    for v, r in zip(sorted_vals, sorted_reqs):
        if v < r:
            return False
    return True

def get_min_inversions_bf(L):
    n = len(L)
    min_inv = float('inf')
    best_p = None
    for p in itertools.permutations(range(1, n + 1)):
        valid = True
        for i in range(n):
            if p[i] < L[i]:
                valid = False
                break
        if valid:
            inv = count_inversions(p)
            if inv < min_inv:
                min_inv = inv
                best_p = p
    return min_inv, best_p

def get_lex_smallest_valid(L):
    n = len(L)
    p = []
    available = set(range(1, n + 1))
    for i in range(n):
        req = L[i]
        chosen = None
        # Try available values in increasing order
        for v in sorted(available):
            if v >= req:
                # Check if the remaining can be matched
                rem_vals = list(available - {v})
                rem_reqs = L[i+1:]
                if is_valid_matching(rem_vals, rem_reqs):
                    chosen = v
                    break
        if chosen is None:
            return None
        p.append(chosen)
        available.remove(chosen)
    return p

# Test with random L lists
import random
random.seed(42)

for _ in range(1000):
    n = random.randint(1, 7)
    L = [random.randint(1, n + 1) for _ in range(n)]
    
    # Filter out cases where no valid matching exists
    if not is_valid_matching(list(range(1, n + 1)), L):
        continue
        
    min_inv, best_p = get_min_inversions_bf(L)
    lex_p = get_lex_smallest_valid(L)
    if lex_p is None:
        print(f"Error: Lex smallest returned None for L = {L}")
        break
    lex_inv = count_inversions(lex_p)
    
    if lex_inv != min_inv:
        print(f"FAILED for L = {L}")
        print(f"BF: inv = {min_inv}, p = {best_p}")
        print(f"Lex: inv = {lex_inv}, p = {lex_p}")
        break
else:
    print("ALL TESTS PASSED!")
