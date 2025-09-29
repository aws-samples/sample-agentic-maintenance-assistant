import pandas as pd
import numpy as np
from scipy import signal
import random

class BearingFaultSimulator:
    """
    Realistic bearing fault simulation based on theme park ride mechanics
    
    Common theme park bearing faults:
    1. Outer Race Fault - Fixed defect, periodic impacts
    2. Inner Race Fault - Rotating defect, modulated impacts  
    3. Ball/Rolling Element Fault - Double impacts per revolution
    4. Cage Fault - Low frequency modulation
    """
    
    def __init__(self, baseline_data_path='vibration_data.csv'):
        self.baseline_data = pd.read_csv(baseline_data_path)
        self.sample_rate = 100  # Hz
        self.ride_counter = 0
        
        # Bearing parameters for typical theme park ride
        self.bearing_params = {
            'shaft_speed': 25,  # RPM (typical ride speed)
            'ball_count': 8,    # Number of rolling elements
            'contact_angle': 0, # Degrees
            'pitch_diameter': 50, # mm
            'ball_diameter': 8    # mm
        }
        
        # Calculate characteristic frequencies
        self._calculate_fault_frequencies()
        
    def _calculate_fault_frequencies(self):
        """Calculate bearing characteristic fault frequencies"""
        rpm = self.bearing_params['shaft_speed']
        nb = self.bearing_params['ball_count']
        
        # Simplified calculations for demonstration
        self.fault_frequencies = {
            'outer_race': rpm * nb / 60 * 0.4,    # ~3.3 Hz
            'inner_race': rpm * nb / 60 * 0.6,    # ~5.0 Hz  
            'ball_fault': rpm * nb / 60 * 0.8,    # ~6.7 Hz
            'cage_fault': rpm / 60 * 0.4          # ~0.17 Hz
        }
        
    def simulate_normal_ride(self):
        """Generate normal ride with minimal bearing noise"""
        self.ride_counter += 1
        ride_data = self.baseline_data.copy()
        
        # Add minimal random noise (healthy bearing)
        noise_level = 0.02
        ride_data['accel_x'] += np.random.normal(0, noise_level, len(ride_data))
        ride_data['accel_y'] += np.random.normal(0, noise_level, len(ride_data))
        ride_data['accel_z'] += np.random.normal(0, noise_level, len(ride_data))
        
        ride_data['ride_id'] = self.ride_counter
        ride_data['fault_type'] = 'NORMAL'
        
        return ride_data
    
    def simulate_outer_race_fault(self, severity=0.3):
        """
        Outer race fault: Fixed defect causes periodic impacts
        - High frequency impacts at outer race frequency
        - Amplitude modulation due to load zone
        """
        self.ride_counter += 1
        ride_data = self.baseline_data.copy()
        
        t = ride_data['timestamp'].values
        freq = self.fault_frequencies['outer_race']
        
        # Generate periodic impulses
        impulse_train = severity * np.sin(2 * np.pi * freq * t)
        
        # Add harmonics for realism
        impulse_train += severity * 0.3 * np.sin(2 * np.pi * freq * 2 * t)
        impulse_train += severity * 0.1 * np.sin(2 * np.pi * freq * 3 * t)
        
        # Amplitude modulation (load zone effect)
        modulation = 1 + 0.2 * np.sin(2 * np.pi * 0.5 * t)
        impulse_train *= modulation
        
        # Apply to accelerometer data (mainly radial direction)
        ride_data['accel_x'] += impulse_train * 0.7
        ride_data['accel_y'] += impulse_train * 0.5
        ride_data['accel_z'] += impulse_train * 0.2
        
        # Add normal noise
        noise = np.random.normal(0, 0.02, len(ride_data))
        ride_data['accel_x'] += noise
        ride_data['accel_y'] += noise
        ride_data['accel_z'] += noise
        
        ride_data['ride_id'] = self.ride_counter
        ride_data['fault_type'] = 'OUTER_RACE_FAULT'
        
        return ride_data
    
    def simulate_inner_race_fault(self, severity=0.4):
        """
        Inner race fault: Rotating defect with load modulation
        - Higher frequency than outer race
        - Strong amplitude modulation
        """
        self.ride_counter += 1
        ride_data = self.baseline_data.copy()
        
        t = ride_data['timestamp'].values
        freq = self.fault_frequencies['inner_race']
        
        # Generate fault signature
        fault_signal = severity * np.sin(2 * np.pi * freq * t)
        
        # Strong amplitude modulation (rotating through load zone)
        shaft_freq = self.bearing_params['shaft_speed'] / 60
        modulation = 1 + 0.5 * np.sin(2 * np.pi * shaft_freq * t)
        fault_signal *= modulation
        
        # Add harmonics
        fault_signal += severity * 0.4 * np.sin(2 * np.pi * freq * 2 * t) * modulation
        
        # Apply to all axes (inner race affects all directions)
        ride_data['accel_x'] += fault_signal * 0.8
        ride_data['accel_y'] += fault_signal * 0.9
        ride_data['accel_z'] += fault_signal * 0.3
        
        # Add noise
        noise = np.random.normal(0, 0.03, len(ride_data))
        ride_data['accel_x'] += noise
        ride_data['accel_y'] += noise
        ride_data['accel_z'] += noise
        
        ride_data['ride_id'] = self.ride_counter
        ride_data['fault_type'] = 'INNER_RACE_FAULT'
        
        return ride_data
    
    def simulate_ball_fault(self, severity=0.35):
        """
        Ball/rolling element fault: Double impacts per revolution
        - Characteristic double-peak signature
        - Varies with ball position in load zone
        """
        self.ride_counter += 1
        ride_data = self.baseline_data.copy()
        
        t = ride_data['timestamp'].values
        freq = self.fault_frequencies['ball_fault']
        
        # Generate double-impact signature
        fault_signal = severity * (np.sin(2 * np.pi * freq * t) + 
                                 0.6 * np.sin(2 * np.pi * freq * t + np.pi/4))
        
        # Modulation as ball moves through load zone
        cage_freq = self.fault_frequencies['cage_fault']
        modulation = 1 + 0.3 * np.sin(2 * np.pi * cage_freq * t)
        fault_signal *= modulation
        
        # Apply primarily to radial directions
        ride_data['accel_x'] += fault_signal * 0.6
        ride_data['accel_y'] += fault_signal * 0.7
        ride_data['accel_z'] += fault_signal * 0.1
        
        # Add noise
        noise = np.random.normal(0, 0.025, len(ride_data))
        ride_data['accel_x'] += noise
        ride_data['accel_y'] += noise
        ride_data['accel_z'] += noise
        
        ride_data['ride_id'] = self.ride_counter
        ride_data['fault_type'] = 'BALL_FAULT'
        
        return ride_data
    
    def simulate_cage_fault(self, severity=0.25):
        """
        Cage fault: Low frequency modulation of overall vibration
        - Cage frequency modulation
        - Affects all bearing frequencies
        """
        self.ride_counter += 1
        ride_data = self.baseline_data.copy()
        
        t = ride_data['timestamp'].values
        cage_freq = self.fault_frequencies['cage_fault']
        
        # Low frequency modulation
        modulation = 1 + severity * np.sin(2 * np.pi * cage_freq * t)
        
        # Apply modulation to existing vibration
        ride_data['accel_x'] *= modulation
        ride_data['accel_y'] *= modulation
        ride_data['accel_z'] *= modulation
        
        # Add cage-specific low frequency component
        cage_signal = severity * 0.5 * np.sin(2 * np.pi * cage_freq * t)
        ride_data['accel_x'] += cage_signal
        ride_data['accel_y'] += cage_signal
        ride_data['accel_z'] += cage_signal * 0.5
        
        # Add noise
        noise = np.random.normal(0, 0.02, len(ride_data))
        ride_data['accel_x'] += noise
        ride_data['accel_y'] += noise
        ride_data['accel_z'] += noise
        
        ride_data['ride_id'] = self.ride_counter
        ride_data['fault_type'] = 'CAGE_FAULT'
        
        return ride_data
    
    def generate_fault_dataset(self, samples_per_class=50):
        """Generate balanced dataset for training"""
        dataset = []
        
        print("Generating bearing fault dataset...")
        
        # Generate samples for each class
        fault_types = [
            ('normal', self.simulate_normal_ride),
            ('outer_race', lambda: self.simulate_outer_race_fault(random.uniform(0.2, 0.5))),
            ('inner_race', lambda: self.simulate_inner_race_fault(random.uniform(0.3, 0.6))),
            ('ball_fault', lambda: self.simulate_ball_fault(random.uniform(0.2, 0.4))),
            ('cage_fault', lambda: self.simulate_cage_fault(random.uniform(0.1, 0.3)))
        ]
        
        for fault_name, fault_func in fault_types:
            print(f"   Generating {samples_per_class} {fault_name} samples...")
            for _ in range(samples_per_class):
                ride_data = fault_func()
                dataset.append(ride_data)
        
        print(f"Generated {len(dataset)} total samples")
        return dataset

def main():
    simulator = BearingFaultSimulator()
    
    # Generate sample of each fault type
    print("Bearing Fault Simulation Demo")
    print("=" * 40)
    
    faults = [
        ("Normal", simulator.simulate_normal_ride()),
        ("Outer Race", simulator.simulate_outer_race_fault()),
        ("Inner Race", simulator.simulate_inner_race_fault()),
        ("Ball Fault", simulator.simulate_ball_fault()),
        ("Cage Fault", simulator.simulate_cage_fault())
    ]
    
    for name, data in faults:
        magnitude = np.sqrt(data['accel_x']**2 + data['accel_y']**2 + data['accel_z']**2)
        print(f"{name:12} | Max: {magnitude.max():.2f} | RMS: {np.sqrt(np.mean(magnitude**2)):.2f}")
    
    return simulator

if __name__ == "__main__":
    simulator = main()