# Find the largest of three numbers with if / elif / else.
x = 14
y = 42
z = 27

if x >= y and x >= z:
    largest = x
elif y >= x and y >= z:
    largest = y
else:
    largest = z

print("The largest number is", largest)
