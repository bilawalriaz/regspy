import json
from sqlalchemy import create_engine, Column, String, DateTime, Integer, ForeignKey, Float, Boolean, Text, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from contextlib import contextmanager
from datetime import datetime

Base = declarative_base()

class VehicleCache(Base):
    __tablename__ = 'vehicle_cache'
    id = Column(Integer, primary_key=True)
    registration_number = Column(String, index=True)
    make = Column(String)
    model = Column(String)
    first_used_date = Column(String)
    fuel_type = Column(String)
    primary_colour = Column(String)
    registration_date = Column(String)
    manufacture_date = Column(String)
    engine_size = Column(Integer)
    mot_data = Column(Text)
    tax_status = Column(String)
    tax_due_date = Column(String)
    mot_status = Column(String)
    mot_expiry_date = Column(String)
    year_of_manufacture = Column(Integer)
    co2_emissions = Column(Integer)
    last_updated = Column(DateTime, default=datetime.utcnow)
    last_requested = Column(DateTime, default=datetime.utcnow)
    request_count = Column(Integer, default=0)
    historical_records = relationship("HistoricalRecord", back_populates="vehicle_cache")

def cache_vehicle_data(db, reg, data):
    vehicle = db.query(VehicleCache).filter(VehicleCache.registration_number == reg).first()
    
    if vehicle:
        # Update all fields including nested MOT data
        vehicle.make = data.get('make', vehicle.make)
        vehicle.model = data.get('model', vehicle.model)
        vehicle.first_used_date = data.get('firstUsedDate', vehicle.first_used_date)
        vehicle.fuel_type = data.get('fuelType', vehicle.fuel_type)
        vehicle.primary_colour = data.get('colour', vehicle.primary_colour)
        vehicle.registration_date = data.get('registrationDate', vehicle.registration_date)
        vehicle.manufacture_date = data.get('manufactureDate', vehicle.manufacture_date)
        vehicle.engine_size = data.get('engineCapacity', vehicle.engine_size)
        vehicle.tax_status = data.get('taxStatus', vehicle.tax_status)
        vehicle.tax_due_date = data.get('taxDueDate', vehicle.tax_due_date)
        vehicle.mot_status = data.get('motStatus', vehicle.mot_status)
        vehicle.mot_expiry_date = data.get('motExpiryDate', vehicle.mot_expiry_date)
        vehicle.year_of_manufacture = data.get('yearOfManufacture', vehicle.year_of_manufacture)
        vehicle.co2_emissions = data.get('co2Emissions', vehicle.co2_emissions)
        
        # Merge and update MOT data
        existing_mot_data = json.loads(vehicle.mot_data) if vehicle.mot_data else []
        new_mot_data = data.get('motTests', [])
        merged_mot_data = merge_mot_data(existing_mot_data, new_mot_data)
        vehicle.mot_data = json.dumps(merged_mot_data)
        
        vehicle.last_updated = datetime.utcnow()
        vehicle.last_requested = datetime.utcnow()
        vehicle.request_count += 1
    else:
        # Create new vehicle record
        vehicle = VehicleCache(
            registration_number=reg,
            make=data.get('make'),
            model=data.get('model'),
            first_used_date=data.get('firstUsedDate'),
            fuel_type=data.get('fuelType'),
            primary_colour=data.get('colour'),
            registration_date=data.get('registrationDate'),
            manufacture_date=data.get('manufactureDate'),
            engine_size=data.get('engineCapacity'),
            mot_data=json.dumps(data.get('motTests', [])),
            tax_status=data.get('taxStatus'),
            tax_due_date=data.get('taxDueDate'),
            mot_status=data.get('motStatus'),
            mot_expiry_date=data.get('motExpiryDate'),
            year_of_manufacture=data.get('yearOfManufacture'),
            co2_emissions=data.get('co2Emissions'),
            request_count=1
        )
        db.add(vehicle)

    db.commit()
    print(f"{'Updated' if vehicle else 'Created'} record for: {reg}")

def get_cached_vehicle_data(db, reg):
    vehicle = db.query(VehicleCache).filter(VehicleCache.registration_number == reg).first()
    if vehicle:
        # Check if cache is older than 1 day
        if (datetime.utcnow() - vehicle.last_updated).days >= 1:
            # Cache is stale, return None to trigger fresh lookup
            return None
        
        vehicle.last_requested = datetime.utcnow()
        vehicle.request_count += 1
        db.commit()
        data = {column.name: getattr(vehicle, column.name) for column in vehicle.__table__.columns}
        data['motTests'] = json.loads(data['mot_data'])
        return data
    return None

def get_mot_history(db, reg):
    vehicle = db.query(VehicleCache).filter(VehicleCache.registration_number == reg).first()
    if vehicle:
        data = json.loads(vehicle.mot_data)
        return data.get('motTests', [])
    return []

class HistoricalRecord(Base):
    __tablename__ = 'historical_records'
    id = Column(Integer, primary_key=True)
    vehicle_cache_id = Column(Integer, ForeignKey('vehicle_cache.id'))
    data = Column(String)
    recorded_at = Column(DateTime, default=datetime.utcnow)
    vehicle_cache = relationship("VehicleCache", back_populates="historical_records")

class RequestLog(Base):
    __tablename__ = 'request_logs'
    id = Column(Integer, primary_key=True)
    registration_number = Column(String, index=True)
    requester_ip = Column(String)
    user_agent = Column(String)
    referrer = Column(String)
    cf_country = Column(String)
    cf_region = Column(String)
    cf_city = Column(String)
    cf_timezone = Column(String)
    cf_isp = Column(String)
    local_timezone = Column(String)
    query_time = Column(Float)  # in seconds
    is_cached = Column(Boolean)
    requested_at = Column(DateTime, default=datetime.utcnow)
    headers = Column(Text)  # Store all headers as JSON

engine = create_engine('sqlite:///vehicle_cache.db')
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def merge_mot_data(existing_data, new_data):
    # Create a dictionary of existing MOT tests for easy lookup
    existing_dict = {test['completedDate']: test for test in existing_data}
    
    # Merge new data, updating or adding as necessary
    for new_test in new_data:
        existing_dict[new_test['completedDate']] = new_test
    
    # Convert back to list and sort by date (newest first)
    merged_data = list(existing_dict.values())
    merged_data.sort(key=lambda x: x['completedDate'], reverse=True)
    
    return merged_data

def update_vehicle_model(db, reg, model):
    vehicle = db.query(VehicleCache).filter(VehicleCache.registration_number == reg).first()
    if vehicle:
        vehicle.model = model
        db.commit()
        print(f"Updated model for {reg}: {model}")
        return True
    return False

def get_historical_data(db, reg):
    vehicle = db.query(VehicleCache).filter(VehicleCache.registration_number == reg).first()
    if vehicle:
        return [
            {
                "data": json.loads(record.data),
                "recorded_at": record.recorded_at.isoformat()
            }
            for record in vehicle.historical_records
        ]
    return []

def increment_request_count(db, reg):
    vehicle = db.query(VehicleCache).filter(VehicleCache.registration_number == reg).first()
    if vehicle:
        vehicle.request_count += 1
        vehicle.last_requested = datetime.utcnow()
        db.commit()

def get_request_count(db, reg):
    vehicle = db.query(VehicleCache).filter(VehicleCache.registration_number == reg).first()
    return vehicle.request_count if vehicle else 0

def check_cache_exists(db, reg):
    """Check if a registration exists in the vehicle_cache table."""
    return db.query(VehicleCache).filter(VehicleCache.registration_number == reg).first() is not None

def log_request(db, reg, request_data, query_time, is_cached):
    log_entry = RequestLog(
        registration_number=reg,
        requester_ip=request_data['cf_connecting_ip'],
        user_agent=request_data['user_agent'],
        referrer=request_data['referrer'],
        cf_country=request_data['cf_country'],
        cf_region=request_data['cf_region'],
        cf_city=request_data['cf_city'],
        cf_timezone=request_data['cf_timezone'],
        cf_isp=request_data['cf_isp'],
        local_timezone=request_data['local_timezone'],
        query_time=query_time,
        is_cached=is_cached,
        headers=json.dumps(request_data['headers'])
    )
    db.add(log_entry)
    increment_request_count(db, reg)
    db.commit()