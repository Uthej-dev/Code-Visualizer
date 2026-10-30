# Dictionaries map keys to values.
stock = {"apples": 5, "pears": 2}
stock["bananas"] = 7        # add a new key
stock["apples"] = 3         # update an existing key
del stock["pears"]          # remove a key

for fruit in stock:
    print(fruit, "->", stock[fruit])

total = sum(stock.values())
print("Total fruit:", total)
