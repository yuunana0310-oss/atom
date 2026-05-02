filepath = 'c:/Users/yuuna/Desktop/AI/e21_form_viewer.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

before = content.count('overflow:hidden')
# Replace all occurrences of overflow:hidden with overflow:visible
content = content.replace('overflow:hidden', 'overflow:visible')
after = content.count('overflow:hidden')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Replaced {before - after} occurrences. Remaining: {after}")
