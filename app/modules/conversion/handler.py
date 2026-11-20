from fastapi import APIRouter, Request, Body
from app.engine import evaluate
from app.web import render
router=APIRouter()
@router.get('/conversion')
def page(request:Request):
    return render(request,'conversion')
@router.post('/api/conversion')
def calculate(payload:dict=Body(default={})):
    return evaluate(payload,until=2)
