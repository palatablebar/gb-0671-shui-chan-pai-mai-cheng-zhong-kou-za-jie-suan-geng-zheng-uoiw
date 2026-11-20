from fastapi import APIRouter, Request, Body
from app.engine import evaluate
from app.web import render
router=APIRouter()
@router.get('/correction')
def page(request:Request):
    return render(request,'correction')
@router.post('/api/correction')
def calculate(payload:dict=Body(default={})):
    return evaluate(payload,until=5)
