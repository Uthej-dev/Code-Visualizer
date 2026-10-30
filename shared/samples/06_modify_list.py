# Lists are mutable: changing one through any name changes the same object.
scores = [70, 85, 90]
backup = scores          # same list, two names
copy = list(scores)      # a brand-new list

scores.append(100)
scores[0] = 75
backup.remove(85)

print("scores:", scores)
print("backup:", backup)
print("copy:  ", copy)

scores = [1, 2, 3]       # re-binding: scores now names a different list
print("backup still has", backup)
