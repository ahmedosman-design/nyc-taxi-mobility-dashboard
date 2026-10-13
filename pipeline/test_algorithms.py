from algorithms import top_k_zones

data = [(1, 50), (2, 900), (3, 10), (4, 700), (5, 300), (6, 800)]
print(top_k_zones(data, 3))
# expected: [(900, 2), (800, 6), (700, 4)]