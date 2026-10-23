"""Render the editable Markdown guide using the bundled Python/reportlab runtime."""
from pathlib import Path
from html import escape
import re
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

pdfmetrics.registerFont(TTFont("GuideSans", "/usr/share/fonts/truetype/lato/Lato-Regular.ttf"))
pdfmetrics.registerFont(TTFont("GuideBold", "/usr/share/fonts/truetype/lato/Lato-Bold.ttf"))
pdfmetrics.registerFont(TTFont("GuideMono", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"))

root = Path(__file__).resolve().parents[2]
source = root / 'experiments/docs/simd-kernel-guide.md'
output = root / 'output/pdf/simd-kernel-guide.pdf'
output.parent.mkdir(parents=True, exist_ok=True)
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='GuideTitle', fontName='GuideBold', fontSize=23, leading=28, textColor=colors.HexColor('#14354b'), spaceAfter=16))
styles.add(ParagraphStyle(name='GuideHead', fontName='GuideBold', fontSize=12, leading=16, textColor=colors.HexColor('#176b80'), spaceBefore=13, spaceAfter=7))
styles.add(ParagraphStyle(name='GuideBody', fontName='GuideSans', fontSize=10, leading=14, spaceAfter=8))
styles.add(ParagraphStyle(name='GuideCode', fontName='GuideMono', fontSize=7.5, leading=10.5, backColor=colors.HexColor('#eef3f5'), borderPadding=8, spaceBefore=5, spaceAfter=12))
styles.add(ParagraphStyle(name='GuideBullet', parent=styles['GuideBody'], leftIndent=12, firstLineIndent=-8, spaceAfter=5))

def markup(text):
    text = escape(text)
    return re.sub(r'(https://[^\s]+)', r'<link href="\1" color="#176b80">\1</link>', text)

story = []
for page_index, page in enumerate(source.read_text().split('<!-- page -->')):
    if page_index:
        story.append(PageBreak())
    lines = page.strip().splitlines()
    para = []
    code = None
    def flush():
        if para:
            story.append(Paragraph(markup(' '.join(para)), styles['GuideBody']))
            para.clear()
    for line in lines:
        if line.startswith('```'):
            flush()
            if code is None:
                code = []
            else:
                story.append(Preformatted('\n'.join(code), styles['GuideCode']))
                code = None
        elif code is not None:
            code.append(line)
        elif line.startswith('# '):
            flush()
            story.append(Paragraph(markup(line[2:]), styles['GuideTitle']))
        elif line.startswith('## '):
            flush()
            story.append(Paragraph(markup(line[3:]), styles['GuideHead']))
        elif line.startswith('- ') or re.match(r'^\d\. ', line):
            flush()
            text = '- ' + line[2:] if line.startswith('- ') else line
            story.append(Paragraph(markup(text), styles['GuideBullet']))
        elif not line.strip():
            flush()
        else:
            para.append(line)
    flush()

def footer(canvas, doc):
    canvas.setStrokeColor(colors.HexColor('#c8d7df'))
    canvas.line(48, 42, 564, 42)
    canvas.setFont('GuideSans', 8)
    canvas.setFillColor(colors.HexColor('#526673'))
    canvas.drawString(48, 28, 'PROJECT 1  /  C++ SIMD STARTER')
    canvas.drawRightString(564, 28, str(doc.page))

doc = SimpleDocTemplate(str(output), pagesize=(612, 792), rightMargin=48, leftMargin=48, topMargin=42, bottomMargin=58, title='Your first SIMD kernel in C++', author='Codex')
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print(output)
