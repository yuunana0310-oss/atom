filepath = 'c:/Users/yuuna/Desktop/AI/e21_form_viewer.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Revert: white-space:normal → white-space:nowrap (keep row height fixed)
before = content.count('white-space:normal')
content = content.replace('white-space:normal', 'white-space:nowrap')
after_nowrap = content.count('white-space:nowrap')
print(f"Reverted white-space:normal → nowrap: {before} occurrences")

# Make sure overflow is visible (text shows outside cell)
before_ov = content.count('overflow:visible')
if 'overflow:hidden' in content:
    content = content.replace('overflow:hidden', 'overflow:visible')
    print(f"Also fixed overflow:hidden remaining")

# Ensure the CSS .form-table td also has overflow:visible
# Update the CSS rule for .form-table td
content = content.replace(
    '.form-table td {\n  cursor: pointer;\n  font-size: 7.5pt;\n  line-height: 1.2;\n  word-break: break-all;\n}',
    '.form-table td {\n  cursor: pointer;\n  font-size: 7.5pt;\n  line-height: 1.2;\n  word-break: keep-all;\n  overflow: visible;\n  white-space: nowrap;\n}'
)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Done. overflow:visible count: {content.count('overflow:visible')}")
