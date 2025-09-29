from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd
import numpy as np
import os
import json
from datetime import datetime
from scipy import signal
from ride_simulator import RideSimulator
from lstm_fault_classifier import LSTMFaultClassifier
from functools import wraps

def get_runtime_config_path():
    """Get the path to runtime_config.json relative to the current script"""
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(parent_dir, 'runtime_config.json')

def verify_user_token(token):
    """Verify JWT token and extract user information"""
    try:
        import jwt
        from jwt import PyJWKClient
        import ssl
        
        # Load runtime config
        with open(get_runtime_config_path(), 'r') as f:
            runtime_config = json.load(f)
        
        user_pool_id = runtime_config.get('USER_POOL_ID')
        user_app_client_id = runtime_config.get('USER_APP_CLIENT_ID')
        region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
        
        if not user_pool_id or not user_app_client_id:
            print("Missing User Pool ID or Client ID in runtime config")
            return None
        
        # Get JWT signing keys
        jwks_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
        
        # Create JWKS client with SSL context that doesn't verify certificates (for development)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        jwks_client = PyJWKClient(jwks_url, ssl_context=ssl_context)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        
        # Decode and verify token
        decoded_token = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=user_app_client_id,
            issuer=f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        )
        
        return decoded_token
        
    except Exception as e:
        print(f"Error verifying user token: {e}")
        return None

def check_user_permissions(user_info, required_groups):
    """Check if user has required group membership"""
    if not user_info:
        return False
    
    user_groups = user_info.get('cognito:groups', [])
    return any(group in user_groups for group in required_groups)

def require_auth(required_groups=None):
    """Authentication decorator with optional group requirements"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization', '')
            
            if not auth_header.startswith('Bearer '):
                return jsonify({'error': 'Authentication required'}), 401
            
            token = auth_header.replace('Bearer ', '')
            user_info = verify_user_token(token)
            
            if not user_info:
                return jsonify({'error': 'Invalid or expired token'}), 401
            
            # Check group permissions if required
            if required_groups:
                user_groups = user_info.get('cognito:groups', [])
                # Allow users without groups for testing (remove in production)
                if not user_groups:
                    print(f"Warning: User {user_info.get('email')} has no groups assigned, allowing access for testing")
                elif not check_user_permissions(user_info, required_groups):
                    print(f"User {user_info.get('email')} has groups {user_groups} but needs {required_groups}")
                    return jsonify({'error': 'Insufficient permissions'}), 403
            
            # Add user context to request
            request.user = user_info
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def create_audit_log_entry(user_info, action, details=None):
    """Create audit log entry for user actions"""
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'user_email': user_info.get('email', 'unknown'),
        'user_id': user_info.get('sub', 'unknown'),
        'user_groups': user_info.get('cognito:groups', []),
        'action': action,
        'details': details or {}
    }
    
    # Log to console (in production, send to CloudWatch)
    print(f"AUDIT: {json.dumps(log_entry)}")
    return log_entry

app = Flask(__name__)
CORS(app)

# Store alerts in memory (in production, use a database)
active_alerts = []

# Initialize system
simulator = RideSimulator()
classifier = LSTMFaultClassifier()

# Check if trained model exists
model_path = 'models/'
if os.path.exists(f'{model_path}lstm_fault_model.h5'):
    try:
        classifier.load_model(model_path)
        print("Loaded pre-trained LSTM model")
    except:
        print("WARNING: Failed to load model, will train on first request")
else:
    print("No pre-trained model found, will train on first request")

@app.route('/api/train-model', methods=['POST'])
@require_auth(['Administrators'])
def train_model():
    """Train the LSTM model with bearing fault data"""
    try:
        print("🧠 Training LSTM model...")
        
        # Generate training dataset
        dataset = simulator.bearing_simulator.generate_fault_dataset(samples_per_class=30)
        
        # Train classifier
        classifier.train(dataset, epochs=30)
        classifier.save_model()
        
        return jsonify({
            'success': True,
            'message': 'LSTM model trained successfully',
            'classes': list(classifier.label_encoder.classes_)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/simulate-ride', methods=['POST'])
@require_auth(['Administrators', 'Operators'])
def simulate_ride():
    """Run ride simulation with LSTM analysis"""
    try:
        data = request.get_json() or {}
        force_fault = data.get('force_fault_type', None)
        asset_id = data.get('asset_id', None)  # Allow specifying which asset to simulate
        
        # If no asset_id provided, get the first available asset
        if not asset_id:
            try:
                from models import get_db, Asset
                db = get_db()
                first_asset = db.query(Asset).first()
                asset_id = first_asset.id if first_asset else 1
                db.close()
            except:
                asset_id = 1  # Fallback
        
        # Run simulation
        ride_data = simulator.run_ride_cycle(force_fault)
        ride_summary = simulator.get_ride_summary(ride_data)
        
        # Add asset_id to the response
        ride_data['asset_id'] = asset_id
        
        # Analyze with LSTM if trained
        if classifier.is_trained:
            lstm_result = classifier.predict_ride(ride_data)
            
            # Create alert if fault detected
            if not lstm_result['is_healthy'] and lstm_result['confidence'] > 0.6:
                create_alert(
                    asset_id=asset_id,  # Use the asset_id from the simulation request
                    fault_type=lstm_result['fault_type'],
                    confidence=lstm_result['confidence'],
                    severity=lstm_result['severity']
                )
        else:
            lstm_result = {
                'fault_type': 'MODEL_NOT_TRAINED',
                'confidence': 0.0,
                'probabilities': {},
                'is_healthy': True,
                'severity': 'UNKNOWN'
            }
        
        # Prepare chart data
        magnitude = np.sqrt(ride_data['accel_x']**2 + ride_data['accel_y']**2 + ride_data['accel_z']**2)
        chart_data = {
            'timestamps': ride_data['timestamp'].tolist()[::120],  # Every 1.2s
            'magnitude': magnitude.tolist()[::120]
        }
        
        # Generate frequency domain data
        try:
            # Convert pandas Series to numpy array
            magnitude_array = magnitude.values if hasattr(magnitude, 'values') else magnitude
            
            fs = 100  # 100 Hz sampling rate
            f, psd = signal.welch(magnitude_array, fs, nperseg=256)
            
            frequency_data = [{'frequency': float(freq), 'power': float(10*np.log10(max(power, 1e-12)))} 
                             for freq, power in zip(f, psd) if freq <= 25]
            print(f"Generated {len(frequency_data)} frequency points")
        except Exception as freq_error:
            print(f"Frequency analysis error: {freq_error}")
            frequency_data = []
        
        # Identify fault frequencies based on fault type
        fault_frequencies = []
        if ride_summary['fault_type'] == 'OUTER_RACE_FAULT':
            fault_frequencies = [3.3, 6.6, 9.9]
        elif ride_summary['fault_type'] == 'INNER_RACE_FAULT':
            fault_frequencies = [5.0, 10.0, 15.0]
        elif ride_summary['fault_type'] == 'BALL_FAULT':
            fault_frequencies = [6.7, 13.4]
        elif ride_summary['fault_type'] == 'CAGE_FAULT':
            fault_frequencies = [0.17, 0.34]
        
        print(f"Generated {len(frequency_data)} frequency points, fault frequencies: {fault_frequencies}")
        
        # Create audit log
        create_audit_log_entry(request.user, 'ride_simulation', {
            'ride_id': int(ride_summary['ride_id']),
            'actual_fault_type': ride_summary['fault_type'],
            'predicted_fault_type': lstm_result['fault_type'],
            'prediction_correct': ride_summary['fault_type'] == lstm_result['fault_type'],
            'confidence': float(lstm_result['confidence'])
        })
        
        return jsonify({
            'success': True,
            'ride_id': int(ride_summary['ride_id']),
            'actual_fault_type': ride_summary['fault_type'],
            'duration': float(ride_summary['duration']),
            'max_gforce': float(ride_summary['max_acceleration'] / 9.81),
            'rms_acceleration': float(ride_summary['rms_acceleration']),
            'is_actually_faulty': ride_summary['is_faulty'],
            
            # LSTM Analysis Results
            'predicted_fault_type': lstm_result['fault_type'],
            'prediction_confidence': float(lstm_result['confidence']),
            'fault_probabilities': lstm_result['probabilities'],
            'is_predicted_healthy': lstm_result['is_healthy'],
            'fault_severity': lstm_result['severity'],
            
            # Performance metrics
            'prediction_correct': ride_summary['fault_type'] == lstm_result['fault_type'],
            
            'chart_data': chart_data,
            'frequency_data': frequency_data,
            'fault_frequencies': fault_frequencies
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/status')
@require_auth(['Administrators', 'Operators', 'Viewers'])
def status():
    """Get system status"""
    return jsonify({
        'simulator_ready': True,
        'lstm_trained': classifier.is_trained,
        'total_rides': simulator.ride_counter,
        'fault_types': list(simulator.fault_probabilities.keys()),
        'model_classes': list(classifier.label_encoder.classes_) if classifier.is_trained else []
    })

@app.route('/api/baseline-data')
@require_auth(['Administrators', 'Operators', 'Viewers'])
def baseline_data():
    """Get baseline normal ride data for comparison"""
    try:
        # Load original vibration data
        original_data = pd.read_csv('vibration_data.csv')
        original_magnitude = np.sqrt(original_data['accel_x']**2 + original_data['accel_y']**2 + original_data['accel_z']**2)
        
        # Time domain chart data
        chart_data = {
            'timestamps': original_data['timestamp'].tolist()[::120],
            'magnitude': original_magnitude.tolist()[::120]
        }
        
        # Frequency domain data for original baseline
        try:
            fs = 100
            f, psd = signal.welch(original_magnitude.values, fs, nperseg=256)
            baseline_frequency_data = [{'frequency': float(freq), 'power': float(10*np.log10(max(power, 1e-12)))} 
                                     for freq, power in zip(f, psd) if freq <= 25]
        except Exception as freq_error:
            print(f"Baseline frequency error: {freq_error}")
            baseline_frequency_data = []
        
        return jsonify({
            'success': True,
            'chart_data': chart_data,
            'frequency_data': baseline_frequency_data,
            'fault_type': 'NORMAL'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/fault-info')
@require_auth(['Administrators', 'Operators', 'Viewers'])
def fault_info():
    """Get information about bearing fault types"""
    fault_descriptions = {
        'NORMAL': {
            'name': 'Normal Operation',
            'description': 'Healthy bearing with minimal vibration',
            'symptoms': 'Low, consistent vibration levels',
            'severity': 'None'
        },
        'OUTER_RACE_FAULT': {
            'name': 'Outer Race Fault',
            'description': 'Defect in outer bearing race causing periodic impacts',
            'symptoms': 'Regular impulses at outer race frequency (~3.3 Hz)',
            'severity': 'Medium to High'
        },
        'INNER_RACE_FAULT': {
            'name': 'Inner Race Fault', 
            'description': 'Defect in inner bearing race with load modulation',
            'symptoms': 'Modulated impacts at inner race frequency (~5.0 Hz)',
            'severity': 'High'
        },
        'BALL_FAULT': {
            'name': 'Ball/Element Fault',
            'description': 'Damaged rolling element causing double impacts',
            'symptoms': 'Double-peak signature at ball frequency (~6.7 Hz)',
            'severity': 'Medium'
        },
        'CAGE_FAULT': {
            'name': 'Cage Fault',
            'description': 'Cage damage causing low frequency modulation',
            'symptoms': 'Low frequency modulation of all vibration (~0.17 Hz)',
            'severity': 'Low to Medium'
        }
    }
    
    return jsonify(fault_descriptions)

def create_alert(asset_id, fault_type, confidence, severity):
    """Create a new alert for an asset"""
    global active_alerts
    
    # Remove old alerts for the same asset and fault type
    active_alerts = [alert for alert in active_alerts 
                    if not (alert['asset_id'] == asset_id and alert['fault_type'] == fault_type)]
    
    # Create new alert
    alert = {
        'id': len(active_alerts) + 1,
        'asset_id': asset_id,
        'fault_type': fault_type,
        'confidence': confidence,
        'severity': severity.lower(),
        'timestamp': datetime.now().isoformat(),
        'acknowledged': False
    }
    
    active_alerts.append(alert)
    
    # Keep only last 10 alerts
    if len(active_alerts) > 10:
        active_alerts = active_alerts[-10:]

@app.route('/api/alerts')
@require_auth(['Administrators', 'Operators', 'Viewers'])
def get_alerts():
    """Get current active alerts"""
    return jsonify({
        'success': True,
        'alerts': active_alerts
    })

@app.route('/api/alerts/<int:alert_id>/acknowledge', methods=['POST'])
@require_auth(['Administrators', 'Operators'])
def acknowledge_alert(alert_id):
    """Acknowledge an alert"""
    global active_alerts
    
    for alert in active_alerts:
        if alert['id'] == alert_id:
            alert['acknowledged'] = True
            return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Alert not found'}), 404

if __name__ == '__main__':
    app.run(debug=False, port=5000)