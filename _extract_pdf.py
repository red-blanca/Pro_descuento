from pathlib import Path
import PyPDF2
pdf = Path(r'C:\Users\rza_w\Downloads\soluciones-digitales.pptx.pdf')
reader = PyPDF2.PdfReader(str(pdf))
for i, page in enumerate(reader.pages, 1):
    txt = page.extract_text() or ''
    print(f'--- PAGE {i} ---')
    safe = txt.encode('utf-8', 'replace').decode('utf-8', 'replace')
    print((safe[:2500] + ('\\n...[truncado]' if len(safe) > 2500 else ''))
          .encode('unicode_escape').decode('ascii'))
    print()
