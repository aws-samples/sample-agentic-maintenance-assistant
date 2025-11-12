import os
import boto3
from strands.models import BedrockModel
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient
from strands import Agent
import logging
import utils
import requests
import time
import zipfile
from botocore.exceptions import ClientError
import json
from pprint import pprint

REGION = os.environ.get('AWS_REGION', 'us-east-1')
setup_config_filepath = 'setup_config.json'
runtime_config_filepath = 'runtime_config.json'

# Configure the root strands logger. Change it to DEBUG if you are debugging the issue.
logging.getLogger("strands").setLevel(logging.INFO)

# Add a handler to see the logs
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s", 
    handlers=[logging.StreamHandler()]
)

# Load project configuration data
try:
    with open(setup_config_filepath, 'r') as config_file:
        config_data = json.load(config_file)
        print("Setup configuration loaded successfully.")
        AGENTCORE_GATEWAY_NAME = config_data['AGENTCORE_GATEWAY_NAME']
        AGENTCORE_GATEWAY_TARGET_NAME = config_data['AGENTCORE_GATEWAY_TARGET_NAME']
        USER_POOL_NAME = config_data['USER_POOL_NAME']
        RESOURCE_SERVER_ID = config_data['RESOURCE_SERVER_ID']
        RESOURCE_SERVER_NAME = config_data['RESOURCE_SERVER_NAME']
        CLIENT_NAME = config_data['CLIENT_NAME']
        MODEL = config_data['MODEL'].strip()
        MAINTAINX_API_KEY_PARAMETER_NAME = config_data['MAINTAINX_API_KEY_PARAMETER_NAME']
        MAINTAINX_API_KEY = config_data['MAINTAINX_API_KEY']
        OPENAPI_FILE_PATH = config_data['OPENAPI_FILE_PATH']
        OPENAPI_FILE_NAME = config_data['OPENAPI_FILE_NAME']
        S3_BUCKET_NAME = config_data['S3_BUCKET_NAME']
except FileNotFoundError:
    print("Error: setup_config.json not found.")
    exit(1)
except json.JSONDecodeError:
    print("Error: Invalid JSON format in setup_config.json.")
    exit(1)

# Prepare runtime configuration file
config_data = {}
try:
    with open(runtime_config_filepath, 'r') as config_file:
        config_data = json.load(config_file)
        print("Existing runtime configuration loaded successfully.")
except FileNotFoundError:
    print("Runtime configuration file not found. Creating new one.")
    config_data = {}
except json.JSONDecodeError:
    print("Error: Invalid JSON format in runtime_config.json.")
    exit(1)

def update_runtime_config(key, value):
    print(f"{key}: {value}")
    # Check if the key exists and append/update
    if key in config_data:
        print(f"'{key}' already exists in runtime_config.json. Updating value.")
    config_data[key] = value
    
    # Write to file immediately
    with open(runtime_config_filepath, 'w') as config_file:
        json.dump(config_data, config_file, indent=2)

# Create an IAM role for the Gateway to assume
agentcore_gateway_iam_role = utils.create_agentcore_gateway_role("sample-lambdagateway")
print("Agentcore gateway role ARN: ", agentcore_gateway_iam_role['Role']['Arn'])

# Create Cognito resources for AgentCore Gateway Inbound Authentication
SCOPES = [
    {"ScopeName": "gateway:read", "ScopeDescription": "Read access"},
    {"ScopeName": "gateway:write", "ScopeDescription": "Write access"}
]
scopeString = f"{RESOURCE_SERVER_ID}/gateway:read {RESOURCE_SERVER_ID}/gateway:write"

cognito = boto3.client("cognito-idp", region_name=REGION)

print("Creating or retrieving Cognito resources...")
user_pool_id = utils.get_or_create_user_pool(cognito, USER_POOL_NAME)
print(f"User Pool ID: {user_pool_id}")
update_runtime_config("USER_POOL_ID", user_pool_id)

utils.get_or_create_resource_server(cognito, user_pool_id, RESOURCE_SERVER_ID, RESOURCE_SERVER_NAME, SCOPES)
print("Resource server ensured.")
update_runtime_config("RESOURCE_SERVER_ID", RESOURCE_SERVER_ID)

client_id, client_secret  = utils.get_or_create_m2m_client(cognito, user_pool_id, CLIENT_NAME, RESOURCE_SERVER_ID)
print(f"M2M Client ID: {client_id}")
update_runtime_config("CLIENT_ID", client_id)
update_runtime_config("CLIENT_SECRET", client_secret)

# Create user app client for frontend authentication
user_app_client_name = f"{CLIENT_NAME}-UserApp"
user_app_client_id = utils.get_or_create_user_app_client(cognito, user_pool_id, user_app_client_name)
print(f"User App Client ID: {user_app_client_id}")
update_runtime_config("USER_APP_CLIENT_ID", user_app_client_id)

# Create user groups for role-based access control
print("Creating user groups...")
utils.create_user_groups(cognito, user_pool_id)

# Create Lambda function for post-confirmation trigger
print("Setting up Lambda trigger for auto-group assignment...")
lambda_function_arn = utils.create_post_confirmation_lambda(user_pool_id)
if lambda_function_arn:
    utils.configure_cognito_trigger(cognito, user_pool_id, lambda_function_arn)
    update_runtime_config("POST_CONFIRMATION_LAMBDA_ARN", lambda_function_arn)

# Create Cognito Identity Pool for AWS credential federation
print("Creating Cognito Identity Pool for AWS credential federation...")
identity_pool_id = utils.create_identity_pool(user_pool_id, user_app_client_id, REGION)
if identity_pool_id:
    update_runtime_config("IDENTITY_POOL_ID", identity_pool_id)
    
    # Create IAM roles for different user groups
    print("Creating IAM roles for user groups...")
    utils.create_identity_pool_roles(identity_pool_id, REGION)

# Get discovery URL  
cognito_discovery_url = f'https://cognito-idp.{REGION}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration'
print(cognito_discovery_url)

# CreateGateway with Cognito authorizer without CMK. Use the Cognito user pool created in the previous step
gateway_client = boto3.client('bedrock-agentcore-control', region_name = REGION)
auth_config = {
    "customJWTAuthorizer": { 
        "allowedClients": [client_id],  # Client MUST match with the ClientId configured in Cognito. Example: 7rfbikfsm51j2fpaggacgng84g
        "discoveryUrl": cognito_discovery_url
    }
}

try:
    create_response = gateway_client.create_gateway(name=AGENTCORE_GATEWAY_NAME,
        roleArn = agentcore_gateway_iam_role['Role']['Arn'], # The IAM Role must have permissions to create/list/get/delete Gateway 
        protocolType='MCP',
        authorizerType='CUSTOM_JWT',
        authorizerConfiguration=auth_config, 
        description='AgentCore Gateway for generative AI assistant'
    )
    print("Created new gateway")
    gatewayID = create_response["gatewayId"]
    gatewayURL = create_response["gatewayUrl"]
except ClientError as e:
    if e.response['Error']['Code'] == 'ConflictException':
        print("Gateway already exists, finding existing gateway...")
        gateways = gateway_client.list_gateways()
        for gateway in gateways.get('items', []):
            if gateway['name'] == AGENTCORE_GATEWAY_NAME:
                gatewayID = gateway['gatewayId']
                # Get gateway details to retrieve URL
                gateway_details = gateway_client.get_gateway(gatewayIdentifier=gatewayID)
                gatewayURL = gateway_details['gatewayUrl']
                print(f"Using existing gateway: {gatewayID}")
                break
    else:
        raise e

print(f"Gateway ID: {gatewayID}")
update_runtime_config("GATEWAY_ID", gatewayID)
update_runtime_config("GATEWAY_URL", gatewayURL)

acps = boto3.client(service_name="bedrock-agentcore-control")

try:
    response=acps.create_api_key_credential_provider(
        name=MAINTAINX_API_KEY_PARAMETER_NAME,
        apiKey=MAINTAINX_API_KEY,
    )
    credentialProviderARN = response['credentialProviderArn']
    print(f"Created credential provider: {credentialProviderARN}")
except ClientError as e:
    if e.response['Error']['Code'] in ['ConflictException', 'ValidationException']:
        # Credential provider already exists - delete and recreate to ensure API key is current
        print(f"Credential provider already exists, updating with current API key...")
        try:
            # Delete existing provider
            acps.delete_api_key_credential_provider(name=MAINTAINX_API_KEY_PARAMETER_NAME)
            print(f"Deleted existing credential provider")
            
            # Wait for deletion to propagate
            time.sleep(5)
            
            # Create new provider with current API key
            response = acps.create_api_key_credential_provider(
                name=MAINTAINX_API_KEY_PARAMETER_NAME,
                apiKey=MAINTAINX_API_KEY,
            )
            credentialProviderARN = response['credentialProviderArn']
            print(f"Created new credential provider with current API key: {credentialProviderARN}")
            
        except Exception as update_error:
            print(f"Error updating credential provider: {update_error}")
            # Try to find existing one as fallback
            try:
                providers = acps.list_api_key_credential_providers()
                credentialProviderARN = None
                for provider in providers.get('credentialProviders', []):
                    if provider['name'] == MAINTAINX_API_KEY_PARAMETER_NAME:
                        credentialProviderARN = provider['credentialProviderArn']
                        print(f"Using existing credential provider: {credentialProviderARN}")
                        print(f"WARNING: API key may not be current!")
                        break
                
                if not credentialProviderARN:
                    print(f"Error: Could not find existing credential provider {MAINTAINX_API_KEY_PARAMETER_NAME}")
                    exit(1)
            except Exception as list_error:
                print(f"Error listing credential providers: {list_error}")
                exit(1)
    else:
        print(f"Error creating credential provider: {e}")
        print(f"Error code: {e.response['Error']['Code']}")
        print(f"Error message: {e.response['Error']['Message']}")
        exit(1)

# Store credential provider ARN in runtime config
update_runtime_config("CREDENTIAL_PROVIDER_ARN", credentialProviderARN)

# Upload OpenAPI specifications to S3
# Create an S3 client
session = boto3.session.Session()
s3_client = session.client('s3')
sts_client = session.client('sts')

# Retrieve AWS account ID and region
account_id = sts_client.get_caller_identity()["Account"]
region = session.region_name or REGION
# Define parameters
# Your s3 bucket to upload the OpenAPI json file.
bucket_name = f'{S3_BUCKET_NAME}-{account_id}-{region}'
file_path = OPENAPI_FILE_PATH
object_key = OPENAPI_FILE_NAME

# Upload the file using put_object and read response
try:
    if region == "us-east-1":
        s3bucket = s3_client.create_bucket(
            Bucket=bucket_name
        )

    with open(file_path, 'rb') as file_data:
        response = s3_client.put_object(
            Bucket=bucket_name,
            Key=object_key,
            Body=file_data
        )

    # Construct the ARN of the uploaded object with account ID and region
    openapi_s3_uri = f's3://{bucket_name}/{object_key}'
    print(f'Uploaded object S3 URI: {openapi_s3_uri}')

except Exception as e:
    print(f'Error uploading file: {e}')
    exit(1)

# S3 Uri for OpenAPI spec file
agentcore_s3_target_config = {
    "mcp": {
          "openApiSchema": {
              "s3": {
                  "uri": openapi_s3_uri
              }
          }
      }
}

# API Key credentials provider configuration
api_key_credential_config = [
    {
        "credentialProviderType" : "API_KEY", 
        "credentialProvider": {
            "apiKeyCredentialProvider": {
                    "credentialParameterName": "Authorization", # Replace this with the name of the api key name expected by the respective API provider. For passing token in the header, use "Authorization"
                    "providerArn": credentialProviderARN,
                    "credentialLocation":"HEADER", # Location of api key. Possible values are "HEADER" and "QUERY_PARAMETER".
                    "credentialPrefix": "Bearer" # Prefix for the token. Valid values are "Basic". Applies only for tokens.
            }
        }
    }
  ]

try:
    response = gateway_client.create_gateway_target(
        gatewayIdentifier=gatewayID,
        name=AGENTCORE_GATEWAY_TARGET_NAME,
        description='OpenAPI Target for generative AI assistant',
        targetConfiguration=agentcore_s3_target_config,
        credentialProviderConfigurations=api_key_credential_config)
    print("Created new gateway target")
except ClientError as e:
    if e.response['Error']['Code'] == 'ConflictException':
        print("Gateway target already exists, skipping creation")
    else:
        raise e

update_runtime_config("AGENTCORE_GATEWAY_TARGET_NAME", AGENTCORE_GATEWAY_TARGET_NAME)
update_runtime_config("MODEL", MODEL)

# Create Knowledge Base for RAG using helper class
print("Creating Knowledge Base for RAG...")
from knowledge_base import BedrockKnowledgeBase

knowledge_base_name = 'maintenance-kb'
knowledge_base_description = "Knowledge Base containing maintenance documentation"
rag_bucket_name = f'maintenance-docs-{account_id}-{region}'

# Create S3 bucket for documents first
print("Creating S3 bucket for documents...")
try:
    if region == "us-east-1":
        s3_client.create_bucket(Bucket=rag_bucket_name)
    else:
        s3_client.create_bucket(
            Bucket=rag_bucket_name,
            CreateBucketConfiguration={'LocationConstraint': region}
        )
    print(f"Created S3 bucket: {rag_bucket_name}")
except ClientError as e:
    if e.response['Error']['Code'] != 'BucketAlreadyOwnedByYou':
        print(f"Error creating bucket: {e}")
        exit(1)

# Upload documents to S3 bucket
print("Uploading documents to S3...")
import os
documents_dir = 'documents'
for filename in os.listdir(documents_dir):
    if filename.endswith('.pdf'):
        file_path = os.path.join(documents_dir, filename)
        s3_client.upload_file(file_path, rag_bucket_name, filename)
        print(f"Uploaded {filename}")

# Create Knowledge Base using helper class
knowledge_base = BedrockKnowledgeBase(
    kb_name=knowledge_base_name,
    kb_description=knowledge_base_description,
    data_bucket_name=rag_bucket_name
)

# Wait for Knowledge Base to be ready
print("Waiting for Knowledge Base to be ready...")
kb_id = knowledge_base.get_knowledge_base_id()
while True:
    kb_response = knowledge_base.bedrock_agent_client.get_knowledge_base(knowledgeBaseId=kb_id)
    status = kb_response['knowledgeBase']['status']
    print(f"Knowledge Base status: {status}")
    if status == 'ACTIVE':
        break
    elif status == 'FAILED':
        raise Exception("Knowledge Base creation failed")
    time.sleep(30)

# Start ingestion job
print("Starting ingestion job...")
try:
    knowledge_base.start_ingestion_job()
    print("Ingestion job started successfully")
except Exception as e:
    print(f"Warning: Failed to start ingestion job: {e}")
    print("You can manually start the ingestion job later from the AWS console")

# Create Lambda function for Knowledge Base access
print("Creating Lambda function for Knowledge Base access...")

# Create Lambda IAM role
lambda_role_name = 'KnowledgeBaseLambdaRole'
lambda_trust_policy = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "lambda.amazonaws.com"},
        "Action": "sts:AssumeRole"
    }]
}

lambda_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        },
        {
            "Effect": "Allow",
            "Action": ["bedrock:Retrieve"],
            "Resource": f"arn:aws:bedrock:{REGION}:{account_id}:knowledge-base/{kb_id}"
        }
    ]
}

iam_client = boto3.client('iam', region_name=REGION)
lambda_client = boto3.client('lambda', region_name=REGION)

try:
    lambda_role = iam_client.create_role(
        RoleName=lambda_role_name,
        AssumeRolePolicyDocument=json.dumps(lambda_trust_policy)
    )
    print(f"Created Lambda IAM role: {lambda_role_name}")
except ClientError as e:
    if e.response['Error']['Code'] == 'EntityAlreadyExists':
        lambda_role = iam_client.get_role(RoleName=lambda_role_name)
        print(f"Using existing Lambda IAM role: {lambda_role_name}")
    else:
        raise e

# Always update the policy to ensure it has the correct Knowledge Base ID
iam_client.put_role_policy(
    RoleName=lambda_role_name,
    PolicyName='KnowledgeBaseLambdaPolicy',
    PolicyDocument=json.dumps(lambda_policy)
)
print(f"Updated Lambda role policy with Knowledge Base ID: {kb_id}")

time.sleep(10)  # Wait for role propagation

# Create Lambda deployment package
with zipfile.ZipFile('lambda_function.zip', 'w') as zip_file:
    zip_file.write('lambda_function.py')

# Create Lambda function
function_name = 'knowledge-base-query'
try:
    with open('lambda_function.zip', 'rb') as zip_file:
        lambda_response = lambda_client.create_function(
            FunctionName=function_name,
            Runtime='python3.9',
            Role=lambda_role['Role']['Arn'],
            Handler='lambda_function.lambda_handler',
            Code={'ZipFile': zip_file.read()},
            Description='Query Knowledge Base for maintenance documentation',
            Timeout=30,
            Environment={
                'Variables': {
                    'KNOWLEDGE_BASE_ID': kb_id
                }
            }
        )
    lambda_arn = lambda_response['FunctionArn']
    print(f"Created Lambda function: {function_name}")
except ClientError as e:
    if e.response['Error']['Code'] == 'ResourceConflictException':
        lambda_response = lambda_client.get_function(FunctionName=function_name)
        lambda_arn = lambda_response['Configuration']['FunctionArn']
        print(f"Using existing Lambda function: {function_name}")
        
        # Update the function's environment variables with the new Knowledge Base ID
        lambda_client.update_function_configuration(
            FunctionName=function_name,
            Environment={
                'Variables': {
                    'KNOWLEDGE_BASE_ID': kb_id
                }
            }
        )
        print(f"Updated Lambda function environment with Knowledge Base ID: {kb_id}")
    else:
        raise e

# Add Lambda role to OpenSearch data access policy
print("Adding Lambda role to OpenSearch data access policy...")
lambda_role_arn = lambda_role['Role']['Arn']

# Get the OpenSearch policy created by BedrockKnowledgeBase
aoss_client = boto3.client('opensearchserverless', region_name=REGION)
policies = aoss_client.list_access_policies(type='data')
kb_policy = None
for policy in policies['accessPolicySummaries']:
    if f'bedrock-sample-rag-ap-{knowledge_base.suffix}' == policy['name']:
        kb_policy = policy
        break

if kb_policy:
    current_policy = aoss_client.get_access_policy(
        name=kb_policy['name'],
        type='data'
    )
    
    policy_doc = current_policy['accessPolicyDetail']['policy']
    if isinstance(policy_doc, str):
        policy_doc = json.loads(policy_doc)
    
    # Check if Lambda role needs to be added
    policy_updated = False
    for rule in policy_doc:
        if 'Principal' in rule:
            principals = rule['Principal']
            if lambda_role_arn not in principals:
                principals.append(lambda_role_arn)
                policy_updated = True
    
    if policy_updated:
        aoss_client.update_access_policy(
            name=kb_policy['name'],
            type='data',
            policyVersion=current_policy['accessPolicyDetail']['policyVersion'],
            policy=json.dumps(policy_doc)
        )
        print("Updated OpenSearch data access policy")
    else:
        print("Lambda role already in OpenSearch data access policy")

# Create Gateway target for Lambda
lambda_target_config = {
    "mcp": {
        "lambda": {
            "lambdaArn": lambda_arn,
            "toolSchema": {
                "inlinePayload": [
                    {
                        "name": "search_knowledge_base",
                        "description": "Search maintenance documentation in the knowledge base",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Search query for maintenance documentation"
                                }
                            },
                            "required": ["query"]
                        }
                    }
                ]
            }
        }
    }
}

# Add Lambda invoke permission to Gateway role
try:
    gateway_details = gateway_client.get_gateway(gatewayIdentifier=gatewayID)
    gateway_info = gateway_details.get('gateway', gateway_details)
    gateway_role_arn = gateway_info['roleArn']
    gateway_role_name = gateway_role_arn.split('/')[-1]
    
    lambda_invoke_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": "lambda:InvokeFunction",
            "Resource": lambda_arn
        }]
    }
    
    iam_client.put_role_policy(
        RoleName=gateway_role_name,
        PolicyName='LambdaInvokePolicy',
        PolicyDocument=json.dumps(lambda_invoke_policy)
    )
    print(f"Added Lambda invoke permission to Gateway role")
except Exception as e:
    print(f"Warning: Could not add Lambda permission to Gateway role: {e}")

credential_config = [{
    "credentialProviderType": "GATEWAY_IAM_ROLE"
}]

try:
    gateway_client.create_gateway_target(
        gatewayIdentifier=gatewayID,
        name='knowledge-base-lambda-target',
        description='Lambda target for Knowledge Base queries',
        targetConfiguration=lambda_target_config,
        credentialProviderConfigurations=credential_config
    )
    print(f"Created Gateway target: knowledge-base-lambda-target")
except ClientError as e:
    if e.response['Error']['Code'] == 'ConflictException':
        print("Gateway target already exists")
    else:
        raise e

# Cleanup
os.remove('lambda_function.zip')


update_runtime_config("LAMBDA_FUNCTION_ARN", lambda_arn)
update_runtime_config("LAMBDA_TARGET_NAME", 'knowledge-base-lambda-target')
update_runtime_config("KNOWLEDGE_BASE_ID", kb_id)
update_runtime_config("RAG_BUCKET_NAME", rag_bucket_name)


print("\n" + "="*80)
print("SETUP COMPLETE!")
print("="*80)
print(f"Knowledge Base ID: {kb_id}")
print(f"S3 Bucket: {rag_bucket_name}")
print(f"Lambda Function: {function_name}")
print(f"Gateway URL: {gatewayURL}")
print(f"Model: {MODEL}")
print("\nRAG functionality is now integrated with the Gateway!")