import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
import os

class RideAnomalyDetector:
    def __init__(self):
        self.scaler = StandardScaler()
        self.anomaly_model = IsolationForest(contamination=0.1, random_state=42)
        self.is_trained = False
        
    def extract_features(self, df):
        """Extract key features from vibration data"""
        # Calculate magnitude
        magnitude = np.sqrt(df['accel_x']**2 + df['accel_y']**2 + df['accel_z']**2)
        
        features = {
            'mean_magnitude': magnitude.mean(),
            'std_magnitude': magnitude.std(),
            'max_magnitude': magnitude.max(),
            'min_magnitude': magnitude.min(),
            'mean_x': df['accel_x'].mean(),
            'std_x': df['accel_x'].std(),
            'mean_y': df['accel_y'].mean(), 
            'std_y': df['accel_y'].std(),
            'mean_z': df['accel_z'].mean(),
            'std_z': df['accel_z'].std(),
            'peak_count': (magnitude > magnitude.quantile(0.95)).sum(),
            'smoothness_x': np.mean(np.abs(np.diff(df['accel_x']))),
            'smoothness_y': np.mean(np.abs(np.diff(df['accel_y']))),
            'smoothness_z': np.mean(np.abs(np.diff(df['accel_z'])))
        }
        
        return pd.Series(features)
    
    def train(self, baseline_data, n_simulations=50):
        """Train anomaly detector on normal ride variations"""
        print("Training Anomaly Detection Model...")
        
        # Generate training data from baseline
        training_features = []
        
        for i in range(n_simulations):
            # Add small random variations to simulate normal ride-to-ride differences
            noise_factor = np.random.normal(0, 0.05)  # 5% variation
            
            simulated_ride = baseline_data.copy()
            simulated_ride['accel_x'] += np.random.normal(0, 0.1, len(simulated_ride))
            simulated_ride['accel_y'] += np.random.normal(0, 0.1, len(simulated_ride)) 
            simulated_ride['accel_z'] += np.random.normal(0, 0.1, len(simulated_ride))
            
            features = self.extract_features(simulated_ride)
            training_features.append(features)
        
        # Convert to DataFrame and train
        X = pd.DataFrame(training_features)
        X_scaled = self.scaler.fit_transform(X)
        
        self.anomaly_model.fit(X_scaled)
        self.is_trained = True
        
        print(f"Model trained on {n_simulations} simulated normal rides")
        return X
    
    def detect_anomaly(self, ride_data):
        """Detect if a ride shows anomalous behavior"""
        if not self.is_trained:
            raise ValueError("Model not trained yet!")
        
        # Extract features
        features = self.extract_features(ride_data)
        X = features.values.reshape(1, -1)
        X_scaled = self.scaler.transform(X)
        
        # Predict
        anomaly_score = self.anomaly_model.decision_function(X_scaled)[0]
        is_anomaly = self.anomaly_model.predict(X_scaled)[0] == -1
        
        # Calculate confidence (distance from decision boundary)
        confidence = abs(anomaly_score)
        
        return {
            'is_anomaly': is_anomaly,
            'anomaly_score': anomaly_score,
            'confidence': confidence,
            'features': features.to_dict(),
            'status': 'ANOMALY DETECTED' if is_anomaly else 'NORMAL'
        }
    
    def save_model(self, path='models/'):
        """Save trained model"""
        os.makedirs(path, exist_ok=True)
        joblib.dump(self.scaler, f'{path}/anomaly_scaler.pkl')
        joblib.dump(self.anomaly_model, f'{path}/anomaly_model.pkl')
        print(f"Anomaly model saved to {path}")
    
    def load_model(self, path='models/'):
        """Load trained model"""
        self.scaler = joblib.load(f'{path}/anomaly_scaler.pkl')
        self.anomaly_model = joblib.load(f'{path}/anomaly_model.pkl')
        self.is_trained = True
        print(f"Anomaly model loaded from {path}")

def main():
    # Load baseline ride data
    baseline_data = pd.read_csv('vibration_data.csv')
    
    # Initialize and train detector
    detector = RideAnomalyDetector()
    training_data = detector.train(baseline_data)
    
    # Test on baseline data (should be normal)
    result = detector.detect_anomaly(baseline_data)
    
    print(f"\nBASELINE RIDE ANALYSIS:")
    print(f"   Status: {result['status']}")
    print(f"   Anomaly Score: {result['anomaly_score']:.3f}")
    print(f"   Confidence: {result['confidence']:.3f}")
    
    # Save model
    detector.save_model()
    
    return detector

if __name__ == "__main__":
    detector = main()