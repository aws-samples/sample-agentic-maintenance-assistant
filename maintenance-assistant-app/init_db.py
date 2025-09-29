#!/usr/bin/env python3
from models import create_tables, get_db, AssetType, Asset, MapConfig, Simulator

def initialize_database():
    """Initialize database with sample data"""
    print("Initializing database...")
    
    # Create tables
    create_tables()
    
    db = get_db()
    
    # Create default simulator
    ride_simulator = Simulator(
        name="Theme Park Ride Simulator",
        class_name="RideSimulator",
        description="Simulator for industrial equipment rides"
    )
    db.add(ride_simulator)
    db.commit()
    
    # Create default asset type
    roller_coaster = AssetType(
        name="Roller Coaster",
        description="High-speed theme park ride with complex mechanical systems",
        simulator_id=ride_simulator.id
    )
    db.add(roller_coaster)
    db.commit()
    
    # Create default map config
    default_map = MapConfig(
        name="Theme Park Map",
        image_path="/assets/Theme_park_map.jpeg",
        is_active=True,
        width=1200,
        height=800
    )
    db.add(default_map)
    db.commit()
    
    # Create sample asset
    main_ride = Asset(
        name="Main Roller Coaster",
        asset_type_id=roller_coaster.id,
        map_x=910.8910891089109,  # 910.8910891089109, 295.4848921517992 are the co-ords that look good
        map_y=295.4848921517992,
        map_width=80,
        map_height=60,
        status="active"
    )
    db.add(main_ride)
    db.commit()
    
    print("  Database initialized with sample data")
    print(f"   - Simulator: {ride_simulator.name}")
    print(f"   - Asset Type: {roller_coaster.name}")
    print(f"   - Asset: {main_ride.name}")
    print(f"   - Map: {default_map.name}")

if __name__ == "__main__":
    initialize_database()