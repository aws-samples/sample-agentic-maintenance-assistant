# Deployment Guide

This guide provides step-by-step instructions for deploying the Industry-Agnostic Generative AI Maintenance Assistant.

## Prerequisites

### AWS Account Setup
- AWS Account with appropriate permissions
- AWS CLI configured with credentials
- AWS Region with Bedrock service availability (recommended: us-east-1, us-west-2)

### Required AWS Services
- Amazon Bedrock (with model access)
- Amazon Bedrock Agent Core
- Amazon Cognito
- AWS Lambda
- Amazon S3
- Amazon OpenSearch Serverless
- AWS IAM

### Local Development Environment
- Python 3.9 or higher
- Node.js 16 or higher
- npm or yarn package manager
- Git

### Required Permissions
Your AWS user/role needs the following permissions:
- `bedrock:*`
- `bedrock-agent:*`
- `bedrock-agentcore:*`
- `cognito-idp:*`
- `cognito-identity:*` (for Identity Pool management)
- `lambda:*`
- `s3:*`
- `opensearch:*`
- `iam:*` (for role creation and management)
- `sts:GetCallerIdentity`
- `sts:AssumeRole` (for credential federation)

## Step 1: Environment Setup

### 1.1 Clone the Repository
```bash
git clone <repository-url>
cd sample-agentic-maintenance-assistant
```

### 1.2 Configure AWS Credentials
```bash
# Option 1: AWS CLI
aws configure

# Option 2: Environment Variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_REGION=us-east-1
```

### 1.3 Install Python Dependencies
```bash
pip install -r requirements.txt
```

## Step 2: Configuration

### 2.1 Create Setup Configuration
Create `setup_config.json` in the root directory. You can use the provided 'setup_config.json.example' file to get started.

```json
{
  "AGENTCORE_GATEWAY_NAME": "maintenance-assistant-gateway",  // Name of the Amazon Bedrock AgentCore Gateway
  "AGENTCORE_GATEWAY_TARGET_NAME": "maintainx-api-target",    // Name of the Amazon Bedrock AgentCore Gateway Target that connects to 3rd party application
  "USER_POOL_NAME": "MaintenanceAssistantUsers",              // Name of the Amazon Cognito User Pool
  "RESOURCE_SERVER_ID": "maintenance-api",                    // ID of the Amazon Cognito OAuth 2.0 Resource Server
  "RESOURCE_SERVER_NAME": "Maintenance API Resource Server",  // Name of the Amazon Cognito OAuth 2.0 Resource Server
  "CLIENT_NAME": "MaintenanceAssistantClient",                // Name of the Amazon Cognito User Pool Client
  "MODEL": "us.amazon.nova-pro-v1:0",                         // Large Language Model used by the Amazon Bedrock AgentCore Gateway
  "MAINTAINX_API_KEY_PARAMETER_NAME": "maintainx-api-key",    // Name of the parameter in the Amazon Bedrock AgentCore Identity that is used to authenticate outbound API requests to the MaintainX application
  "MAINTAINX_API_KEY": "your-maintainx-api-key",              // API key used to authenticate outbound API requests to the MaintainX application      
  "OPENAPI_FILE_PATH": "openapi.json",                        // Path to the OpenAPI specs of the MaintainX application
  "OPENAPI_FILE_NAME": "openapi.json",                        // Full name of the OpenAPI specs file of the MaintainX application
  "S3_BUCKET_NAME": "agentcore-gateway"                       // Name of the Amazon S3 bucket that stores the MaintainX OpenAPI specs file
}
```

### 2.2 Request Bedrock Model Access
1. Go to AWS Bedrock Console
2. Navigate to "Model access"
3. Request access to required models:
   - `us.amazon.nova-pro-v1:0`
   - `anthropic.claude-3-haiku-20240307-v1:0`
   - `amazon.titan-embed-text-v1`

## Step 3: Infrastructure Deployment

### 3.1 Deploy AWS Infrastructure
```bash
python setup.py
```

This script will:
- Create IAM roles and policies for user-based access control
- Set up Amazon Cognito User Pool and Identity Pool
- Configure role-based AWS credential federation
- Create Bedrock Agent Core Gateway with MCP integration
- Set up Knowledge Base with OpenSearch Serverless
- Deploy Lambda function for knowledge base queries
- Upload API specifications to S3
- Configure secure authentication and authorization

### 3.2 Verify Deployment
Check that `runtime_config.json` was created with all necessary values:
```bash
cat runtime_config.json
```

## Step 4: Application Deployment

### 4.1 Start All Services (Recommended)

Use the provided convenience script to start all services at once:

```bash
cd maintenance-assistant-app
chmod +x start_all_servers.sh
./start_all_servers.sh
```

**What this script does:**
- Automatically kills any existing server processes for clean restart
- Checks and installs missing Python/Node.js dependencies
- Starts all backend servers with authentication enabled:
  - Asset API (port 5001) - Asset management with role-based access
  - Main API (port 5000) - Fault detection and simulation
  - Chat Server (port 5002) - Secure AI chat with user credentials
- Starts the React frontend (port 3000) - Authenticated user interface
- Provides detailed status feedback and error handling
- Clean shutdown with Ctrl+C

**Access URLs:**
- Main App: http://localhost:3000

## Step 5: Ready to Use!

**The sample comes pre-configured with everything you need:**

**Sample facility map** - Theme park layout with positioned assets  
**Pre-trained ML models** - LSTM fault classifier and anomaly detector ready to use  
**Sample asset data** - Roller coaster asset with simulator configured  
**Knowledge base documents** - 12 maintenance manuals and procedures  
**Database initialized** - Asset types, simulators, and map configuration  

**You can start testing immediately at http://localhost:3000**

### 5.1 Try the Sample (Recommended)
1. **Access the main app**: http://localhost:3000
2. **Click "Tron" to navigate to simulator**
3. **Click "Simulate Ride"** to generate fault scenarios
4. **View alerts** on the facility map
5. **Click alert indicators** to test AI chat functionality
6. **Ask questions** like "What type of fault is this?" or "Show me the maintenance manual"

### 5.2 Customize for Your Use Case (Optional)

If you want to adapt the sample for your specific industry or assets:

#### Admin Panel Configuration
```bash
# Access admin panel
open http://localhost:3000/admin
```
- Upload your own facility maps
- Configure industry-specific asset types
- Position assets at their physical locations
- Customize branding and company information

#### Train Custom ML Models
```bash
cd maintenance-assistant-app
python lstm_fault_classifier.py  # Train with your data
python generate_all_models.py    # Generate additional models
```

#### Add Your Documentation
```bash
# Add your maintenance manuals to documents folder
cp your_manuals/*.pdf documents/
# Re-run setup to upload to knowledge base
python setup.py
```

## Step 6: Testing and Validation

### 6.1 Test Fault Detection
1. Access the main application at http://localhost:3000
2. Click "Simulate Ride" to generate fault scenarios
3. Verify alerts appear on the facility map
4. Click alert indicators to test chat functionality

### 6.2 Test Conversational AI
1. Ensure you're logged in with a valid user account
2. Click on any alert indicator to open the secure chat interface
3. Ask questions like:
   - "What type of fault is this?"
   - "How do I fix an outer race fault?"
   - "Show me the maintenance manual"
4. Verify responses include relevant documentation with clickable links
5. Confirm that each user operates with their own AWS credentials

### 6.3 Test Admin Functions
1. Access admin panel at http://localhost:3000/admin
2. Test asset creation and positioning
3. Upload new maps and models
4. Verify branding customization

## Step 7: Production Deployment

### 7.1 Environment Variables
For production, use environment variables instead of config files:
```bash
export AWS_REGION=us-east-1
export BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
export COGNITO_USER_POOL_ID=us-east-1_xxxxxxxxx
export GATEWAY_URL=https://xxxxxxxxx.execute-api.us-east-1.amazonaws.com
```

### 7.2 Security Hardening

#### Authentication & Authorization
- Configure strong password policies in Cognito User Pool
- Set appropriate JWT token expiration times
- Implement proper role-based access control (RBAC)
- Enable multi-factor authentication (MFA) for admin users
- Regular audit of user permissions and group memberships

#### Network Security
- Enable VPC endpoints for AWS services
- Configure security groups with minimal required access
- Implement Web Application Firewall (WAF) for public endpoints
- Use HTTPS/TLS for all communications
- Configure CORS policies restrictively

#### Data Protection
- Use AWS Secrets Manager for sensitive configuration
- Enable encryption at rest for all data stores
- Implement proper key rotation policies
- Configure S3 bucket policies with least privilege
- Enable versioning and backup for critical data

#### Monitoring & Compliance
- Enable CloudTrail for comprehensive audit logging
- Set up CloudWatch monitoring and alerting
- Implement user activity monitoring and anomaly detection
- Configure log retention policies per compliance requirements
- Regular security assessments and penetration testing

## Step 8: Monitoring and Maintenance

### 8.1 CloudWatch Monitoring
- Set up custom metrics for application performance
- Configure alarms for error rates and latency
- Monitor AWS service usage and costs

### 8.2 Log Management
- Centralize logs using CloudWatch Logs
- Set up log retention policies
- Configure log-based alerts

### 8.3 Backup and Recovery
- Enable S3 versioning for documents and models
- Backup database regularly
- Document recovery procedures

## Troubleshooting

### Common Issues

#### 1. Bedrock Model Access Denied
- Verify model access is granted in Bedrock console
- Check IAM permissions for Bedrock service
- Ensure correct model ID in configuration

#### 2. Cognito Authentication Errors
- Verify user pool and Identity Pool configuration
- Check JWT token expiration and refresh logic
- Validate redirect URLs and CORS settings
- Ensure Identity Pool has proper IAM role mappings
- Verify user group assignments for role-based access

#### 3. Knowledge Base Query Failures
- Check Lambda function logs in CloudWatch
- Verify OpenSearch collection is active
- Ensure documents are properly ingested

#### 4. Frontend Build Errors
- Clear npm cache: `npm cache clean --force`
- Delete node_modules and reinstall: `rm -rf node_modules && npm install`
- Check Node.js version compatibility

#### 5. User Authentication Issues
- Verify user account is confirmed in Cognito User Pool
- Check if user is assigned to appropriate groups (Administrators, Operators)
- Ensure Identity Pool is configured with correct User Pool
- Verify IAM roles have necessary permissions for user groups
- Check JWT token format and expiration in browser developer tools

#### 6. Chat Server Credential Issues
- Verify user's AWS credentials are being cached properly
- Check server logs for credential validation messages
- Ensure Identity Pool has proper trust relationships
- Verify Bedrock model access permissions for user roles
- Check for expired AWS credentials and refresh logic

### Getting Help
- Check CloudWatch logs for detailed error messages
- Review AWS service health dashboard
- Consult AWS documentation for service-specific issues
- Open GitHub issues for application-specific problems

## Cost Optimization

### AWS Service Costs
- **Bedrock**: Pay-per-token usage
- **OpenSearch Serverless**: Pay-per-OCU (OpenSearch Compute Units)
- **Lambda**: Pay-per-invocation and duration
- **S3**: Storage and request costs
- **Cognito**: Free tier available, then pay-per-MAU

### Optimization Tips
- Use appropriate Bedrock models for your use case
- Configure OpenSearch Serverless capacity limits
- Implement caching to reduce API calls
- Monitor and optimize Lambda function performance
- Use S3 lifecycle policies for document management

## Next Steps

After successful deployment:
1. Customize for your specific industry and use case
2. Integrate with your existing maintenance systems
3. Train models on your actual equipment data
4. Expand to additional facilities and asset types
5. Implement advanced analytics and reporting features