"""Render the editable two-page cheat sheet with ReportLab."""
from pathlib import Path
from html import escape
import re
from reportlab.platypus import SimpleDocTemplate, Paragraph, Preformatted, Table, TableStyle, PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
root = Path(__file__).resolve().parents[2]
pdfmetrics.registerFont(TTFont('Lato', '/usr/share/fonts/truetype/lato/Lato-Regular.ttf'))
pdfmetrics.registerFont(TTFont('LatoBold', '/usr/share/fonts/truetype/lato/Lato-Bold.ttf'))
pdfmetrics.registerFont(TTFont('Mono', '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'))
navy=colors.HexColor('#17364b'); teal=colors.HexColor('#136a79')
styles={
 'title':ParagraphStyle('title',fontName='LatoBold',fontSize=19,leading=23,textColor=navy,spaceAfter=8),
 'head':ParagraphStyle('head',fontName='LatoBold',fontSize=10.5,leading=13,textColor=teal,spaceBefore=8,spaceAfter=5),
 'body':ParagraphStyle('body',fontName='Lato',fontSize=8.5,leading=11,spaceAfter=6),
 'cell':ParagraphStyle('cell',fontName='Mono',fontSize=7.0,leading=9),
 'label':ParagraphStyle('label',fontName='Lato',fontSize=8,leading=10),
 'code':ParagraphStyle('code',fontName='Mono',fontSize=7.4,leading=10,backColor=colors.HexColor('#edf3f6'),borderPadding=5,spaceBefore=3,spaceAfter=8),
 'ref':ParagraphStyle('ref',fontName='Lato',fontSize=7,leading=9,spaceAfter=1),
}
def mark(s):
 s=escape(s)
 return re.sub(r'https://[^\s]+',lambda m:f'<link href="{m[0]}" color="#136a79">{m[0]}</link>',s)
story=[]
for idx,page in enumerate((root/'experiments/docs/simd-intrinsics-cheatsheet.md').read_text().split('<!-- page -->')):
 if idx: story.append(PageBreak())
 lines=page.strip().splitlines(); i=0
 while i<len(lines):
  l=lines[i]
  if not l: i+=1; continue
  if l.startswith('# '): story.append(Paragraph(mark(l[2:]),styles['title'])); i+=1
  elif l.startswith('## '): story.append(Paragraph(mark(l[3:]),styles['head'])); i+=1
  elif l.startswith('```'):
   code=[]; i+=1
   while not lines[i].startswith('```'): code.append(lines[i]); i+=1
   story.append(Preformatted('\n'.join(code),styles['code'])); i+=1
  elif l.startswith('|'):
   rows=[]
   while i<len(lines) and lines[i].startswith('|'):
    cells=[x.strip() for x in lines[i].strip('|').split('|')]
    if not all(set(x)<=set('- :') for x in cells): rows.append(cells)
    i+=1
   widths=[145,184,211] if len(rows[0])==3 else [105,70,120,245]
   # Type table is prose; intrinsic names stay monospaced in lookups.
   data=[[Paragraph(mark(c),styles['label'] if r==0 or j==0 or len(row)==4 else styles['cell']) for j,c in enumerate(row)] for r,row in enumerate(rows)]
   t=Table(data,colWidths=widths,hAlign='LEFT')
   t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dceaf0')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.whitesmoke,colors.white]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
   story.append(t)
  else:
   story.append(Paragraph(mark(l),styles['ref'] if re.match(r'^\[\d\]',l) else styles['body'])); i+=1

def footer(c,d):
 c.setFont('Lato',7); c.setFillColor(navy)
 c.drawString(36,20,'SIMD INTRINSICS  /  x86  /  Checked October 18, 2026')
 c.drawRightString(576,20,str(d.page))
out=root/'output/pdf/simd-intrinsics-cheatsheet.pdf'
SimpleDocTemplate(str(out),pagesize=(612,792),leftMargin=36,rightMargin=36,topMargin=30,bottomMargin=34,title='C++ SIMD intrinsics cheat sheet',author='Codex').build(story,onFirstPage=footer,onLaterPages=footer)
print(out)
