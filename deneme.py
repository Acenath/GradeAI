line = "2. Thesis statement is supported by at least three pieces of evidence from credible sources (11231231230 pt)"
first, last = -5, -6
while line[first:last:-1].isdigit():
        last += -1
        
last += 1 if last != -6 else 0

print(line[first:last:-1][::-1])