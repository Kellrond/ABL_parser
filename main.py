with open('keywords.txt', 'r') as file:
    lines = file.read()

lines.replace('check mark', 'True')
lines = lines.split('\n')

keywords = []
for ln in lines:
    keywords.append(ln.split('\t'))

keywords = [ {'keyword':x[0], 'reserved': True if x[1] != '?' else False, 'min_abr': x[2] if x[2] != '?' else None} for x in keywords ]

with open('language/generated_keywords_list.py', 'w') as file:
    file.write('keywords = [\n')
    [file.write(f"    {x},\n") for x in keywords]
    file.write(']\n\n')

