filepath = 'c:/Users/yuuna/Desktop/AI/e21_form_viewer.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

before = content.count('white-space:nowrap')
# Replace white-space:nowrap with white-space:normal so text wraps inside cells
content = content.replace('white-space:nowrap', 'white-space:normal')
after = content.count('white-space:nowrap')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Replaced {before - after} occurrences. Remaining: {after}")
