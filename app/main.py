from __future__ import annotations
import json, os, re, sqlite3, uuid, zipfile
from pathlib import Path
from typing import Any
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pypdf import PdfReader
from docx import Document
from pptx import Presentation
from openpyxl import load_workbook

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; DATA.mkdir(exist_ok=True)
UPLOADS=DATA/'uploads'; UPLOADS.mkdir(exist_ok=True); DB=DATA/'app.db'
app=FastAPI(title='LectureForge',version='0.1.0')
app.mount('/static',StaticFiles(directory=ROOT/'app/static'),name='static')
tpl=Jinja2Templates(directory=ROOT/'app/templates')

def db():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init():
 c=db(); c.executescript('''
 CREATE TABLE IF NOT EXISTS courses(id TEXT PRIMARY KEY,name TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,course_id TEXT,name TEXT,kind TEXT,text TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY,course_id TEXT,kind TEXT,title TEXT,payload TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
 '''); c.commit(); c.close()
init()

class Course(BaseModel): name:str
class Generate(BaseModel): course_id:str; title:str='Materiale di studio'; difficulty:str='difficile'; quiz_count:int=20

def clean(s:str)->str:
 return re.sub(r'\s+',' ',s or '').strip()

def extract(path:Path)->str:
 ext=path.suffix.lower()
 if ext in {'.txt','.md','.csv','.json','.html'}:
  return path.read_text(errors='ignore')
 if ext=='.pdf': return '\n'.join((p.extract_text() or '') for p in PdfReader(str(path)).pages)
 if ext=='.docx': return '\n'.join(p.text for p in Document(str(path)).paragraphs)
 if ext=='.pptx':
  prs=Presentation(str(path)); return '\n'.join(sh.text for sl in prs.slides for sh in sl.shapes if hasattr(sh,'text'))
 if ext=='.xlsx':
  wb=load_workbook(path,data_only=True,read_only=True); out=[]
  for ws in wb.worksheets:
   out.append(f'FOGLIO: {ws.title}')
   for row in ws.iter_rows(values_only=True): out.append(' | '.join('' if v is None else str(v) for v in row))
  return '\n'.join(out)
 if ext in {'.zip'}:
  out=[]
  with zipfile.ZipFile(path) as z:
   for name in z.namelist():
    if name.lower().endswith(('.txt','.md','.json','.html')):
     out.append(z.read(name).decode(errors='ignore'))
  return '\n'.join(out)
 raise ValueError(f'Formato non supportato: {ext}')

def parse_chat(text:str)->str:
 """Normalizza esportazioni ChatGPT/Claude/Copilot in JSON o testo."""
 try:
  obj=json.loads(text)
  parts=[]
  def walk(x):
   if isinstance(x,dict):
    role=x.get('role') or x.get('author') or x.get('sender')
    content=x.get('content') or x.get('text') or x.get('message')
    if isinstance(content,str): parts.append(f'{role or "messaggio"}: {content}')
    for v in x.values(): walk(v)
   elif isinstance(x,list):
    for v in x: walk(v)
  walk(obj)
  return '\n'.join(dict.fromkeys(parts)) or text
 except Exception:
  return text

def sentences(text:str):
 return [clean(x) for x in re.split(r'(?<=[.!?])\s+|\n+',text) if len(clean(x))>35]

def keywords(text:str,n=12):
 stop=set('della delle degli della che per con sono come anche questo questa nella nelle degli alla dalla più non una uno del dei un il la le i gli e o a da in di su si'.split())
 words=re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'-]{3,}",text.lower())
 from collections import Counter
 return [w for w,_ in Counter(w for w in words if w not in stop).most_common(n)]

def course_text(cid:str)->str:
 c=db(); rows=c.execute('SELECT text FROM sources WHERE course_id=? ORDER BY created_at',(cid,)).fetchall(); c.close()
 return '\n'.join(r['text'] for r in rows)

def make_map(text:str,title:str):
 ss=sentences(text); ks=keywords(text,10); nodes=[]
 for k in ks:
  related=[s for s in ss if k in s.lower()][:3]
  nodes.append({'concept':k.title(),'explanation':related[0] if related else f'Concetto chiave: {k}.','details':related[1:]})
 return {'title':title,'central_question':'Quali sono definizioni, formule, collegamenti ed esempi essenziali?','nodes':nodes,'sources_note':'Generato esclusivamente dai materiali caricati.'}

def make_cards(text:str):
 ss=sentences(text); ks=keywords(text,20); cards=[]
 for k in ks:
  hit=next((s for s in ss if k in s.lower()),None)
  if hit: cards.append({'front':f'Che cosa devi ricordare su “{k}”?','back':hit})
 return cards

def make_quiz(text:str,count:int):
 ss=sentences(text); ks=keywords(text,30); qs=[]
 for i,k in enumerate(ks):
  hit=next((s for s in ss if k in s.lower()),None)
  if not hit: continue
  distract=[x.title() for x in ks if x!=k][:2]
  opts=[k.title()]+distract
  shift=i%3; opts=opts[shift:]+opts[:shift]; ans=opts.index(k.title())
  qs.append({'question':f'Quale concetto è descritto dalla seguente affermazione? “{hit[:220]}”','options':opts,'answer':ans,'explanation':f'La frase contiene e definisce il concetto “{k}”.'})
  if len(qs)>=count: break
 return qs

def save_art(cid,kind,title,payload):
 aid=str(uuid.uuid4()); c=db(); c.execute('INSERT INTO artifacts VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)',(aid,cid,kind,title,json.dumps(payload,ensure_ascii=False))); c.commit(); c.close(); return aid

@app.get('/',response_class=HTMLResponse)
def home(request:Request):
 c=db(); courses=c.execute('SELECT * FROM courses ORDER BY created_at DESC').fetchall(); c.close()
 return tpl.TemplateResponse('index.html',{'request':request,'courses':courses})

@app.post('/api/courses')
def create_course(x:Course):
 cid=str(uuid.uuid4()); c=db(); c.execute('INSERT INTO courses(id,name) VALUES(?,?)',(cid,x.name)); c.commit(); c.close(); return {'id':cid,'name':x.name}

@app.get('/api/courses/{cid}')
def get_course(cid:str):
 c=db(); cr=c.execute('SELECT * FROM courses WHERE id=?',(cid,)).fetchone(); src=c.execute('SELECT id,name,kind,created_at FROM sources WHERE course_id=?',(cid,)).fetchall(); arts=c.execute('SELECT id,kind,title,created_at FROM artifacts WHERE course_id=? ORDER BY created_at DESC',(cid,)).fetchall(); c.close()
 if not cr: raise HTTPException(404,'Corso non trovato')
 return {'course':dict(cr),'sources':[dict(x) for x in src],'artifacts':[dict(x) for x in arts]}

@app.post('/api/upload')
async def upload(course_id:str=Form(...),kind:str=Form('document'),files:list[UploadFile]=File(...)):
 out=[]
 for f in files:
  safe=f'{uuid.uuid4()}_{Path(f.filename).name}'; path=UPLOADS/safe; path.write_bytes(await f.read())
  try: text=extract(path); text=parse_chat(text) if kind=='chat' else text
  except Exception as e: raise HTTPException(400,str(e))
  sid=str(uuid.uuid4()); c=db(); c.execute('INSERT INTO sources(id,course_id,name,kind,text) VALUES(?,?,?,?,?)',(sid,course_id,f.filename,kind,text)); c.commit(); c.close(); out.append({'id':sid,'name':f.filename,'chars':len(text)})
 return out

@app.post('/api/generate')
def generate(x:Generate):
 text=course_text(x.course_id)
 if len(text)<100: raise HTTPException(400,'Carica almeno un materiale con testo sufficiente')
 result={
  'map':save_art(x.course_id,'concept_map',x.title,make_map(text,x.title)),
  'flashcards':save_art(x.course_id,'flashcards',x.title,make_cards(text)),
  'quiz':save_art(x.course_id,'quiz',x.title,make_quiz(text,min(max(x.quiz_count,5),50)))
 }
 return result

@app.get('/api/artifacts/{aid}')
def artifact(aid:str):
 c=db(); r=c.execute('SELECT * FROM artifacts WHERE id=?',(aid,)).fetchone(); c.close()
 if not r: raise HTTPException(404,'Artefatto non trovato')
 x=dict(r); x['payload']=json.loads(x['payload']); return x

@app.get('/artifact/{aid}',response_class=HTMLResponse)
def artifact_page(request:Request,aid:str):
 x=artifact(aid); return tpl.TemplateResponse('artifact.html',{'request':request,'a':x})

@app.get('/health')
def health(): return {'status':'ok'}
