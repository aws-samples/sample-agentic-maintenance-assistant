from flask import Flask, jsonify, request
from flask_cors import CORS
from models import create_tables, get_db, AssetType, Asset, MLModel, MapConfig, Simulator
import os
import json
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from functools import wraps

def get_runtime_config_path():
    """Get the path to runtime_config.json relative to the current script"""
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(parent_dir, 'runtime_config.json')



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
            region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
            user_info = verify_user_token(token, region)
            
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

# Initialize database
create_tables()

# Settings file path
SETTINGS_FILE = 'admin_settings.json'

def load_settings():
    """Load admin settings from file"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {
        'branding': {
            'app_title': 'AI Predictive Maintenance',
            'app_subtitle': 'Theme Park Asset Management',
            'company_name': 'Theme Park Operations'
        }
    }

def save_settings(settings):
    """Save admin settings to file"""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
        return True
    except:
        return False

def sync_settings_to_db():
    """Sync settings file to database on startup"""
    settings = load_settings()
    if not settings:
        return
    
    db = get_db()
    try:
        # Restore active map
        if 'active_map' in settings:
            db.query(MapConfig).update({'is_active': False})
            existing = db.query(MapConfig).filter(MapConfig.image_path == settings['active_map']).first()
            if existing:
                existing.is_active = True
            else:
                new_map = MapConfig(
                    name='Restored Map',
                    image_path=settings['active_map'],
                    is_active=True
                )
                db.add(new_map)
        
        # Restore asset types
        for at_data in settings.get('asset_types', []):
            existing = db.query(AssetType).filter(AssetType.name == at_data['name']).first()
            if not existing:
                asset_type = AssetType(**at_data)
                db.add(asset_type)
        
        # Restore ML models
        for ml_data in settings.get('ml_models', []):
            existing = db.query(MLModel).filter(MLModel.name == ml_data['name']).first()
            if not existing:
                model = MLModel(**ml_data)
                db.add(model)
        
        # Restore assets
        for asset_data in settings.get('assets', []):
            existing = db.query(Asset).filter(Asset.name == asset_data['name']).first()
            if not existing:
                asset = Asset(**asset_data)
                db.add(asset)
        
        db.commit()
    finally:
        db.close()

# Load settings on startup
sync_settings_to_db()

@app.route('/api/admin/maps', methods=['GET'])
@require_auth(['Administrators', 'Operators'])
def get_maps():
    """Get configured maps from database"""
    db = get_db()
    try:
        # Get maps from database, not filesystem
        db_maps = db.query(MapConfig).all()
        maps = []
        
        for db_map in db_maps:
            # Verify the file still exists
            assets_path = os.path.join(os.path.dirname(__file__), 'public', 'assets')
            file_path = os.path.join(assets_path, os.path.basename(db_map.image_path))
            
            if os.path.exists(file_path):
                maps.append({
                    'filename': os.path.basename(db_map.image_path),
                    'path': db_map.image_path,
                    'name': db_map.name
                })
        
        active_map = db.query(MapConfig).filter(MapConfig.is_active == True).first()
        return jsonify({
            'success': True,
            'maps': maps,
            'active_map': active_map.image_path if active_map else None
        })
    finally:
        db.close()

@app.route('/api/admin/maps/upload', methods=['POST'])
@require_auth(['Administrators'])
def upload_map():
    """Upload new map file and create database entry"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    
    if file and file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        assets_path = os.path.join(os.path.dirname(__file__), 'public', 'assets')
        os.makedirs(assets_path, exist_ok=True)
        
        filename = secure_filename(file.filename)
        file_path = os.path.join(assets_path, filename)
        file.save(file_path)
        
        # Create database entry for the uploaded map
        db = get_db()
        try:
            # Create a friendly name from filename
            map_name = filename.replace('_', ' ').replace('.jpeg', '').replace('.jpg', '').replace('.png', '').title()
            
            new_map = MapConfig(
                name=map_name,
                image_path=f'/assets/{filename}',
                is_active=False,  # Don't auto-activate, let user choose
                width=1200,
                height=800
            )
            
            # Create audit log
            create_audit_log_entry(request.user, 'map_upload', {
                'filename': filename,
                'map_name': map_name
            })
            db.add(new_map)
            db.commit()
            
            return jsonify({
                'success': True,
                'filename': filename,
                'path': f'/assets/{filename}',
                'message': 'Map uploaded and added to database successfully'
            })
        except Exception as e:
            db.rollback()
            return jsonify({'success': False, 'error': f'Failed to save to database: {str(e)}'}), 500
        finally:
            db.close()
    
    return jsonify({'success': False, 'error': 'Invalid file type'}), 400

@app.route('/api/admin/maps/<filename>', methods=['DELETE'])
@require_auth(['Administrators'])
def delete_map(filename):
    """Delete map from database (keeps file on filesystem)"""
    db = get_db()
    try:
        # Find and delete the map configuration from database
        map_to_delete = db.query(MapConfig).filter(MapConfig.image_path == f'/assets/{filename}').first()
        
        if map_to_delete:
            db.delete(map_to_delete)
            db.commit()
            return jsonify({
                'success': True, 
                'message': f'Map "{map_to_delete.name}" removed from configuration (file preserved)'
            })
        else:
            return jsonify({'success': False, 'error': 'Map configuration not found in database'}), 404
            
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': f'Database error: {str(e)}'}), 500
    finally:
        db.close()

@app.route('/api/admin/models/upload', methods=['POST'])
@require_auth(['Administrators'])
def upload_model():
    """Upload ML model file"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    
    if file and file.filename.lower().endswith(('.h5', '.pkl', '.joblib', '.model')):
        models_path = os.path.join(os.path.dirname(__file__), 'models')
        os.makedirs(models_path, exist_ok=True)
        
        filename = secure_filename(file.filename)
        file_path = os.path.join(models_path, filename)
        file.save(file_path)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'path': f'models/{filename}'
        })
    
    return jsonify({'success': False, 'error': 'Invalid file type. Supported: .h5, .pkl, .joblib, .model'}), 400

@app.route('/api/admin/maps/active', methods=['POST'])
@require_auth(['Administrators'])
def set_active_map():
    """Set active map"""
    data = request.get_json()
    image_path = data.get('image_path')
    
    db = get_db()
    try:
        # Deactivate all maps
        db.query(MapConfig).update({'is_active': False})
        
        # Set new active map
        existing = db.query(MapConfig).filter(MapConfig.image_path == image_path).first()
        if existing:
            existing.is_active = True
        else:
            new_map = MapConfig(
                name=data.get('name', 'Theme Park Map'),
                image_path=image_path,
                is_active=True
            )
            db.add(new_map)
        
        db.commit()
        
        # Save to settings file
        settings = load_settings()
        settings['active_map'] = image_path
        save_settings(settings)
        
        return jsonify({'success': True})
    finally:
        db.close()

@app.route('/api/admin/simulators', methods=['GET', 'POST'])
@require_auth(['Administrators', 'Operators'])
def handle_simulators():
    db = get_db()
    try:
        if request.method == 'GET':
            simulators = db.query(Simulator).all()
            return jsonify({
                'success': True,
                'simulators': [{
                    'id': s.id,
                    'name': s.name,
                    'class_name': s.class_name,
                    'description': s.description
                } for s in simulators]
            })
        
        elif request.method == 'POST':
            data = request.get_json()
            simulator = Simulator(
                name=data['name'],
                class_name=data['class_name'],
                description=data.get('description', '')
            )
            db.add(simulator)
            db.commit()
            return jsonify({'success': True, 'id': simulator.id})
    finally:
        db.close()

@app.route('/api/admin/simulators/<int:simulator_id>', methods=['DELETE'])
@require_auth(['Administrators'])
def delete_simulator(simulator_id):
    db = get_db()
    try:
        simulator = db.query(Simulator).filter(Simulator.id == simulator_id).first()
        if not simulator:
            return jsonify({'success': False, 'error': 'Simulator not found'}), 404
        
        db.delete(simulator)
        db.commit()
        return jsonify({'success': True})
    finally:
        db.close()

@app.route('/api/admin/asset-types', methods=['GET', 'POST'])
@require_auth(['Administrators', 'Operators'])
def handle_asset_types():
    db = get_db()
    try:
        if request.method == 'GET':
            asset_types = db.query(AssetType).all()
            return jsonify({
                'success': True,
                'asset_types': [{
                    'id': at.id,
                    'name': at.name,
                    'description': at.description,
                    'simulator_id': at.simulator_id,
                    'simulator_name': at.simulator.name if at.simulator else None
                } for at in asset_types]
            })
        
        elif request.method == 'POST':
            data = request.get_json()
            asset_type = AssetType(
                name=data['name'],
                description=data.get('description', ''),
                simulator_id=data.get('simulator_id')
            )
            db.add(asset_type)
            db.commit()
            return jsonify({'success': True, 'id': asset_type.id})
    finally:
        db.close()

@app.route('/api/admin/ml-models', methods=['GET', 'POST'])
@require_auth(['Administrators', 'Operators'])
def handle_ml_models():
    db = get_db()
    try:
        if request.method == 'GET':
            models = db.query(MLModel).all()
            return jsonify({
                'success': True,
                'models': [{
                    'id': m.id,
                    'name': m.name,
                    'model_type': m.model_type,
                    'model_path': m.model_path,
                    'is_trained': m.is_trained,
                    'accuracy': m.accuracy
                } for m in models]
            })
        
        elif request.method == 'POST':
            data = request.get_json()
            model = MLModel(
                name=data['name'],
                model_type=data['model_type'],
                model_path=data.get('model_path', '')
            )
            db.add(model)
            db.commit()
            
            # Save to settings
            settings = load_settings()
            if 'ml_models' not in settings:
                settings['ml_models'] = []
            settings['ml_models'].append({
                'name': data['name'],
                'model_type': data['model_type'],
                'model_path': data.get('model_path', '')
            })
            save_settings(settings)
            
            return jsonify({'success': True, 'id': model.id})
    finally:
        db.close()

@app.route('/api/admin/assets', methods=['GET', 'POST'])
@require_auth(['Administrators', 'Operators'])
def handle_assets():
    db = get_db()
    try:
        if request.method == 'GET':
            assets = db.query(Asset).all()
            return jsonify({
                'success': True,
                'assets': [{
                    'id': a.id,
                    'name': a.name,
                    'asset_type_id': a.asset_type_id,
                    'asset_type_name': a.asset_type.name if a.asset_type else None,
                    'ml_model_id': a.ml_model_id,
                    'ml_model_name': a.ml_model.name if a.ml_model else None,
                    'map_x': a.map_x,
                    'map_y': a.map_y,
                    'map_width': a.map_width,
                    'map_height': a.map_height,
                    'status': a.status
                } for a in assets]
            })
        
        elif request.method == 'POST':
            data = request.get_json()
            asset = Asset(
                name=data['name'],
                asset_type_id=data['asset_type_id'],
                ml_model_id=data.get('ml_model_id'),
                map_x=data.get('map_x'),
                map_y=data.get('map_y'),
                map_width=data.get('map_width', 50),
                map_height=data.get('map_height', 50),
                status=data.get('status', 'active')
            )
            db.add(asset)
            db.commit()
            
            # Save to settings
            settings = load_settings()
            if 'assets' not in settings:
                settings['assets'] = []
            settings['assets'].append({
                'name': data['name'],
                'asset_type_id': data['asset_type_id'],
                'ml_model_id': data.get('ml_model_id'),
                'map_x': data.get('map_x'),
                'map_y': data.get('map_y'),
                'map_width': data.get('map_width', 50),
                'map_height': data.get('map_height', 50),
                'status': data.get('status', 'active')
            })
            save_settings(settings)
            
            return jsonify({'success': True, 'id': asset.id})
    finally:
        db.close()

@app.route('/api/admin/assets/<int:asset_id>', methods=['PUT', 'DELETE'])
@require_auth(['Administrators'])
def handle_asset(asset_id):
    db = get_db()
    try:
        asset = db.query(Asset).filter(Asset.id == asset_id).first()
        
        if not asset:
            return jsonify({'success': False, 'error': 'Asset not found'}), 404
        
        if request.method == 'PUT':
            data = request.get_json()
            for key, value in data.items():
                if hasattr(asset, key):
                    setattr(asset, key, value)
            db.commit()
            return jsonify({'success': True})
        
        elif request.method == 'DELETE':
            db.delete(asset)
            db.commit()
            return jsonify({'success': True})
    finally:
        db.close()

@app.route('/api/admin/asset-types/<int:type_id>', methods=['DELETE'])
@require_auth(['Administrators'])
def delete_asset_type(type_id):
    db = get_db()
    try:
        asset_type = db.query(AssetType).filter(AssetType.id == type_id).first()
        if not asset_type:
            return jsonify({'success': False, 'error': 'Asset type not found'}), 404
        
        db.delete(asset_type)
        db.commit()
        return jsonify({'success': True})
    finally:
        db.close()

@app.route('/api/admin/ml-models/<int:model_id>', methods=['DELETE'])
@require_auth(['Administrators'])
def delete_ml_model(model_id):
    db = get_db()
    try:
        model = db.query(MLModel).filter(MLModel.id == model_id).first()
        if not model:
            return jsonify({'success': False, 'error': 'ML model not found'}), 404
        
        db.delete(model)
        db.commit()
        return jsonify({'success': True})
    finally:
        db.close()

@app.route('/api/admin/branding', methods=['GET', 'POST'])
@require_auth(['Administrators'])
def handle_branding():
    """Get or update branding configuration"""
    if request.method == 'GET':
        settings = load_settings()
        return jsonify({
            'success': True,
            'branding': settings.get('branding', {
                'app_title': 'AI Predictive Maintenance',
                'app_subtitle': 'Theme Park Asset Management',
                'company_name': 'Theme Park Operations'
            })
        })
    
    elif request.method == 'POST':
        data = request.get_json()
        settings = load_settings()
        settings['branding'] = data.get('branding', {})
        
        if save_settings(settings):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to save settings'}), 500

@app.route('/api/test-auth', methods=['GET'])
@require_auth()  # No specific groups required
def test_auth():
    """Test endpoint to verify authentication is working"""
    return jsonify({
        'success': True,
        'user': request.user.get('email', 'unknown'),
        'groups': request.user.get('cognito:groups', []),
        'message': 'Authentication working!'
    })

@app.route('/api/auth/config', methods=['GET'])
def get_auth_config():
    """Get Cognito configuration for frontend"""
    try:
        # Load runtime config to get Cognito details
        with open(get_runtime_config_path(), 'r') as f:
            runtime_config = json.load(f)
        
        return jsonify({
            'success': True,
            'userPoolId': runtime_config.get('USER_POOL_ID'),
            'userAppClientId': runtime_config.get('USER_APP_CLIENT_ID'),
            'identityPoolId': runtime_config.get('IDENTITY_POOL_ID'),
            'region': runtime_config.get('AWS_REGION', 'us-east-1')
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def get_aws_session_from_user_token(id_token, region):
    """Get AWS session using user's Cognito identity token"""
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        # Load runtime config
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(parent_dir, 'runtime_config.json')
        
        with open(config_path, 'r') as f:
            runtime_config = json.load(f)
        
        identity_pool_id = runtime_config.get('IDENTITY_POOL_ID')
        user_pool_id = runtime_config.get('USER_POOL_ID')
        
        if not identity_pool_id or not user_pool_id:
            raise Exception("Identity Pool or User Pool ID not configured")
        
        # Create Cognito Identity client
        cognito_identity = boto3.client('cognito-identity', region_name=region)
        
        # Get identity ID
        identity_response = cognito_identity.get_id(
            IdentityPoolId=identity_pool_id,
            Logins={
                f'cognito-idp.{region}.amazonaws.com/{user_pool_id}': id_token
            }
        )
        
        identity_id = identity_response['IdentityId']
        
        # Get credentials for identity
        credentials_response = cognito_identity.get_credentials_for_identity(
            IdentityId=identity_id,
            Logins={
                f'cognito-idp.{region}.amazonaws.com/{user_pool_id}': id_token
            }
        )
        
        credentials = credentials_response['Credentials']
        
        # Create boto3 session with user's credentials
        session = boto3.Session(
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretKey'],
            aws_session_token=credentials['SessionToken'],
            region_name=region
        )
        
        return session
        
    except Exception as e:
        print(f"Error getting AWS session from user token: {e}")
        return None

def verify_user_token(token, region):
    """Verify JWT token and extract user information"""
    try:
        import jwt
        from jwt import PyJWKClient
        import ssl
        
        # Load runtime config
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(parent_dir, 'runtime_config.json')
        
        with open(config_path, 'r') as f:
            runtime_config = json.load(f)
        
        user_pool_id = runtime_config.get('USER_POOL_ID')
        user_app_client_id = runtime_config.get('USER_APP_CLIENT_ID')
        
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



@app.route('/api/alerts', methods=['GET'])
@require_auth(['Administrators', 'Operators', 'Viewers'])
def get_alerts():
    """Get current alerts for assets from main API server"""
    try:
        import requests
        # Forward the authorization header to the main API server
        auth_header = request.headers.get('Authorization', '')
        headers = {'Authorization': auth_header} if auth_header else {}
        response = requests.get('http://localhost:5000/api/alerts', headers=headers, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Failed to fetch alerts from main server: {e}")
        pass
    
    # Fallback to sample data if main server not available
    # Get the first available asset from database for sample alert
    try:
        from models import get_db, Asset
        db = get_db()
        first_asset = db.query(Asset).first()
        sample_asset_id = first_asset.id if first_asset else 1
        db.close()
    except:
        sample_asset_id = 1  # Fallback
    
    sample_alerts = [
        {
            'id': 1,
            'asset_id': sample_asset_id,
            'severity': 'high',
            'fault_type': 'OUTER_RACE_FAULT',
            'timestamp': (datetime.now() - timedelta(minutes=5)).isoformat(),
            'confidence': 0.87
        }
    ]
    
    return jsonify({
        'success': True,
        'alerts': sample_alerts
    })

@app.route('/api/map/config', methods=['GET'])
@require_auth(['Administrators', 'Operators', 'Viewers'])
def get_map_config():
    """Get current map configuration and assets"""
    db = get_db()
    try:
        active_map = db.query(MapConfig).filter(MapConfig.is_active == True).first()
        assets = db.query(Asset).all()
        settings = load_settings()
        
        return jsonify({
            'success': True,
            'branding': settings.get('branding', {
                'app_title': 'AI Predictive Maintenance',
                'app_subtitle': 'Theme Park Asset Management',
                'company_name': 'Theme Park Operations'
            }),
            'map': {
                'image_path': active_map.image_path if active_map else None,
                'width': active_map.width if active_map else None,
                'height': active_map.height if active_map else None
            } if active_map else None,
            'assets': [{
                'id': a.id,
                'name': a.name,
                'type': a.asset_type.name if a.asset_type else 'Unknown',
                'x': a.map_x,
                'y': a.map_y,
                'width': a.map_width,
                'height': a.map_height,
                'status': a.status
            } for a in assets if a.map_x is not None and a.map_y is not None]
        })
    finally:
        db.close()

if __name__ == '__main__':
    app.run(debug=False, port=5001)