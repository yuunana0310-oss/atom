import re

filepath = 'c:/Users/yuuna/Desktop/AI/e21_form_viewer.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# The td inline styles have no overflow property at all.
# The CSS rule for .form-table td also has no overflow.
# We need to:
#   1. Keep white-space:nowrap (row height stays fixed)
#   2. Add overflow:visible to each td's inline style
#   3. Also fix the CSS class

# Add overflow:visible after position:relative in each td's inline style
# Pattern: position:relative;box-sizing:border-box" -> add overflow:visible
count = [0]
def replacer(m):
    count[0] += 1
    return m.group(0).replace('position:relative;box-sizing:border-box"', 
                               'position:relative;overflow:visible;box-sizing:border-box"')

content = re.sub(r'<td style="[^"]*position:relative;box-sizing:border-box"', replacer, content)

print(f"Updated {count[0]} td elements with overflow:visible")
print(f"Verification - overflow:visible count: {content.count('overflow:visible')}")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Done!")
