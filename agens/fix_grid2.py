import re

filepath = 'c:/Users/yuuna/Desktop/AI/e21_form_viewer.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Change columns to a wider size, e.g. 24px and rows to 24px
content = re.sub(r'<col style="width:\d+px">', '<col style="width:24px">', content)
content = re.sub(r'<tr style="height:\d+px">', '<tr style="height:24px">', content)

# Remove overflow:hidden so text is never cut off
content = content.replace('overflow:hidden', 'overflow:visible')

# Maybe font-size is too small? The inline style has font-size:12.0pt or font-size:8.0pt in some places, but CSS has 7.5pt. Let's make CSS font-size: 8pt.
content = content.replace('font-size: 7.5pt;', 'font-size: 8pt;')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed layout")
