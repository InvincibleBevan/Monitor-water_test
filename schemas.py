from pydantic import BaseModel, EmailStr
from datetime import datetime

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    phone: str

    class Config:
        orm_mode = True

class TelemetryCreate(BaseModel):
    ph: float
    turbidity: float
    temperature: float
    conductivity: float
    safety_score: float
    pathogen_concentration: float
    ai_label: str | None = None
    ai_score: float | None = None
    ai_is_anomaly: bool | None = None

class TelemetryDataSchema(BaseModel):
    id: int
    timestamp: datetime
    ph: float
    turbidity: float
    temperature: float
    conductivity: float
    is_contaminated: bool
    safety_score: float
    pathogen_concentration: float
    ai_label: str | None = None
    ai_score: float | None = None
    ai_is_anomaly: bool | None = None

    class Config:
        orm_mode = True
