from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import datetime
import models
from dbmanage import get_db
from sqlalchemy.orm import Session
from google.auth.transport import requests
from google.oauth2 import id_token
from uuid import uuid4
import os
from dotenv import load_dotenv

header = "/api/auth"
router = APIRouter(
    prefix = header,
    tags   = ['auth']
)
load_dotenv()
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')

@router.get('/')
async def root():
    return {"success": "true"}

class Google(BaseModel):
    access_token: str

@router.post('/google')
async def google(item: Google, db: Session = Depends(get_db)):
    try:
        # 받은 토큰 검증
        id_info = id_token.verify_oauth2_token(item.access_token, requests.Request(), GOOGLE_CLIENT_ID)

        # 이메일과 이름 추출
        email = id_info.get("email")
        name = id_info.get("name")

        if not email or not name:
            raise HTTPException(status_code=400, detail="Invalid token payload")

        data = db.query(models.UserDB).filter(models.UserDB.email == email).first()
        if data is None:
            user = models.UserDB(google_id=str(uuid4()), email=email, display_name=name)
            db.add(user)
            db.commit()
            db.refresh(user)

        else:
            data.last_login = datetime.datetime.now()
            db.commit()

        ## 세션 생성
        session = models.SessionDB(session_id=str(uuid4()), google_id=data.google_id)
        db.add(session)
        db.commit()

        return JSONResponse({
            "session_token": session.session_id,
            "display_name": data.display_name,
            "study_level" : data.study_level
        })
    
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid token")

class Verify(BaseModel):
    session_token: str

@router.post('/verify')
async def create(item: Verify, db: Session = Depends(get_db)):
    data = db.query(models.SessionDB).filter(models.SessionDB.session_id == item.session_token).first()
    if data is None:
        raise HTTPException(status_code=400, detail="Invalid session token")
    else:
        return JSONResponse({
            "is_valid": True,
            "display_name": data.session_owner.display_name,
            "study_level": data.session_owner.study_level
        })

@router.post('/logout')
async def logout(item: Verify, db: Session = Depends(get_db)):
    data = db.query(models.SessionDB).filter(models.SessionDB.session_id == item.session_token).first()
    if data is None:
        raise HTTPException(status_code=400, detail="Invalid session token")
    else:
        db.delete(data)
        db.commit()
        return JSONResponse({
            "success": True
        })

@router.post('/test_session_create')
async def test_session_create(item: Google, db: Session = Depends(get_db)):
    if os.environ.get('TEST_SESSION_TOKEN') != item.access_token:
        raise HTTPException(status_code=400, detail="Invalid environment")
    data = db.query(models.UserDB).filter(models.UserDB.email == "test@test.com").first()
    if data is not None:
        session = models.SessionDB(session_id=str(uuid4()), google_id=data.google_id)
        db.add(session)
        db.commit()
        return JSONResponse({
            "session_token": session.session_id,
            "display_name": data.display_name,
            "study_level" : data.study_level
        })
    else:
        raise HTTPException(status_code=400, detail="User not found")