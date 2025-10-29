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

# Delete Lambda function and role first
if 'LAMBDA_FUNCTION_ARN' in config_data:
    print("Deleting Lambda function and role...")
    lambda_client = boto3.client('lambda', region_name=REGION)
    
    try:
        safe_delete(
            lambda_client.delete_function,
            "Lambda function: knowledge-base-query",
            FunctionName='knowledge-base-query'
        )
    except Exception as e:
        print(f"Lambda function not found: {e}")
    
    try:
        safe_delete(
            iam_client.delete_role_policy,
            "Lambda role policy: KnowledgeBaseLambdaPolicy",
            RoleName='KnowledgeBaseLambdaRole',
            PolicyName='KnowledgeBaseLambdaPolicy'
        )
    except:
        pass
    
    try:
        safe_delete(
            iam_client.delete_role,
            "Lambda IAM role: KnowledgeBaseLambdaRole",
            RoleName='KnowledgeBaseLambdaRole'
        )
    except Exception as e:
        print(f"Lambda role not found: {e}")

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
        
        # Delete OpenSearch Serverless resources (enhanced)
        aoss_client = boto3.client('opensearchserverless', region_name=REGION)
        
        print("Cleaning up OpenSearch Serverless resources...")
        
        # Delete collections
        collection_name = f'bedrock-sample-rag-{suffix}'
        try:
            collections = aoss_client.list_collections(collectionFilters={'name': collection_name})
            for collection in collections.get('collectionSummaries', []):
                safe_delete(
                    aoss_client.delete_collection,
                    f"OpenSearch Collection: {collection['name']}",
                    id=collection['id']
                )
        except Exception as e:
            print(f"Error deleting OpenSearch collection: {e}")
        
        # Delete access policies (comprehensive)
        try:
            access_policies = aoss_client.list_access_policies(type='data')
            for policy in access_policies.get('accessPolicySummaries', []):
                if f'bedrock-sample-rag' in policy['name'] and suffix in policy['name']:
                    safe_delete(
                        aoss_client.delete_access_policy,
                        f"Access Policy: {policy['name']}",
                        name=policy['name'],
                        type='data'
                    )
        except Exception as e:
            print(f"Error deleting access policies: {e}")
        
        # Delete network policies (comprehensive)
        try:
            network_policies = aoss_client.list_security_policies(type='network')
            for policy in network_policies.get('securityPolicySummaries', []):
                if f'bedrock-sample-rag' in policy['name'] and suffix in policy['name']:
                    safe_delete(
                        aoss_client.delete_security_policy,
                        f"Network Policy: {policy['name']}",
                        name=policy['name'],
                        type='network'
                    )
        except Exception as e:
            print(f"Error deleting network policies: {e}")
        
        # Delete encryption policies (comprehensive)
        try:
            encryption_policies = aoss_client.list_security_policies(type='encryption')
            for policy in encryption_policies.get('securityPolicySummaries', []):
                if f'bedrock-sample-rag' in policy['name'] and suffix in policy['name']:
                    safe_delete(
                        aoss_client.delete_security_policy,
                        f"Encryption Policy: {policy['name']}",
                        name=policy['name'],
                        type='encryption'
                    )
        except Exception as e:
            print(f"Error deleting encryption policies: {e}")
        
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

# Delete Cognito Client
if 'USER_POOL_ID' in config_data and 'CLIENT_ID' in config_data:
    try:
        cognito.describe_user_pool_client(
            UserPoolId=config_data['USER_POOL_ID'],
            ClientId=config_data['CLIENT_ID']
        )
        safe_delete(
            cognito.delete_user_pool_client,
            f"Cognito Client: {config_data['CLIENT_ID']}",
            UserPoolId=config_data['USER_POOL_ID'],
            ClientId=config_data['CLIENT_ID']
        )
    except ClientError:
        print(f"Cognito Client {config_data['CLIENT_ID']} already deleted")

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

# Delete IAM Roles
role_names = [
    "sample-lambdagateway-agentcore-gateway-role"
]

for role_name in role_names:
    try:
        # Check if role exists
        iam_client.get_role(RoleName=role_name)
        
        # Detach policies
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

print("\n" + "="*50)
print("Cleanup completed!")
print("\nResources that CANNOT be automatically deleted:")
print("- Config files (setup_config.json, runtime_config.json) - preserved as requested")
print("- Some CloudWatch logs may have retention policies")
print("- IAM roles/policies may have dependencies")
print("\nNote: Some resources may require elevated permissions to delete.")
print("If any resources remain, they can be safely deleted manually from the AWS console.")