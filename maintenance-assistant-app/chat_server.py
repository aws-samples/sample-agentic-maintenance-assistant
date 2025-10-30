from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS
import sys
import os
import json
from datetime import datetime

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

def get_runtime_config_path():
    """Get the path to runtime_config.json relative to the current script"""
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(parent_dir, 'runtime_config.json')

from strands.models import BedrockModel
from mcp.client.streamable_http import streamablehttp_client 
from strands.tools.mcp.mcp_client import MCPClient
from strands import Agent
import utils
import boto3
import re

app = Flask(__name__)
CORS(app)

# Set AWS region
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

# Cache for user AWS sessions
user_sessions_cache = {}

def load_config():
    with open(get_runtime_config_path(), 'r') as f:
        return json.load(f)

def get_access_token(config):
    REGION = os.environ['AWS_DEFAULT_REGION']
    scopeString = f"{config['RESOURCE_SERVER_ID']}/gateway:read {config['RESOURCE_SERVER_ID']}/gateway:write"
    token_response = utils.get_token(
        config['USER_POOL_ID'], 
        config['CLIENT_ID'], 
        config['CLIENT_SECRET'], 
        scopeString, 
        REGION
    )
    return token_response["access_token"]

def create_streamable_http_transport(gateway_url, access_token):
    return streamablehttp_client(gateway_url, headers={"Authorization": f"Bearer {access_token}"})

def verify_user_token(token):
    """Verify JWT token and extract user information"""
    try:
        import jwt
        from jwt import PyJWKClient
        import os
        
        # Load runtime config with relative path
        config_path = get_runtime_config_path()
        
        if not os.path.exists(config_path):
            print(f"Runtime config not found at: {config_path}")
            return None
            
        with open(config_path, 'r') as f:
            runtime_config = json.load(f)
        
        user_pool_id = runtime_config.get('USER_POOL_ID')
        user_app_client_id = runtime_config.get('USER_APP_CLIENT_ID')
        region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
        
        print(f"Using User Pool: {user_pool_id}")
        print(f"Using Client ID: {user_app_client_id}")
        print(f"Using Region: {region}")
        
        if not user_pool_id or not user_app_client_id:
            print("Missing User Pool ID or Client ID in runtime config")
            return None
        
        # Get JWT signing keys
        jwks_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
        print(f"JWKS URL: {jwks_url}")
        
        # Create JWKS client with SSL context that doesn't verify certificates (for development)
        import ssl
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
        
        print(f"Token verified successfully for user: {decoded_token.get('email', 'unknown')}")
        return decoded_token
        
    except Exception as e:
        print(f"Error verifying user token: {e}")
        print(f"Token type: {type(token)}")
        print(f"Token length: {len(token) if token else 'None'}")
        return None

def check_user_permissions(user_info, required_groups):
    """Check if user has required group membership"""
    if not user_info:
        return False
    
    user_groups = user_info.get('cognito:groups', [])
    return any(group in user_groups for group in required_groups)

def create_audit_log_entry(user_info, action, details=None):
    """Create audit log entry for user actions"""
    import datetime
    
    log_entry = {
        'timestamp': datetime.datetime.utcnow().isoformat(),
        'user_email': user_info.get('email', 'unknown'),
        'user_id': user_info.get('sub', 'unknown'),
        'user_groups': user_info.get('cognito:groups', []),
        'action': action,
        'details': details or {}
    }
    
    # Log to console (in production, send to CloudWatch)
    print(f"AUDIT: {json.dumps(log_entry)}")
    return log_entry

def get_user_aws_session(user_jwt_token):
    """Get AWS session using user's Cognito Identity Pool credentials with caching"""
    try:
        import boto3
        import datetime
        
        # Extract user ID from JWT for caching
        try:
            import jwt
            decoded_token = jwt.decode(user_jwt_token, options={"verify_signature": False})
            user_id = decoded_token.get('sub', 'unknown')
        except:
            user_id = 'test-user-id'
            

        
        # Check if we have valid cached credentials
        if user_id in user_sessions_cache:
            cached_data = user_sessions_cache[user_id]
            expiration = cached_data.get('expiration')
            
            if expiration and datetime.datetime.now(expiration.tzinfo) < expiration - datetime.timedelta(minutes=5):
                print(f"Using cached AWS credentials for user {user_id}")
                return cached_data['session']
            else:
                print(f"Cached credentials expired for user {user_id}, refreshing...")
                del user_sessions_cache[user_id]
        
        # Load runtime config
        with open(get_runtime_config_path(), 'r') as f:
            runtime_config = json.load(f)
        
        user_pool_id = runtime_config.get('USER_POOL_ID')
        identity_pool_id = runtime_config.get('IDENTITY_POOL_ID')
        region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
        
        print(f"Getting fresh AWS credentials for user {user_id} via Identity Pool: {identity_pool_id}")
        
        if not identity_pool_id or not user_pool_id:
            print("Missing Identity Pool ID or User Pool ID")
            return None
        
        # Create Cognito Identity client (this uses environment credentials for the initial call)
        cognito_identity = boto3.client('cognito-identity', region_name=region)
        
        # Get identity ID using user's JWT token
        identity_response = cognito_identity.get_id(
            IdentityPoolId=identity_pool_id,
            Logins={
                f'cognito-idp.{region}.amazonaws.com/{user_pool_id}': user_jwt_token
            }
        )
        
        identity_id = identity_response['IdentityId']
        print(f"Got Identity ID: {identity_id}")
        
        # Get AWS credentials for this identity
        credentials_response = cognito_identity.get_credentials_for_identity(
            IdentityId=identity_id,
            Logins={
                f'cognito-idp.{region}.amazonaws.com/{user_pool_id}': user_jwt_token
            }
        )
        
        credentials = credentials_response['Credentials']
        expiration = credentials.get('Expiration')
        
        # Check if credentials are about to expire (within 5 minutes)
        if expiration:
            import datetime
            now = datetime.datetime.now(expiration.tzinfo)
            time_until_expiry = expiration - now
            if time_until_expiry.total_seconds() < 300:  # Less than 5 minutes
                print(f"Warning: Credentials expire soon: {time_until_expiry}")
        
        # Create boto3 session with user's temporary AWS credentials
        user_session = boto3.Session(
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretKey'],
            aws_session_token=credentials['SessionToken'],
            region_name=region
        )
        
        # Test the credentials by making a simple call
        try:
            sts_client = user_session.client('sts')
            caller_identity = sts_client.get_caller_identity()
            print(f"Credentials validated - User ARN: {caller_identity.get('Arn', 'unknown')}")
        except Exception as test_error:
            print(f"Credential validation failed: {test_error}")
            return None
        
        # Cache the session and credentials
        user_sessions_cache[user_id] = {
            'session': user_session,
            'expiration': expiration,
            'created_at': datetime.datetime.now()
        }
        
        print(f"Cached fresh AWS credentials for user {user_id}")
        return user_session
        
    except Exception as e:
        print(f"Error getting user AWS session: {e}")
        # Clean up any cached data for this user
        if user_id in user_sessions_cache:
            del user_sessions_cache[user_id]
        return None

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        print("Received chat request")
        
        # Step 1: Verify user authentication
        auth_header = request.headers.get('Authorization', '')
        print(f"Received Authorization header: {auth_header[:50] if auth_header else 'None'}...")
        
        if not auth_header.startswith('Bearer '):
            print("No Bearer token in Authorization header")
            return jsonify({'error': 'No authorization token provided'}), 401
        
        user_token = auth_header.replace('Bearer ', '')
        print(f"Extracted token length: {len(user_token)}")
        
        user_info = verify_user_token(user_token)
        
        if not user_info:
            print("Token verification failed")
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        print(f"User authenticated: {user_info.get('email', 'unknown')}")
        
        # Step 2: Check user permissions
        required_groups = ['Administrators', 'Operators']  # Viewers can't use chat
        user_groups = user_info.get('cognito:groups', [])
        
        # Temporary: Allow users without groups for testing (remove this later)
        if not user_groups:
            print("Warning: User has no groups assigned, allowing access for testing")
        elif not check_user_permissions(user_info, required_groups):
            create_audit_log_entry(user_info, 'chat_access_denied', {'reason': 'insufficient_permissions'})
            return jsonify({'error': 'Insufficient permissions for chat access'}), 403
        
        # Step 3: Process request data
        data = request.get_json()
        message = data.get('message', '')
        alert_context = data.get('alert_context', {})
        print(f"User: {user_info.get('email')} - Message: {message}")
        print(f"Alert context: {alert_context}")
        
        # Add alert context to message if provided
        if alert_context:
            context_msg = f"Alert Context - Asset: {alert_context.get('asset_name', 'Unknown')}, Fault: {alert_context.get('fault_type', 'Unknown')}, Severity: {alert_context.get('severity', 'Unknown')}. User Question: {message}"
            message = context_msg
            print(f"Enhanced message with context: {message}")
        
        if not message:
            return jsonify({'error': 'No message provided'}), 400
        
        # Step 4: Get user's AWS credentials from Identity Pool
        user_aws_session = get_user_aws_session(user_token)
        if not user_aws_session:
            return jsonify({'error': 'Could not obtain AWS credentials for user'}), 500
        
        # Step 5: Use service credentials for AgentCore Gateway (M2M)
        config = load_config()
        service_token = get_access_token(config)  # M2M token for AgentCore
        
        # Step 6: Create MCP client with service token
        mcp_client = MCPClient(lambda: create_streamable_http_transport(config['GATEWAY_URL'], service_token))
        
        # Use full AgentCore with non-streaming Bedrock model
        print("Using AgentCore Gateway with Strands Agent...")
        
        # Step 7: Create Bedrock model using USER'S AWS credentials
        try:
            # Create Bedrock client with user's credentials
            bedrock_client = user_aws_session.client('bedrock-runtime')
            
            # Skip access test - just trust the credentials work
            print("Bedrock client created with user credentials")
            
            # Create BedrockModel using environment variables temporarily
            # Store current env vars
            old_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
            old_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY') 
            old_session_token = os.environ.get('AWS_SESSION_TOKEN')
            
            # Set user's credentials in environment
            credentials = user_aws_session.get_credentials()
            os.environ['AWS_ACCESS_KEY_ID'] = credentials.access_key
            os.environ['AWS_SECRET_ACCESS_KEY'] = credentials.secret_key
            if credentials.token:
                os.environ['AWS_SESSION_TOKEN'] = credentials.token
            
            try:
                # Create BedrockModel - it will use the environment credentials
                model = BedrockModel(
                    model_id=config['MODEL'],  # Use model from runtime config
                    temperature=0,  # Use greedy decoding for better tool use
                    streaming=False
                )
            finally:
                # Restore original environment variables
                if old_access_key:
                    os.environ['AWS_ACCESS_KEY_ID'] = old_access_key
                else:
                    os.environ.pop('AWS_ACCESS_KEY_ID', None)
                    
                if old_secret_key:
                    os.environ['AWS_SECRET_ACCESS_KEY'] = old_secret_key
                else:
                    os.environ.pop('AWS_SECRET_ACCESS_KEY', None)
                    
                if old_session_token:
                    os.environ['AWS_SESSION_TOKEN'] = old_session_token
                else:
                    os.environ.pop('AWS_SESSION_TOKEN', None)
            print("Using user's AWS credentials for Bedrock")
            
        except Exception as bedrock_error:
            print(f"Failed to use user's AWS credentials for Bedrock: {bedrock_error}")
            print(f"Error type: {type(bedrock_error).__name__}")
            
            # Check if it's a token expiration issue
            if "ExpiredToken" in str(bedrock_error) or "expired" in str(bedrock_error).lower():
                return jsonify({
                    'error': 'AWS credentials expired. Please refresh your login.',
                    'error_type': 'expired_credentials'
                }), 401
            
            # For other errors, try fallback to environment credentials
            try:
                model = BedrockModel(
                    model_id=config['MODEL'],  # Use model from runtime config
                    temperature=0,  # Use greedy decoding for better tool use
                    streaming=False
                )
                print("Warning: Falling back to environment AWS credentials")
            except Exception as fallback_error:
                print(f"Fallback to environment credentials also failed: {fallback_error}")
                return jsonify({
                    'error': 'Could not access Bedrock with user or environment credentials',
                    'details': str(bedrock_error)
                }), 500
        
        # Load system prompt
        system_prompt = "You are an agentic maintenance assistant for industrial facilities. Help with maintenance work orders, asset management, and troubleshooting across various industries including manufacturing, energy, transportation, and healthcare. Always provide clear, human-readable responses and use descriptive names instead of IDs. In order to get IDs, you need to use the \"list\" tools in MaintainX. Be direct and concise - only show successful results, not failed attempts or reasoning process. Do not mention tool failures, ID issues, or apologize for problems. Answer only what you can accomplish successfully."
        
        with mcp_client:
            tools = mcp_client.list_tools_sync()
            print(f"Got {len(tools)} tools")
            print(f"Tool info: {[getattr(tool, 'tool_name', str(tool)) for tool in tools]}")
            
            # Create Agent with non-streaming model
            agent = Agent(model=model, tools=tools, system_prompt=system_prompt)
            print("Calling AgentCore agent...")
            
            try:
                response = agent(message)
                print("AgentCore agent responded successfully")
                
                # Log the original AgentCore response
                original_response = str(response)
                print(f"Original AgentCore response: {original_response}", flush=True)
                
                # Check if response mentions documents and add knowledge base content
                response_str = original_response
                if "attached" in response_str.lower() or "pdf" in response_str.lower() or "manual" in response_str.lower():
                    print("Response mentions documents, retrieving knowledge base content...")
                    try:
                        # Build dynamic query from alert context and user message
                        fault_type = alert_context.get('fault_type', '').replace('_', ' ').lower()
                        asset_name = alert_context.get('asset_name', 'equipment')
                        
                        # Use fault type from context, fallback to message content
                        if fault_type:
                            query = f"{fault_type} maintenance manual {asset_name} repair"
                        else:
                            # Extract key terms from user message for query
                            query_terms = []
                            if 'bearing' in message.lower():
                                query_terms.append('bearing')
                            if 'fault' in message.lower():
                                query_terms.append('fault')
                            if 'maintenance' in message.lower():
                                query_terms.append('maintenance')
                            query = ' '.join(query_terms) + ' manual repair' if query_terms else 'maintenance manual repair'
                        
                        kb_result = mcp_client.call_tool_sync(
                            tool_use_id="kb-search-1",
                            name="knowledge-base-lambda-target___search_knowledge_base",
                            arguments={"query": query}
                        )
                        kb_content = kb_result['content'][0]['text']
                        
                        # Parse and create presigned URLs for documents
                        import boto3
                        import re
                        import json as json_lib
                        
                        s3_client = boto3.client('s3', region_name='us-east-1')
                        
                        # Extract S3 URLs from the response
                        try:
                            # Parse the Lambda response format
                            if kb_content.startswith('{"statusCode"'):
                                lambda_response = json_lib.loads(kb_content)
                                kb_body = json_lib.loads(lambda_response['body'])
                            else:
                                kb_body = json_lib.loads(kb_content)
                            
                            documents = []
                            
                            for result in kb_body.get('results', []):
                                source = result.get('source', '')
                                if source.startswith('s3://'):
                                    # Parse S3 URL
                                    s3_parts = source.replace('s3://', '').split('/', 1)
                                    bucket = s3_parts[0]
                                    key = s3_parts[1] if len(s3_parts) > 1 else ''
                                    
                                    # Generate presigned URL
                                    try:
                                        presigned_url = s3_client.generate_presigned_url(
                                            'get_object',
                                            Params={'Bucket': bucket, 'Key': key},
                                            ExpiresIn=3600  # 1 hour
                                        )
                                        
                                        # Get filename without icon
                                        file_ext = key.split('.')[-1].lower()
                                        
                                        filename = key.split('/')[-1]
                                        documents.append({
                                            'name': filename,
                                            'url': presigned_url,
                                            'content': result.get('content', '')[:200] + '...' if len(result.get('content', '')) > 200 else result.get('content', '')
                                        })
                                    except Exception as url_e:
                                        print(f"Error generating presigned URL: {url_e}")
                            
                            # Format documents for display with HTML
                            if documents:
                                docs_html = "\n\n**Referenced Documents:**\n"
                                for doc in documents:
                                    docs_html += f"\n<a href='{doc['url']}' target='_blank' style='color: #3b82f6; text-decoration: underline;'><strong>{doc['name']}</strong></a> <em>(Click to open in new tab)</em>\n"
                                    docs_html += f"Preview: {doc['content']}\n"
                                
                                response_str += docs_html
                            else:
                                response_str += f"\n\n**Referenced Documents Content:**\n{kb_content}"
                                
                        except json_lib.JSONDecodeError:
                            response_str += f"\n\n**Referenced Documents Content:**\n{kb_content}"
                        
                        response = response_str
                        print("Added knowledge base content with presigned URLs")
                    except Exception as kb_e:
                        print(f"Could not retrieve knowledge base content: {kb_e}")
                        response_str += "\n\n*Note: Referenced documents are available in the maintenance knowledge base but could not be retrieved at this time.*"
                        response = response_str
                        
            except Exception as e:
                print(f"Agent error: {e}")
                response = f"AgentCore error: {str(e)}"
            
            # Step 6: Create audit log for successful operation
            create_audit_log_entry(user_info, 'chat_completed', {
                'message_length': len(message),
                'has_alert_context': bool(alert_context),
                'response_length': len(str(response))
            })
            
            return jsonify({
                'response': str(response),
                'timestamp': datetime.now().isoformat(),
                'user': user_info.get('email')  # Include user context in response
            })
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({
            'response': f'Error: {str(e)}',
            'timestamp': datetime.now().isoformat()
        })

@app.route('/')
def chat_interface():
    try:
        return render_template('chat.html')
    except Exception as e:
        return f"<h1>Chat Interface</h1><p>Error: {str(e)}</p>"

@app.route('/health')
def health():
    return "Chat server running"

@app.route('/api/status')
def status():
    return jsonify({
        'server_status': 'running',
        'agentcore_available': True,
        'agentcore_initialized': True
    })

if __name__ == '__main__':
    print("Starting simple chat server...")
    app.run(host='0.0.0.0', port=5002, debug=False)