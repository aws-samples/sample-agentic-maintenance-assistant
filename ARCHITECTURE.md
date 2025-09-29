# Architecture Overview

This document provides a detailed technical architecture overview of the Industry-Agnostic Generative AI Maintenance Assistant.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interface Layer                     │
├─────────────────────────────────────────────────────────────────┤
│  React Frontend  │  Admin Panel  │  Interactive Maps  │  Chat   │
│  (Authenticated) │  (Role-based) │  (Real-time)       │ (Secure)│
└─────────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────────────────────────────────────┐
│                      Application Layer                          │
├─────────────────────────────────────────────────────────────────┤
│  Asset API       │  Chat Server  │  Main API        │  Utils    │
│  (Flask + Auth)  │  (User Creds) │  (Flask + Auth)  │  (Shared) │
└─────────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────────────────────────────────────┐
│                    Machine Learning Layer                       │
├─────────────────────────────────────────────────────────────────┤
│  LSTM Classifier │  Fault Sim.   │  Bearing Sim.    │  Models   │
│  (TensorFlow)    │  (NumPy/SciPy)│  (Signal Proc.)  │  (H5/PKL) │
└─────────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────────────────────────────────────┐
│                      AWS Services Layer                         │
├─────────────────────────────────────────────────────────────────┤
│  Bedrock Agent   │  Knowledge     │  Lambda          │  Cognito │
│  Core Gateway    │  Base + RAG    │  Functions       │  Identity│
│                  │                │                  │  Pool    │
│  OpenSearch      │  S3 Storage    │  IAM Roles       │  MCP     │
│  Serverless      │  (Docs/Models) │  & Policies      │  Tools   │
└─────────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────────────────────────────────────┐
│                    External Integrations                        │
├─────────────────────────────────────────────────────────────────┤
│  MaintainX API   │  Industry      │  Sensor Data     │  Third   │
│     (CMMS)       │  Simulators    │  Sources         │  Party   │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. User Interface Layer

#### React Frontend
- **Interactive Maps**: SVG-based facility layouts with asset positioning
- **Real-time Alerts**: Visual indicators for fault conditions
- **Dashboard**: Asset status, performance metrics, and system health
- **Responsive Design**: Mobile and desktop compatibility

#### Admin Panel
- **Asset Management**: CRUD operations for assets, types, and models
- **Map Configuration**: Upload and configure facility layouts
- **Model Management**: ML model upload and configuration
- **Branding**: Customizable company branding and themes

#### Chat Interface
- **Conversational AI**: Natural language maintenance assistance
- **Context Awareness**: Alert-specific guidance and troubleshooting
- **Document Integration**: RAG-powered responses with maintenance manuals
- **Multi-modal**: Text and document-based interactions

### 2. Application Layer

#### Asset API (`asset_api.py`)
- **Secure Authentication**: JWT token verification with role-based access control
- **RESTful Endpoints**: Standard CRUD operations with permission checks
- **Database Integration**: SQLAlchemy ORM with SQLite
- **File Management**: Secure map and model file uploads with audit logging
- **Configuration**: Persistent settings and branding (Admin-only access)
- **Role-based Permissions**: Administrators have full access, Operators have read access

#### Chat Server (`chat_server.py`)
- **Secure Authentication**: JWT token verification with Cognito
- **User-based AWS Credentials**: Identity Pool integration for per-user access
- **Credential Caching**: Automatic AWS credential refresh and caching
- **Bedrock Integration**: Claude 3 Haiku with user-specific credentials
- **MCP Client**: Model Context Protocol for tool integration
- **Knowledge Base**: RAG queries with presigned URL generation
- **Context Management**: Alert context and conversation history

#### API Server (`api_server.py`)
- **Secure Authentication**: JWT token verification with role-based access
- **Fault Detection**: Real-time LSTM-based classification
- **Simulation Engine**: Realistic bearing fault simulation with audit logging
- **Alert Management**: Fault detection and notification system
- **Analytics**: Frequency domain analysis and performance metrics
- **User Permissions**: Administrators can train models, Operators can run simulations

#### Runtime Engine (`runtime.py`)
- **System Orchestration**: Main application coordinator
- **Authentication**: Cognito token management
- **Gateway Integration**: Bedrock Agent Core connectivity
- **Tool Management**: MCP tool registration and execution

### 3. Machine Learning Layer

#### LSTM Fault Classifier
- **Architecture**: Multi-layer LSTM with batch normalization
- **Input**: Time-series accelerometer data (100Hz, 3-axis)
- **Output**: Fault classification with confidence scores
- **Classes**: Normal, Outer Race, Inner Race, Ball, Cage faults
- **Training**: Synthetic fault injection with real baseline data

#### Bearing Fault Simulator
- **Physics-Based**: Realistic bearing mechanics simulation
- **Fault Types**: Characteristic frequency patterns for each fault
- **Severity Levels**: Configurable fault intensity
- **Signal Processing**: Frequency domain analysis and filtering

#### Ride Simulator
- **Operational Scenarios**: Theme park ride cycle simulation
- **Fault Injection**: Probabilistic fault occurrence
- **Performance Metrics**: G-force, RMS acceleration, peak events
- **Data Generation**: Training and testing dataset creation

### 4. AWS Services Layer

#### Amazon Bedrock
- **Agent Core Gateway**: Tool integration and orchestration
- **Foundation Models**: Claude 3 Haiku for chat, Nova Pro for gateway
- **Knowledge Bases**: RAG system for maintenance documentation
- **Vector Embeddings**: Titan Embed for document similarity

#### Amazon Cognito
- **User Pools**: Authentication and user management
- **Identity Pools**: AWS credential federation for users
- **Resource Servers**: API access control
- **JWT Tokens**: Secure API authentication with automatic refresh
- **OAuth 2.0**: Standard authentication flows
- **Role-based Access**: Different AWS permissions per user group

#### AWS Lambda
- **Knowledge Base Queries**: Serverless document retrieval
- **Event Processing**: Asynchronous task execution
- **API Gateway Integration**: RESTful endpoint exposure
- **Cost Optimization**: Pay-per-use execution model

#### Amazon S3
- **Document Storage**: Maintenance manuals and procedures
- **Model Artifacts**: Trained ML models and preprocessors
- **Static Assets**: Frontend resources and media files
- **Versioning**: Document and model version control

#### Amazon OpenSearch Serverless
- **Vector Storage**: Document embeddings and similarity search
- **Indexing**: Automatic document processing and indexing
- **Search**: Fast semantic search capabilities
- **Scaling**: Automatic capacity management

### 5. Data Flow Architecture

#### Fault Detection Pipeline
1. **Data Ingestion**: Sensor data from simulators or real equipment
2. **Preprocessing**: Signal filtering and feature extraction
3. **ML Inference**: LSTM model prediction with confidence scoring
4. **Alert Generation**: Threshold-based fault detection
5. **Notification**: Real-time alerts to operators and systems

#### Conversational AI Pipeline
1. **Authentication**: JWT token verification and user identification
2. **Credential Exchange**: User JWT token → AWS credentials via Identity Pool
3. **User Query**: Natural language maintenance question with context
4. **Secure Tool Execution**: MCP tool calls with user-specific AWS credentials
5. **Knowledge Retrieval**: RAG queries with presigned URLs for documents
6. **Response Generation**: AI-powered maintenance guidance with citations
7. **Audit Logging**: User actions and system responses for compliance

#### Asset Management Pipeline
1. **Asset Registration**: Physical asset digital twin creation
2. **Model Assignment**: ML model association with assets
3. **Map Positioning**: Spatial asset placement on facility maps
4. **Status Monitoring**: Real-time asset health tracking

### 6. Security Architecture

#### Authentication Flow
1. **User Login**: Cognito User Pool authentication
2. **JWT Token**: Secure token with user identity and groups
3. **Identity Pool**: JWT token exchange for AWS credentials
4. **Credential Caching**: Server-side caching with automatic refresh
5. **API Access**: User-specific AWS credentials for all operations

#### Authorization Model
- **Role-based Access Control**: Different AWS IAM roles per user group
- **Resource-level Permissions**: Fine-grained access to AWS services
- **API Gateway Protection**: All endpoints require valid JWT tokens
- **Audit Trail**: Complete logging of user actions and system responses

#### Data Security
- **Encryption in Transit**: HTTPS/TLS for all communications
- **Encryption at Rest**: S3 and OpenSearch data encryption
- **Credential Isolation**: Each user operates with their own AWS credentials
- **Token Expiration**: Automatic JWT and AWS credential refresh

#### Network Security
- **CORS Configuration**: Restricted cross-origin requests
- **API Rate Limiting**: Protection against abuse
- **Input Validation**: Sanitization of all user inputs
- **Error Handling**: Secure error messages without sensitive data exposure

This architecture provides a robust, scalable, and secure foundation for asset maintenance applications across multiple industry verticals with enterprise-grade security controls.