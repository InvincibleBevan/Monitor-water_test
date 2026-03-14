from sqlalchemy import Column, Integer, Float, DateTime, Boolean, String
from database import Base
import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    phone = Column(String)
    password_hash = Column(String)


class TelemetryData(Base):
    __tablename__ = "telemetry_data"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    
    # Sensor data
    ph = Column(Float)
    turbidity = Column(Float)
    temperature = Column(Float)
    conductivity = Column(Float)
    
    # System status
    is_contaminated = Column(Boolean, default=False)
    safety_score = Column(Float, default=100.0)
    pathogen_concentration = Column(Float)
    
    # AI model fields
    ai_label = Column(String)
    ai_score = Column(Float)
    ai_is_anomaly = Column(Boolean)

