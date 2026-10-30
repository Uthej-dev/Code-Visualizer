# Functions get their own frame with local variables.
def area(width, height):
    result = width * height
    return result

def describe(w, h):
    a = area(w, h)
    return "A " + str(w) + "x" + str(h) + " rectangle has area " + str(a)

room = area(3, 4)
text = describe(5, 2)
print(room)
print(text)
