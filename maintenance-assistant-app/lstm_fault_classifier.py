import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import EarlyStopping
import joblib
import os

class LSTMFaultClassifier:
    """
    LSTM-based bearing fault classifier for theme park rides
    Uses time-series vibration data to classify bearing conditions
    """
    
    def __init__(self, sequence_length=100, n_features=3):
        self.sequence_length = sequence_length  # 1 second at 100Hz
        self.n_features = n_features  # x, y, z accelerations
        self.model = None
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
        self.is_trained = False
        
    def prepare_sequences(self, data_list):
        """Convert ride data to LSTM sequences"""
        sequences = []
        labels = []
        
        for ride_data in data_list:
            # Extract accelerometer data
            accel_data = ride_data[['accel_x', 'accel_y', 'accel_z']].values
            fault_type = ride_data['fault_type'].iloc[0]
            
            # Create overlapping sequences
            for i in range(0, len(accel_data) - self.sequence_length + 1, 50):  # 50% overlap
                sequence = accel_data[i:i + self.sequence_length]
                sequences.append(sequence)
                labels.append(fault_type)
        
        return np.array(sequences), np.array(labels)
    
    def build_model(self, n_classes):
        """Build LSTM model architecture"""
        model = Sequential([
            # First LSTM layer
            LSTM(64, return_sequences=True, input_shape=(self.sequence_length, self.n_features)),
            BatchNormalization(),
            Dropout(0.3),
            
            # Second LSTM layer
            LSTM(32, return_sequences=False),
            BatchNormalization(),
            Dropout(0.3),
            
            # Dense layers
            Dense(32, activation='relu'),
            Dropout(0.2),
            Dense(16, activation='relu'),
            Dense(n_classes, activation='softmax')
        ])
        
        model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss='sparse_categorical_crossentropy',
            metrics=['accuracy']
        )
        
        return model
    
    def train(self, dataset, validation_split=0.2, epochs=50):
        """Train the LSTM classifier"""
        print("🧠 Training LSTM Fault Classifier...")
        
        # Prepare sequences
        X, y = self.prepare_sequences(dataset)
        print(f"   Created {len(X)} sequences of length {self.sequence_length}")
        
        # Encode labels
        y_encoded = self.label_encoder.fit_transform(y)
        n_classes = len(self.label_encoder.classes_)
        
        print(f"   Classes: {list(self.label_encoder.classes_)}")
        
        # Scale features
        X_reshaped = X.reshape(-1, self.n_features)
        X_scaled = self.scaler.fit_transform(X_reshaped)
        X_scaled = X_scaled.reshape(X.shape)
        
        # Split data
        X_train, X_val, y_train, y_val = train_test_split(
            X_scaled, y_encoded, test_size=validation_split, 
            random_state=42, stratify=y_encoded
        )
        
        # Build model
        self.model = self.build_model(n_classes)
        
        # Training callbacks
        early_stopping = EarlyStopping(
            monitor='val_accuracy', patience=10, restore_best_weights=True
        )
        
        # Train model
        history = self.model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=epochs,
            batch_size=32,
            callbacks=[early_stopping],
            verbose=1
        )
        
        # Evaluate
        val_pred = self.model.predict(X_val)
        val_pred_classes = np.argmax(val_pred, axis=1)
        
        print("\nValidation Results:")
        print(classification_report(y_val, val_pred_classes, 
                                  target_names=self.label_encoder.classes_))
        
        self.is_trained = True
        return history
    
    def predict_ride(self, ride_data):
        """Predict fault type for a single ride"""
        if not self.is_trained:
            raise ValueError("Model not trained yet!")
        
        # Extract accelerometer data
        accel_data = ride_data[['accel_x', 'accel_y', 'accel_z']].values
        
        # Create sequences
        sequences = []
        for i in range(0, len(accel_data) - self.sequence_length + 1, self.sequence_length):
            sequence = accel_data[i:i + self.sequence_length]
            sequences.append(sequence)
        
        if len(sequences) == 0:
            # Handle short rides
            if len(accel_data) >= self.sequence_length:
                sequences = [accel_data[:self.sequence_length]]
            else:
                # Pad short sequences
                padded = np.zeros((self.sequence_length, self.n_features))
                padded[:len(accel_data)] = accel_data
                sequences = [padded]
        
        X = np.array(sequences)
        
        # Scale features
        X_reshaped = X.reshape(-1, self.n_features)
        X_scaled = self.scaler.transform(X_reshaped)
        X_scaled = X_scaled.reshape(X.shape)
        
        # Predict
        predictions = self.model.predict(X_scaled, verbose=0)
        
        # Average predictions across sequences
        avg_prediction = np.mean(predictions, axis=0)
        predicted_class = np.argmax(avg_prediction)
        confidence = avg_prediction[predicted_class]
        
        fault_type = self.label_encoder.inverse_transform([predicted_class])[0]
        
        return {
            'fault_type': fault_type,
            'confidence': float(confidence),
            'probabilities': {
                class_name: float(prob) 
                for class_name, prob in zip(self.label_encoder.classes_, avg_prediction)
            },
            'is_healthy': fault_type == 'NORMAL',
            'severity': 'LOW' if confidence < 0.7 else 'MEDIUM' if confidence < 0.9 else 'HIGH'
        }
    
    def save_model(self, path='models/'):
        """Save trained model and preprocessors"""
        os.makedirs(path, exist_ok=True)
        
        self.model.save(os.path.join(path, 'lstm_fault_model.h5'))
        joblib.dump(self.scaler, os.path.join(path, 'lstm_scaler.pkl'))
        joblib.dump(self.label_encoder, os.path.join(path, 'lstm_label_encoder.pkl'))
        
        # Save metadata
        metadata = {
            'sequence_length': self.sequence_length,
            'n_features': self.n_features,
            'classes': list(self.label_encoder.classes_)
        }
        joblib.dump(metadata, f'{path}/lstm_metadata.pkl')
        
        print(f"LSTM model saved to {path}")
    
    def load_model(self, path='models/'):
        """Load trained model and preprocessors"""
        self.model = tf.keras.models.load_model(f'{path}/lstm_fault_model.h5')
        self.scaler = joblib.load(f'{path}/lstm_scaler.pkl')
        self.label_encoder = joblib.load(f'{path}/lstm_label_encoder.pkl')
        
        metadata = joblib.load(f'{path}/lstm_metadata.pkl')
        self.sequence_length = metadata['sequence_length']
        self.n_features = metadata['n_features']
        
        self.is_trained = True
        print(f"LSTM model loaded from {path}")

def main():
    """Demo the LSTM classifier"""
    from bearing_fault_simulator import BearingFaultSimulator
    
    print("LSTM Bearing Fault Classification Demo")
    print("=" * 50)
    
    # Generate training data
    simulator = BearingFaultSimulator()
    dataset = simulator.generate_fault_dataset(samples_per_class=20)  # Small for demo
    
    # Train classifier
    classifier = LSTMFaultClassifier()
    history = classifier.train(dataset, epochs=20)  # Reduced for demo
    
    # Test on new samples
    print("\n🧪 Testing on new samples:")
    test_samples = [
        ("Normal", simulator.simulate_normal_ride()),
        ("Outer Race", simulator.simulate_outer_race_fault()),
        ("Inner Race", simulator.simulate_inner_race_fault()),
        ("Ball Fault", simulator.simulate_ball_fault())
    ]
    
    for name, ride_data in test_samples:
        result = classifier.predict_ride(ride_data)
        print(f"{name:12} | Predicted: {result['fault_type']:15} | Confidence: {result['confidence']:.3f}")
    
    # Save model
    classifier.save_model()
    
    return classifier

if __name__ == "__main__":
    classifier = main()