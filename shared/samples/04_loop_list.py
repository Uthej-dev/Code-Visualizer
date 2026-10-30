# Loop through a list and keep a running total.
prices = [4, 8, 15, 16]
total = 0
for price in prices:
    total = total + price
    print("Added", price, "-> total is", total)

count = len(prices)
print("Average price:", total / count)
