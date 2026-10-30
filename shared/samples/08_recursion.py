# Recursion: a function that calls itself with a smaller problem.
def factorial(n):
    if n <= 1:
        return 1
    smaller = factorial(n - 1)
    return n * smaller

answer = factorial(4)
print("4! =", answer)
