import re
filepath = 'c:/Users/yuuna/Desktop/AI/e21_form_viewer.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()
# Replace <col style="width:XXpx"> with 16px
content = re.sub(r'<col style="width:\d+px">', '<col style="width:16px">', content)
# Replace <tr style="height:XXpx"> with 16px
content = re.sub(r'<tr style="height:\d+px">', '<tr style="height:16px">', content)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
