from fastapi import APIRouter, Request, Body
from app.engine import evaluate
from app.web import render
router=APIRouter()
@router.get('/pairing')
def page(request:Request):
    return render(request,'pairing')
@router.post('/api/pairing')
def calculate(payload:dict=Body(default={})):
    return evaluate(payload,until=3)
