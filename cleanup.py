import os
import boto3
import json
from botocore.exceptions import ClientError

REGION = os.environ.get('AWS_REGION', 'us-east-1')
runtime_config_filepath = 'runtime_config.json'

# Load runtime configuration
try:
    with open(runtime_config_filepath, 'r') as config_file:
        config_data = json.load(config_file)
        print("Runtime configuration loaded successfully.")
except FileNotFoundError:
    print("Error: runtime_config.json not found. Nothing to clean up.")
    exit(0)

def safe_delete(func, resource_name, *args, **kwargs):
    try:
        result = func(*args, **kwargs)
        print(f"✓ Deleted {resource_name}")
        return result
    except ClientError as e:
        print(f"✗ Failed to delete {resource_name}: {e}")
    except Exception as e:
        print(f"✗ Error deleting {resource_name}: {e}")

# Initialize clients
gateway_client = boto3.client('bedrock-agentcore-control', region_name=REGION)
cognito = boto3.client("cognito-idp", region_name=REGION)
s3_client = boto3.client('s3', region_name=REGION)
sts_client = boto3.client('sts', region_name=REGION)
iam_client = boto3.client('iam', region_name=REGION)

print("Starting cleanup...")

# Delete Lambda functions and roles
lambda_client = boto3.client('lambda', region_name=REGION)

# Delete Knowledge Base Lambda
if 'LAMBDA_FUNCTION_ARN' in config_data:
    print("Deleting Knowledge Base Lambda function and role...")
    
    try:
        safe_delete(
            lambda_client.delete_function,
            "Lambda function: knowledge-base-query",
            FunctionName='knowledge-base-query'
        )
    except Exception as e:
        print(f"Lambda function not found: {e}")
    
    # Delete all inline policies from the role
    try:
        inline_policies = iam_client.list_role_policies(RoleName='KnowledgeBaseLambdaRole')
        for policy_name in inline_policies.get('PolicyNames', []):
            safe_delete(
                iam_client.delete_role_policy,
                f"Lambda role policy: {policy_name}",
                RoleName='KnowledgeBaseLambdaRole',
                PolicyName=policy_name
            )
        # Wait for policy deletion to propagate
        if inline_policies.get('PolicyNames'):
            time.sleep(2)
    except Exception as e:
        print(f"Error deleting inline policies: {e}")
    
    try:
        safe_delete(
            iam_client.delete_role,
            "Lambda IAM role: KnowledgeBaseLambdaRole",
            RoleName='KnowledgeBaseLambdaRole'
        )
    except Exception as e:
        print(f"Lambda role not found: {e}")

# Delete Post-Confirmation Lambda
if 'POST_CONFIRMATION_LAMBDA_NAME' in config_data:
    print("Deleting Post-Confirmation Lambda function and role...")
    function_name = config_data['POST_CONFIRMATION_LAMBDA_NAME']
    
    try:
        safe_delete(
            lambda_client.delete_function,
            f"Lambda function: {function_name}",
            FunctionName=function_name
        )
    except Exception as e:
        print(f"Lambda function {function_name} not found: {e}")
    
    # Delete the Lambda role
    role_name = "CognitoPostConfirmationRole"
    try:
        # Detach managed policies
        try:
            iam_client.detach_role_policy(
                RoleName=role_name,
                PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
            )
        except:
            pass
        
        # Delete inline policies
        try:
            safe_delete(
                iam_client.delete_role_policy,
                f"Lambda role policy: CognitoGroupManagement",
                RoleName=role_name,
                PolicyName='CognitoGroupManagement'
            )
        except:
            pass
        
        safe_delete(
            iam_client.delete_role,
            f"Lambda IAM role: {role_name}",
            RoleName=role_name
        )
    except Exception as e:
        print(f"Lambda role {role_name} not found: {e}")

# Delete Knowledge Base resources
if 'KNOWLEDGE_BASE_ID' in config_data:
    try:
        print("Deleting Knowledge Base and associated resources...")
        account_id = sts_client.get_caller_identity()["Account"]
        suffix = str(account_id)[:4]
        
        bedrock_agent_client = boto3.client('bedrock-agent', region_name=REGION)
        
        # Update data sources to RETAIN policy first, then delete
        try:
            data_sources = bedrock_agent_client.list_data_sources(
                knowledgeBaseId=config_data['KNOWLEDGE_BASE_ID']
            )
            for ds in data_sources.get('dataSourceSummaries', []):
                try:
                    # Get current data source configuration
                    ds_details = bedrock_agent_client.get_data_source(
                        knowledgeBaseId=config_data['KNOWLEDGE_BASE_ID'],
                        dataSourceId=ds['dataSourceId']
                    )
                    
                    # Update data deletion policy to RETAIN
                    bedrock_agent_client.update_data_source(
                        knowledgeBaseId=config_data['KNOWLEDGE_BASE_ID'],
                        dataSourceId=ds['dataSourceId'],
                        name=ds_details['dataSource']['name'],
                        dataSourceConfiguration=ds_details['dataSource']['dataSourceConfiguration'],
                        dataDeletionPolicy='RETAIN'
                    )
                    print(f"Updated data source {ds['dataSourceId']} to RETAIN policy")
                except Exception as e:
                    print(f"Warning: Could not update data source policy: {e}")
                
                safe_delete(
                    bedrock_agent_client.delete_data_source,
                    f"Data Source: {ds['dataSourceId']}",
                    knowledgeBaseId=config_data['KNOWLEDGE_BASE_ID'],
                    dataSourceId=ds['dataSourceId']
                )
        except Exception as e:
            print(f"Error deleting data sources: {e}")
        
        # Wait a moment for data source updates to propagate
        import time
        time.sleep(30)
        
        # Delete Knowledge Base
        safe_delete(
            bedrock_agent_client.delete_knowledge_base,
            f"Knowledge Base: {config_data['KNOWLEDGE_BASE_ID']}",
            knowledgeBaseId=config_data['KNOWLEDGE_BASE_ID']
        )
        
        # Delete OpenSearch Serverless resources (enhanced and comprehensive)
        aoss_client = boto3.client('opensearchserverless', region_name=REGION)
        
        print("Cleaning up OpenSearch Serverless resources...")
        print(f"Looking for resources with suffix: {suffix}")
        
        # First, delete collections (this is the main cost driver)
        print("Step 1: Deleting OpenSearch Collections...")
        try:
            collections = aoss_client.list_collections()
            found_collections = False
            for collection in collections.get('collectionSummaries', []):
                collection_name = collection['name']
                if 'bedrock-sample-rag' in collection_name and suffix in collection_name:
                    found_collections = True
                    print(f"Found collection: {collection_name} (ID: {collection['id']})")
                    safe_delete(
                        aoss_client.delete_collection,
                        f"OpenSearch Collection: {collection_name}",
                        id=collection['id']
                    )
            
            if found_collections:
                print("Waiting 30 seconds for collection deletion to propagate...")
                import time
                time.sleep(30)
            else:
                print("No matching collections found")
                
        except Exception as e:
            print(f"Error deleting OpenSearch collections: {e}")
        
        # Delete access policies (comprehensive)
        print("Step 2: Deleting Access Policies...")
        try:
            access_policies = aoss_client.list_access_policies(type='data')
            found_policies = False
            for policy in access_policies.get('accessPolicySummaries', []):
                policy_name = policy['name']
                if 'bedrock-sample-rag' in policy_name and suffix in policy_name:
                    found_policies = True
                    print(f"Found access policy: {policy_name}")
                    safe_delete(
                        aoss_client.delete_access_policy,
                        f"Access Policy: {policy_name}",
                        name=policy_name,
                        type='data'
                    )
            if not found_policies:
                print("No matching access policies found")
        except Exception as e:
            print(f"Error deleting access policies: {e}")
        
        # Delete network policies (comprehensive)
        print("Step 3: Deleting Network Policies...")
        try:
            network_policies = aoss_client.list_security_policies(type='network')
            found_policies = False
            for policy in network_policies.get('securityPolicySummaries', []):
                policy_name = policy['name']
                if 'bedrock-sample-rag' in policy_name and suffix in policy_name:
                    found_policies = True
                    print(f"Found network policy: {policy_name}")
                    safe_delete(
                        aoss_client.delete_security_policy,
                        f"Network Policy: {policy_name}",
                        name=policy_name,
                        type='network'
                    )
            if not found_policies:
                print("No matching network policies found")
        except Exception as e:
            print(f"Error deleting network policies: {e}")
        
        # Delete encryption policies (comprehensive)
        print("Step 4: Deleting Encryption Policies...")
        try:
            encryption_policies = aoss_client.list_security_policies(type='encryption')
            found_policies = False
            for policy in encryption_policies.get('securityPolicySummaries', []):
                policy_name = policy['name']
                if 'bedrock-sample-rag' in policy_name and suffix in policy_name:
                    found_policies = True
                    print(f"Found encryption policy: {policy_name}")
                    safe_delete(
                        aoss_client.delete_security_policy,
                        f"Encryption Policy: {policy_name}",
                        name=policy_name,
                        type='encryption'
                    )
            if not found_policies:
                print("No matching encryption policies found")
        except Exception as e:
            print(f"Error deleting encryption policies: {e}")
        
        print("OpenSearch Serverless cleanup completed!")
        
        # Delete KB-specific IAM roles and policies
        kb_role_names = [f'AmazonBedrockExecutionRoleForKnowledgeBase_{suffix}']
        kb_policy_names = [
            f'AmazonBedrockFoundationModelPolicyForKnowledgeBase_{suffix}',
            f'AmazonBedrockS3PolicyForKnowledgeBase_{suffix}',
            f'AmazonBedrockOSSPolicyForKnowledgeBase_{suffix}'
        ]
        
        for role_name in kb_role_names:
            try:
                for policy_name in kb_policy_names:
                    try:
                        policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"
                        iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
                    except:
                        pass
                
                safe_delete(
                    iam_client.delete_role,
                    f"KB IAM Role: {role_name}",
                    RoleName=role_name
                )
            except Exception as e:
                print(f"Error deleting KB role {role_name}: {e}")
        
        for policy_name in kb_policy_names:
            try:
                policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"
                safe_delete(
                    iam_client.delete_policy,
                    f"KB IAM Policy: {policy_name}",
                    PolicyArn=policy_arn
                )
            except Exception as e:
                print(f"Error deleting KB policy {policy_name}: {e}")
                
    except Exception as e:
        print(f"Error with KB cleanup: {e}")

# Delete Gateway and Targets (proper order)
if 'GATEWAY_URL' in config_data:
    # Extract gateway ID from subdomain (before .gateway.bedrock-agentcore)
    gateway_id = config_data['GATEWAY_URL'].split('//')[1].split('.')[0]
    print(f"Cleaning up Gateway: {gateway_id}")
    
    # First, list and delete all targets
    try:
        targets_response = gateway_client.list_gateway_targets(gatewayIdentifier=gateway_id)
        targets = targets_response.get('items', [])
        
        for target in targets:
            safe_delete(
                gateway_client.delete_gateway_target,
                f"Gateway Target: {target['name']}",
                gatewayIdentifier=gateway_id,
                targetId=target['targetId']
            )
        
        # Wait for targets to be fully deleted
        if targets:
            print("Waiting for targets to be deleted...")
            import time
            time.sleep(10)
        
        # Now delete the gateway
        safe_delete(
            gateway_client.delete_gateway,
            f"Gateway: {gateway_id}",
            gatewayIdentifier=gateway_id
        )
        
    except Exception as e:
        print(f"Error cleaning up gateway: {e}")

# Delete API Key Credential Provider
try:
    response = gateway_client.list_api_key_credential_providers()
    for provider in response.get('credentialProviders', []):
        if 'maintainx' in provider['name'].lower() or 'MaintainxAPIKey' in provider['name']:
            safe_delete(
                gateway_client.delete_api_key_credential_provider,
                f"Credential Provider: {provider['name']}",
                name=provider['name']
            )
except Exception as e:
    print(f"Error with credential providers: {e}")

# Delete S3 buckets
try:
    account_id = sts_client.get_caller_identity()["Account"]
    bucket_names = [
        f'maintainx-openapi-{account_id}-{REGION}',
        f'maintenance-docs-{account_id}-{REGION}'
    ]
    
    for bucket_name in bucket_names:
        try:
            response = s3_client.list_objects_v2(Bucket=bucket_name)
            if 'Contents' in response:
                objects = [{'Key': obj['Key']} for obj in response['Contents']]
                s3_client.delete_objects(Bucket=bucket_name, Delete={'Objects': objects})
                print(f"✓ Deleted objects from S3 bucket: {bucket_name}")
            
            safe_delete(
                s3_client.delete_bucket,
                f"S3 Bucket: {bucket_name}",
                Bucket=bucket_name
            )
        except ClientError as e:
            if e.response['Error']['Code'] != 'NoSuchBucket':
                print(f"Error with bucket {bucket_name}: {e}")
except Exception as e:
    print(f"Error deleting S3 resources: {e}")

# Delete Cognito Clients (M2M and User App)
if 'USER_POOL_ID' in config_data:
    # Delete M2M Client
    if 'CLIENT_ID' in config_data:
        try:
            cognito.describe_user_pool_client(
                UserPoolId=config_data['USER_POOL_ID'],
                ClientId=config_data['CLIENT_ID']
            )
            safe_delete(
                cognito.delete_user_pool_client,
                f"Cognito M2M Client: {config_data['CLIENT_ID']}",
                UserPoolId=config_data['USER_POOL_ID'],
                ClientId=config_data['CLIENT_ID']
            )
        except ClientError:
            print(f"Cognito M2M Client {config_data['CLIENT_ID']} already deleted")
    
    # Delete User App Client
    if 'USER_APP_CLIENT_ID' in config_data:
        try:
            cognito.describe_user_pool_client(
                UserPoolId=config_data['USER_POOL_ID'],
                ClientId=config_data['USER_APP_CLIENT_ID']
            )
            safe_delete(
                cognito.delete_user_pool_client,
                f"Cognito User App Client: {config_data['USER_APP_CLIENT_ID']}",
                UserPoolId=config_data['USER_POOL_ID'],
                ClientId=config_data['USER_APP_CLIENT_ID']
            )
        except ClientError:
            print(f"Cognito User App Client {config_data['USER_APP_CLIENT_ID']} already deleted")

# Delete Cognito Resource Server
if 'USER_POOL_ID' in config_data and 'RESOURCE_SERVER_ID' in config_data:
    try:
        cognito.describe_resource_server(
            UserPoolId=config_data['USER_POOL_ID'],
            Identifier=config_data['RESOURCE_SERVER_ID']
        )
        safe_delete(
            cognito.delete_resource_server,
            f"Resource Server: {config_data['RESOURCE_SERVER_ID']}",
            UserPoolId=config_data['USER_POOL_ID'],
            Identifier=config_data['RESOURCE_SERVER_ID']
        )
    except ClientError:
        print(f"Resource Server {config_data['RESOURCE_SERVER_ID']} already deleted")

# Delete Cognito Identity Pool and associated roles
if 'IDENTITY_POOL_ID' in config_data:
    print("Deleting Cognito Identity Pool and associated roles...")
    cognito_identity = boto3.client('cognito-identity', region_name=REGION)
    
    try:
        # Get identity pool details to find associated roles
        identity_pool = cognito_identity.describe_identity_pool(
            IdentityPoolId=config_data['IDENTITY_POOL_ID']
        )
        
        # Delete the identity pool
        safe_delete(
            cognito_identity.delete_identity_pool,
            f"Identity Pool: {config_data['IDENTITY_POOL_ID']}",
            IdentityPoolId=config_data['IDENTITY_POOL_ID']
        )
        
        # Delete associated IAM roles (actual role names from utils.py)
        role_names = [
            'MaintenanceAdministrator',
            'MaintenanceOperator',
            'MaintenanceViewer'
        ]
        
        for role_name in role_names:
            try:
                # Detach all policies
                try:
                    attached_policies = iam_client.list_attached_role_policies(RoleName=role_name)
                    for policy in attached_policies['AttachedPolicies']:
                        iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy['PolicyArn'])
                except:
                    pass
                
                # Delete inline policies
                try:
                    inline_policies = iam_client.list_role_policies(RoleName=role_name)
                    for policy_name in inline_policies['PolicyNames']:
                        iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
                except:
                    pass
                
                safe_delete(
                    iam_client.delete_role,
                    f"Identity Pool IAM Role: {role_name}",
                    RoleName=role_name
                )
            except ClientError as e:
                if e.response['Error']['Code'] != 'NoSuchEntity':
                    print(f"Error deleting role {role_name}: {e}")
                    
    except Exception as e:
        print(f"Error deleting Identity Pool: {e}")

# Delete Cognito User Groups
if 'USER_POOL_ID' in config_data:
    print("Deleting Cognito User Groups...")
    group_names = ['Administrators', 'Operators', 'Viewers']
    
    for group_name in group_names:
        try:
            safe_delete(
                cognito.delete_group,
                f"Cognito Group: {group_name}",
                GroupName=group_name,
                UserPoolId=config_data['USER_POOL_ID']
            )
        except ClientError as e:
            if e.response['Error']['Code'] != 'ResourceNotFoundException':
                print(f"Error deleting group {group_name}: {e}")

# Delete Cognito User Pool Domain first, then User Pool
if 'USER_POOL_ID' in config_data:
    try:
        pool_info = cognito.describe_user_pool(UserPoolId=config_data['USER_POOL_ID'])
        if 'Domain' in pool_info['UserPool']:
            safe_delete(
                cognito.delete_user_pool_domain,
                f"User Pool Domain: {pool_info['UserPool']['Domain']}",
                Domain=pool_info['UserPool']['Domain'],
                UserPoolId=config_data['USER_POOL_ID']
            )
            import time
            time.sleep(30)  # Wait for domain deletion
    except Exception as e:
        print(f"Error deleting domain: {e}")
    
    safe_delete(
        cognito.delete_user_pool,
        f"User Pool: {config_data['USER_POOL_ID']}",
        UserPoolId=config_data['USER_POOL_ID']
    )

# Delete Gateway IAM Role (with all inline policies including Lambda invoke)
role_names = [
    "sample-lambdagateway-agentcore-gateway-role"
]

for role_name in role_names:
    try:
        # Check if role exists
        iam_client.get_role(RoleName=role_name)
        
        # Detach managed policies
        try:
            attached_policies = iam_client.list_attached_role_policies(RoleName=role_name)
            for policy in attached_policies['AttachedPolicies']:
                iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy['PolicyArn'])
                print(f"✓ Detached policy {policy['PolicyName']} from {role_name}")
        except:
            pass
        
        # Delete ALL inline policies (including LambdaInvokePolicy)
        try:
            inline_policies = iam_client.list_role_policies(RoleName=role_name)
            for policy_name in inline_policies['PolicyNames']:
                safe_delete(
                    iam_client.delete_role_policy,
                    f"Inline policy: {policy_name} from {role_name}",
                    RoleName=role_name,
                    PolicyName=policy_name
                )
        except:
            pass
        
        # Delete role
        safe_delete(
            iam_client.delete_role,
            f"IAM Role: {role_name}",
            RoleName=role_name
        )
    except ClientError as e:
        if e.response['Error']['Code'] != 'NoSuchEntity':
            print(f"Error with IAM role {role_name}: {e}")

# Clean up CloudWatch Log Groups
print("Cleaning up CloudWatch Log Groups...")
logs_client = boto3.client('logs', region_name=REGION)

log_group_prefixes = [
    '/aws/lambda/knowledge-base-query',
    '/aws/lambda/CognitoPostConfirmationTrigger',
    '/aws/bedrock/agentcore',
    '/aws/opensearch/collections'
]

for prefix in log_group_prefixes:
    try:
        response = logs_client.describe_log_groups(logGroupNamePrefix=prefix)
        for log_group in response.get('logGroups', []):
            safe_delete(
                logs_client.delete_log_group,
                f"Log Group: {log_group['logGroupName']}",
                logGroupName=log_group['logGroupName']
            )
    except Exception as e:
        print(f"Error deleting log groups with prefix {prefix}: {e}")

# Verification step - check for remaining OpenSearch resources
print("\n" + "="*50)
print("VERIFICATION: Checking for remaining OpenSearch resources...")
try:
    aoss_client = boto3.client('opensearchserverless', region_name=REGION)
    account_id = sts_client.get_caller_identity()["Account"]
    suffix = str(account_id)[:4]
    
    # Check for remaining collections
    collections = aoss_client.list_collections()
    remaining_collections = [c for c in collections.get('collectionSummaries', []) 
                           if 'bedrock-sample-rag' in c['name'] and suffix in c['name']]
    
    # Check for remaining policies
    access_policies = aoss_client.list_access_policies(type='data')
    remaining_access = [p for p in access_policies.get('accessPolicySummaries', []) 
                      if 'bedrock-sample-rag' in p['name'] and suffix in p['name']]
    
    if remaining_collections:
        print("⚠️  WARNING: OpenSearch Collections still exist:")
        for collection in remaining_collections:
            print(f"   - {collection['name']} (ID: {collection['id']}) - STATUS: {collection['status']}")
        print("   These may continue to incur charges!")
    
    if remaining_access:
        print("⚠️  WARNING: Access policies still exist:")
        for policy in remaining_access:
            print(f"   - {policy['name']}")
    
    if not remaining_collections and not remaining_access:
        print("✅ SUCCESS: No OpenSearch Serverless resources found!")
        print("💰 You should no longer be charged for OpenSearch Serverless.")
    
except Exception as e:
    print(f"Could not verify OpenSearch cleanup: {e}")

print("\n" + "="*50)
print("Cleanup completed!")
print("\nResources that CANNOT be automatically deleted:")
print("- Config files (setup_config.json, runtime_config.json) - preserved as requested")
print("- Some CloudWatch logs may have retention policies")
print("- IAM roles/policies may have dependencies")
print("\nNote: Some resources may require elevated permissions to delete.")
print("If any resources remain, they can be safely deleted manually from the AWS console.")