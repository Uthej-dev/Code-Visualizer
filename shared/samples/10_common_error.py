# A common bug: reading past the end of a list.
temperatures = [21, 19, 24]
i = 0
while i <= len(temperatures):   # bug: should be <, not <=
    print("Reading", i, "is", temperatures[i])
    i = i + 1
print("Done")                    # never reached
