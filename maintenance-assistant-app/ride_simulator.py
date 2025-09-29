import pandas as pd
import numpy as np
from datetime import datetime
import random
from bearing_fault_simulator import BearingFaultSimulator

class RideSimulator:
    """Ride simulator with realistic bearing fault simulation"""
    
    def __init__(self, baseline_data_path='vibration_data.csv'):
        self.bearing_simulator = BearingFaultSimulator(baseline_data_path)
        self.ride_counter = 0
        
        # Theme park specific fault probabilities
        self.fault_probabilities = {
            'NORMAL': 0.70,           # 70% normal operation
            'OUTER_RACE_FAULT': 0.12, # 12% outer race issues
            'INNER_RACE_FAULT': 0.08, # 8% inner race issues  
            'BALL_FAULT': 0.06,       # 6% ball/element issues
            'CAGE_FAULT': 0.04        # 4% cage issues
        }
        
        print(f"   Ride Simulator Ready")
        print(f"   Fault probabilities: {self.fault_probabilities}")
    
    def run_ride_cycle(self, force_fault_type=None):
        """Run a single ride cycle with realistic fault distribution"""
        
        print(f"\n  Starting Enhanced Ride Cycle #{self.ride_counter + 1}")
        print("   Launching Theme Park Ride...")
        
        # Determine fault type
        if force_fault_type:
            fault_type = force_fault_type
        else:
            fault_type = np.random.choice(
                list(self.fault_probabilities.keys()),
                p=list(self.fault_probabilities.values())
            )
        
        # Generate ride data based on fault type
        if fault_type == 'NORMAL':
            print("     Normal bearing conditions")
            ride_data = self.bearing_simulator.simulate_normal_ride()
            
        elif fault_type == 'OUTER_RACE_FAULT':
            severity = random.uniform(0.2, 0.5)
            print(f"      Outer race fault detected (severity: {severity:.2f})")
            ride_data = self.bearing_simulator.simulate_outer_race_fault(severity)
            
        elif fault_type == 'INNER_RACE_FAULT':
            severity = random.uniform(0.3, 0.6)
            print(f"      Inner race fault detected (severity: {severity:.2f})")
            ride_data = self.bearing_simulator.simulate_inner_race_fault(severity)
            
        elif fault_type == 'BALL_FAULT':
            severity = random.uniform(0.2, 0.4)
            print(f"      Ball/element fault detected (severity: {severity:.2f})")
            ride_data = self.bearing_simulator.simulate_ball_fault(severity)
            
        elif fault_type == 'CAGE_FAULT':
            severity = random.uniform(0.1, 0.3)
            print(f"      Cage fault detected (severity: {severity:.2f})")
            ride_data = self.bearing_simulator.simulate_cage_fault(severity)
        
        # Add metadata
        ride_data['timestamp_real'] = datetime.now().isoformat()
        
        print(f"     Ride completed - Duration: {ride_data['timestamp'].max():.1f}s")
        
        return ride_data
    
    def get_ride_summary(self, ride_data):
        """Get comprehensive ride summary"""
        magnitude = np.sqrt(ride_data['accel_x']**2 + ride_data['accel_y']**2 + ride_data['accel_z']**2)
        
        summary = {
            'ride_id': ride_data['ride_id'].iloc[0],
            'fault_type': ride_data['fault_type'].iloc[0],
            'duration': ride_data['timestamp'].max(),
            'max_acceleration': magnitude.max(),
            'rms_acceleration': np.sqrt(np.mean(magnitude**2)),
            'peak_events': (magnitude > magnitude.quantile(0.95)).sum(),
            'timestamp': ride_data['timestamp_real'].iloc[0],
            'is_faulty': ride_data['fault_type'].iloc[0] != 'NORMAL'
        }
        
        return summary
    
    def generate_fault_specific_ride(self, fault_type):
        """Generate a ride with specific fault type for testing"""
        return self.run_ride_cycle(force_fault_type=fault_type)

def demo_enhanced_simulator():
    """Demo the enhanced simulator"""
    print("  ENHANCED RIDE SIMULATOR DEMO")
    print("=" * 50)
    
    simulator = RideSimulator()
    
    # Test each fault type
    fault_types = ['NORMAL', 'OUTER_RACE_FAULT', 'INNER_RACE_FAULT', 'BALL_FAULT', 'CAGE_FAULT']
    
    results = []
    for fault_type in fault_types:
        ride_data = simulator.generate_fault_specific_ride(fault_type)
        summary = simulator.get_ride_summary(ride_data)
        results.append((fault_type, summary))
        
        print(f"   {fault_type:18} | RMS: {summary['rms_acceleration']:.3f} | Max: {summary['max_acceleration']:.2f}")
    
    print(f"\n  Demo complete - {len(results)} fault types tested")
    return simulator, results

if __name__ == "__main__":
    simulator, results = demo_enhanced_simulator()