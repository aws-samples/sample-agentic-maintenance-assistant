from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import json

Base = declarative_base()

class Simulator(Base):
    __tablename__ = 'simulators'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    class_name = Column(String(100), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    asset_types = relationship("AssetType", back_populates="simulator")

class AssetType(Base):
    __tablename__ = 'asset_types'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)  # e.g., "Roller Coaster", "Ferris Wheel"
    description = Column(Text)
    simulator_id = Column(Integer, ForeignKey('simulators.id'))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    simulator = relationship("Simulator", back_populates="asset_types")
    assets = relationship("Asset", back_populates="asset_type")

class MLModel(Base):
    __tablename__ = 'ml_models'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    model_type = Column(String(50))  # e.g., "LSTM", "RandomForest"
    model_path = Column(String(255))
    is_trained = Column(Boolean, default=False)
    accuracy = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    assets = relationship("Asset", back_populates="ml_model")

class Asset(Base):
    __tablename__ = 'assets'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)  # e.g., "Main Roller Coaster"
    asset_type_id = Column(Integer, ForeignKey('asset_types.id'), nullable=False)
    ml_model_id = Column(Integer, ForeignKey('ml_models.id'))
    map_x = Column(Float)  # X coordinate on map
    map_y = Column(Float)  # Y coordinate on map
    map_width = Column(Float, default=50)  # Area width
    map_height = Column(Float, default=50)  # Area height
    status = Column(String(20), default='active')  # active, maintenance, offline
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    asset_type = relationship("AssetType", back_populates="assets")
    ml_model = relationship("MLModel", back_populates="assets")

class MapConfig(Base):
    __tablename__ = 'map_configs'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    image_path = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=False)
    width = Column(Integer, default=1200)
    height = Column(Integer, default=800)
    created_at = Column(DateTime, default=datetime.utcnow)

# Database setup
engine = create_engine('sqlite:///theme_park.db', pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()