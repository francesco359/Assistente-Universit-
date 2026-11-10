from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
def test_health(): assert c.get('/health').json()=={'status':'ok'}
def test_course():
 r=c.post('/api/courses',json={'name':'Test'}); assert r.status_code==200 and r.json()['id']
