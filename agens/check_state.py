import re

filepath = 'c:/Users/yuuna/Desktop/AI/e21_form_viewer.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Check current state
print("overflow:hidden count:", content.count('overflow:hidden'))
print("overflow:visible count:", content.count('overflow:visible'))
print("white-space:nowrap count:", content.count('white-space:nowrap'))

# Sample first td
m = re.search(r'<td style="[^"]{0,400}"', content)
if m:
    print("\nSample td style:")
    print(m.group(0))
