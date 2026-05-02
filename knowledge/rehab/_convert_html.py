"""
HTMLファイルをMarkdownに変換してRAGナレッジDBに格納するスクリプト
使い方: python _convert_html.py
"""
from html.parser import HTMLParser
import re, os, sys

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.skip = False
        self.skip_tags = {'script', 'style', 'head', 'nav', 'footer'}
        self.tag_stack = []

    def handle_starttag(self, tag, attrs):
        self.tag_stack.append(tag)
        if tag in self.skip_tags:
            self.skip = True
        if tag in ('h1', 'h2', 'h3', 'h4', 'p', 'li', 'tr'):
            self.text.append('\n')
        if tag == 'hr':
            self.text.append('\n---\n')

    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            self.skip = False
        if tag in ('p', 'li', 'h1', 'h2', 'h3', 'h4', 'tr', 'div', 'section'):
            self.text.append('\n')
        if self.tag_stack and self.tag_stack[-1] == tag:
            self.tag_stack.pop()

    def handle_data(self, data):
        if not self.skip:
            d = data.strip()
            if d:
                t = self.tag_stack[-1] if self.tag_stack else ''
                if t == 'h1':   d = '# ' + d
                elif t == 'h2': d = '## ' + d
                elif t == 'h3': d = '### ' + d
                elif t == 'h4': d = '#### ' + d
                elif t == 'strong' or t == 'b': d = f'**{d}**'
                self.text.append(d + ' ')


def html_to_md(path: str) -> str:
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    p = TextExtractor()
    p.feed(content)
    text = ''.join(p.text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+\n', '\n', text)
    return text.strip()


def convert(src_path: str, dest_path: str, frontmatter: str):
    body = html_to_md(src_path)
    content = frontmatter + '\n\n' + body
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'  OK: {dest_path}')


BASE = os.path.dirname(os.path.abspath(__file__))
AGENS = os.path.join(BASE, '..', '..')

CONVERSIONS = [
    {
        'src': os.path.join(AGENS, '記事/AI/医療職AI活用シリーズ/股関節/股関節OA画像所見と臨床症状の解離.html'),
        'dest': os.path.join(BASE, 'reports/hip_oa_imaging_clinical_dissociation.md'),
        'frontmatter': """---
title: 股関節OA 画像所見と臨床症状の解離
category: reports
tags: [股関節, 変形性関節症, 疫学, Framingham, OAI, CHECK]
source: 記事/AI/医療職AI活用シリーズ/股関節/股関節OA画像所見と臨床症状の解離.html
added: 2026-04-06
---"""
    },
    {
        'src': os.path.join(AGENS, '記事/AI/医療職AI活用シリーズ/股関節/股関節変形性関節症理学療法士の治療アプローチ.html'),
        'dest': os.path.join(BASE, 'reports/hip_oa_pt_treatment_approach.md'),
        'frontmatter': """---
title: 股関節変形性関節症 理学療法士の治療アプローチ
category: reports
tags: [股関節, 変形性関節症, 理学療法, 運動療法, エビデンス]
source: 記事/AI/医療職AI活用シリーズ/股関節/股関節変形性関節症理学療法士の治療アプローチ.html
added: 2026-04-06
---"""
    },
    {
        'src': os.path.join(AGENS, 'departments/02_medical_rehab/rehab/swallowing_pt_evidence_report.html'),
        'dest': os.path.join(BASE, 'reports/swallowing_pt_evidence_report.md'),
        'frontmatter': """---
title: 嚥下障害 PT向けエビデンスレポート
category: reports
tags: [嚥下, 摂食嚥下, 理学療法, エビデンス]
source: departments/02_medical_rehab/rehab/swallowing_pt_evidence_report.html
added: 2026-04-06
---"""
    },
]

if __name__ == '__main__':
    print('HTMLファイルをMarkdownに変換中...')
    for item in CONVERSIONS:
        src = os.path.normpath(item['src'])
        if not os.path.exists(src):
            print(f'  SKIP (not found): {src}')
            continue
        convert(src, os.path.normpath(item['dest']), item['frontmatter'])
    print('完了')
