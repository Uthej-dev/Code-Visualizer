# Linear search: look at each item until we find the target.
names = ["Lin", "Sam", "Priya", "Omar", "Zoe"]
target = "Priya"
found_at = -1

index = 0
while index < len(names):
    if names[index] == target:
        found_at = index
        break
    index = index + 1

if found_at >= 0:
    print(target, "found at index", found_at)
else:
    print(target, "is not in the list")
