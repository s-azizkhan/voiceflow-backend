import re
with open('server.py') as f:
    content = f.read()
m = re.search(r'DASHBOARD_HTML = r?"""', content)
start = content.index('"""', m.end() if m else content.index('DASHBOARD_HTML')) + 3
end = content.rindex('"""')
h = content[start:end]
lines = h.split('\n')
for i, l in enumerate(lines[100:120], 101):
    print(f'{i}: {l[:90]}')
