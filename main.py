from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import asyncio
import json
import os
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai  # common library; replace with 'from google import genai' if using newer SDK
from database import SessionLocal, engine, Base
import models
import schemas
from twilio.rest import Client
from passlib.context import CryptContext
import africastalking
import httpx  # added missing import

# Load environment variables
load_dotenv()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Maji AI API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Africa's Talking SMS
africastalking.initialize(
    os.getenv("AFRICASTALKING_USERNAME"),
    os.getenv("AFRICASTALKING_API_KEY")
)
sms_service = africastalking.SMS

# Google Generative AI
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not set in environment")
genai.configure(api_key=GEMINI_API_KEY)
# For google-genai SDK, use:
# from google import genai
# ai_client = genai.Client(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')  # choose appropriate model

# External AI model endpoint (for AQUA-1B)
AI_MODEL_URL = os.getenv("AI_MODEL_URL", "http://localhost:8001/predict")

async def get_ai_prediction(data: schemas.TelemetryCreate):
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "deviceId": "RiverStation01",
                "pH": data.ph,
                "turbidity": data.turbidity,
                "temperature": data.temperature,
                "conductivity": data.conductivity
            }
            response = await client.post(AI_MODEL_URL, json=payload, timeout=5.0)
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        print(f"AI Model prediction failed: {e}")
    return None

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class AppState:
    def __init__(self):
        self.is_contaminated = False
        self.score = 98.0
        self.current_ph = 7.2
        self.current_tur = 1.5
        self.current_temp = 18.5
        self.current_cond = 350.0
        self.current_pathogens = 0.0
        # AI-related attributes
        self.current_ai_label = None
        self.current_ai_score = None
        self.current_ai_is_anomaly = None

state = AppState()

# WebSocket Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast_json(self, data: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception:
                pass

manager = ConnectionManager()

# SMS alert function (defined before telemetry_loop uses it)
def trigger_sms_alert(record: models.TelemetryData):
    db = SessionLocal()
    try:
        users = db.query(models.User).all()  # In production, filter by opt-in
        numbers = [user.phone for user in users if user.phone]
        if numbers:
            message = (f"🚨 WATER ALERT! Contamination detected at {record.timestamp}. "
                       f"Safety score: {record.safety_score}. Please take precautions.")
            sms_service.send(message, numbers)
            print(f"SMS alert sent to {len(numbers)} recipients")
    except Exception as e:
        print(f"SMS failed: {e}")
    finally:
        db.close()

# Background task for simulating data and sending to websockets
async def telemetry_loop():
    while True:
        # Get AI prediction every 10 seconds
        if int(datetime.now().timestamp()) % 10 == 0:
            ai_data = schemas.TelemetryCreate(
                ph=state.current_ph,
                turbidity=state.current_tur,
                temperature=state.current_temp,
                conductivity=state.current_cond,
                safety_score=state.score,
                pathogen_concentration=state.current_pathogens
            )
            prediction = await get_ai_prediction(ai_data)
            if prediction:
                state.current_ai_label = prediction.get("label")
                state.current_ai_score = prediction.get("risk_score")
                state.current_ai_is_anomaly = prediction.get("anomaly")

        # Save to DB every 5 seconds
        is_db_tick = int(datetime.now().timestamp()) % 5 == 0
        is_ai_tick = int(datetime.now().timestamp()) % 15 == 0

        if is_ai_tick:
            try:
                # Generate AI Insight using Gemini
                prompt = (f"Water Telemetry: pH={state.current_ph}, Turbidity={state.current_tur} NTU, "
                          f"Temp={state.current_temp}C, Conductivity={state.current_cond} uS/cm. "
                          f"Pathogens={state.current_pathogens} CFU/100mL. Safety Score={state.score}/100. "
                          f"Provide a 1-sentence assessment of the safety.")
                # Run in thread to avoid blocking
                response = await asyncio.to_thread(ai_model.generate_content, prompt)
                ai_data = {
                    "type": "ai_insight",
                    "insight": response.text,
                    "safety_score": state.score
                }
                if manager.active_connections:
                    await manager.broadcast_json(ai_data)
            except Exception as e:
                print(f"AI Generation Failed: {e}")

        db_record = None
        if is_db_tick:
            db = SessionLocal()
            try:
                db_record = models.TelemetryData(
                    ph=state.current_ph,
                    turbidity=state.current_tur,
                    temperature=state.current_temp,
                    conductivity=state.current_cond,
                    is_contaminated=state.is_contaminated,
                    safety_score=state.score,
                    pathogen_concentration=state.current_pathogens,
                    ai_label=state.current_ai_label,
                    ai_score=state.current_ai_score,
                    ai_is_anomaly=state.current_ai_is_anomaly
                )
                db.add(db_record)
                db.commit()
                db.refresh(db_record)

                # Check for SMS if contamination and low score
                if state.is_contaminated and state.score < 40:
                    trigger_sms_alert(db_record)
            finally:
                db.close()

        data = {
            "type": "telemetry",
            "timestamp": datetime.now().isoformat(),
            "ph": state.current_ph,
            "turbidity": state.current_tur,
            "temperature": state.current_temp,
            "conductivity": state.current_cond,
            "safety_score": state.score,
            "is_contaminated": state.is_contaminated,
            "pathogen_concentration": state.current_pathogens,
            "ai_label": state.current_ai_label,
            "ai_score": state.current_ai_score,
            "ai_is_anomaly": state.current_ai_is_anomaly
        }

        if manager.active_connections:
            await manager.broadcast_json(data)

        await asyncio.sleep(1)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(telemetry_loop())

@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/api/history", response_model=list[schemas.TelemetryDataSchema])
def get_history(limit: int = 100, db: Session = Depends(get_db)):
    records = db.query(models.TelemetryData).order_by(models.TelemetryData.timestamp.desc()).limit(limit).all()
    records.reverse()
    return records

@app.post("/api/simulate-issue")
def simulate_issue():
    state.is_contaminated = True
    return {"status": "success", "message": "Contamination simulated"}

@app.post("/api/resolve-issue")
def resolve_issue():
    state.is_contaminated = False
    return {"status": "success", "message": "Contamination resolved"}

@app.post("/api/telemetry")
def receive_telemetry(data: schemas.TelemetryCreate):
    state.current_ph = data.ph
    state.current_tur = data.turbidity
    state.current_temp = data.temperature
    state.current_cond = data.conductivity
    state.score = data.safety_score
    state.current_pathogens = data.pathogen_concentration

    return {"status": "success", "is_contaminated": state.is_contaminated}

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

@app.post("/api/register", response_model=schemas.UserResponse)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = get_password_hash(user.password)
    new_user = models.User(
        name=user.name,
        email=user.email,
        phone=user.phone,
        password_hash=hashed_password
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/api/login")
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    return {
        "message": "Login successful",
        "user": {
            "id": db_user.id,
            "name": db_user.name,
            "email": db_user.email,
            "phone": db_user.phone
        }
    }
