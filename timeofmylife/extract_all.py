import zipfile
import xml.etree.ElementTree as ET
import os

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

def extract_docx_text(path):
    with zipfile.ZipFile(path, 'r') as z:
        with z.open('word/document.xml') as f:
            tree = ET.parse(f)
    root = tree.getroot()
    lines = []
    for p in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
        texts = []
        for t in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'):
            if t.text:
                texts.append(t.text)
        lines.append(''.join(texts))
    return '\n'.join(lines)

files = {
    'v2_converged': 'Beyond_Parameter_Scaling_V2_Converged_Theory_and_Research_Program.docx',
    'joker_corpus': 'Joker_Corpus_Dossier_LifeDocs.docx',
    'book3_beholder': 'Book_III_The_Beholder_Between_Fullness_and_Emptiness_V3.docx',
}

out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'extracted')
os.makedirs(out_dir, exist_ok=True)

for key, fname in files.items():
    path = os.path.join(r'C:\Users\Admin\Downloads', fname)
    text = extract_docx_text(path)
    out_path = os.path.join(out_dir, f'{key}.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f'{key}: {len(text)} chars -> {out_path}')

print('Done.')
