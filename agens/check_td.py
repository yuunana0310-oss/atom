import re

filepath = 'c:/Users/yuuna/Desktop/AI/e21_form_viewer.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Check what td inline styles include for overflow
samples = re.findall(r'<td style="[^"]*"', content)[:5]
for s in samples:
    print(s[:200])
    print()
