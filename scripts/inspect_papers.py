from pathlib import Path
import json
from pypdf import PdfReader

root = Path(__file__).resolve().parents[1] / 'audit' / 'evidence'
summary = {}
for name in ('longpibench', 'promptlocate'):
    reader = PdfReader(root / (name + '.pdf'))
    pages = [page.extract_text() for page in reader.pages]
    (root / (name + '_extracted.txt')).write_text('\n'.join(pages), encoding='utf-8')
    summary[name] = {'pages': len(pages), 'table4_pages': [i + 1 for i, text in enumerate(pages) if 'Table 4:' in text]}
print(json.dumps(summary))
