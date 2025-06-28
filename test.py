x = [i**2 for i in range(10)]
y = {i for i in x}

print(f"{type(x)} {x}")
print(f"{type(y)} {y}")