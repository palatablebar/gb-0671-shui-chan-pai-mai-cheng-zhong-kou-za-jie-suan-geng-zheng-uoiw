from fastapi import APIRouter, Request, Body
from app.engine import evaluate
from app.web import render
router=APIRouter()
@router.get('/auction')
def page(request:Request):
    return render(request,'auction')
@router.post('/api/auction')
def calculate(payload:dict=Body(default={})):
    return evaluate(payload,until=4)
