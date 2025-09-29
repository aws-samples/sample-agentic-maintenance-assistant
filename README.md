# Sample Agentic Maintenance Assistant

An intelligent maintenance system that combines asset monitoring, fault simulation, and conversational AI to provide predictive maintenance capabilities across industries.

## Overview

This sample demonstrates an asset-model context approach where physical assets are monitored through industry-specific simulators and machine learning models. The system provides real-time fault detection, interactive mapping, and AI-powered maintenance assistance with user credential management.

## Core Concepts

### Simulators

Simulators generate realistic operational data and fault conditions for specific industry equipment:

- **Manufacturing**: Machinery simulators for CNC machines, conveyor systems, robotic arms
- **Energy**: Motor-generator sets, turbines, transformers in power generation facilities  
- **Transportation**: Vehicle systems, rail equipment, aircraft components
- **Healthcare**: Medical imaging equipment, HVAC systems, laboratory instruments

Each simulator models normal operation and various fault scenarios (bearing wear, electrical faults, vibration anomalies) specific to the equipment type. Simulators can be customized by modifying fault probability distributions, operational parameters, and sensor data patterns in the simulator classes.

### Asset-Model Context

The system follows an asset-model relationship where:
- Each physical asset has a unique digital representation
- Machine learning models are trained on data specific to individual assets
- Models cannot be shared between assets as each has unique operational characteristics
- Asset performance is continuously monitored through its dedicated model

### Interactive Mapping

Assets are positioned on facility maps providing spatial context for maintenance operations. Maps can be customized through the admin interface by uploading facility layouts and positioning assets at their physical locations.

### Fault Detection and Alerts

When simulators generate fault conditions, the system:
1. Processes sensor data through asset-specific ML models
2. Generates alerts for detected anomalies
3. Displays alert indicators on the facility map
4. Enables drill-down investigation through conversational AI

### Conversational AI Integration

Clicking on alert indicators opens a secure chat interface powered by Amazon Bedrock, providing:
- Fault diagnosis assistance with user-specific AWS credentials
- Maintenance procedure guidance with document retrieval
- Parts and documentation lookup via knowledge base
- Historical maintenance data analysis
- Enterprise-grade authentication and authorization

### Machine Learning Model Development

The system uses multiple ML approaches for fault detection:

**Data Source**: Baseline vibration data is derived from the open-source [Roller Coaster SLAM dataset](https://github.com/Factor-Robotics/Roller-Coaster-SLAM-Dataset) by Factor Robotics. The original ROS bag file was converted to CSV format containing accelerometer readings (accel_x, accel_y, accel_z) and timestamps.

**Active Model**:
- **LSTM Fault Classifier**: Deep learning model for time-series fault classification using TensorFlow/Keras. This is the primary model used during simulation to classify bearing faults in roller coaster vehicles based on vibration sequences:
  - **NORMAL**: Healthy bearing operation with minimal vibration
  - **OUTER_RACE_FAULT**: Defect in the outer bearing ring causing periodic impacts
  - **INNER_RACE_FAULT**: Damage to the inner bearing ring with load-modulated vibration
  - **BALL_FAULT**: Damaged rolling element creating double-impact signatures
  - **CAGE_FAULT**: Bearing cage damage causing low-frequency modulation

**Reference Models** (provided as examples, not integrated):
- **Anomaly Detector** (`anomaly_detector.py`): Isolation Forest model that detects deviations from normal operational patterns using statistical features extracted from vibration data
- **Failure Predictor** (`generate_all_models.py`): Random Forest classifier for predicting maintenance needs based on operational parameters like vibration levels, operating hours, and temperature

**Training Process**:
1. Baseline normal operation data from the roller coaster dataset
2. Synthetic fault injection using bearing fault simulators
3. Feature extraction from vibration signatures
4. LSTM model training with fault-specific frequency patterns
5. Validation using cross-validation and holdout test sets

**Model Outputs**:
- `lstm_fault_classifier.py` → `lstm_fault_model.h5`, `lstm_scaler.pkl`, `lstm_label_encoder.pkl`, `lstm_metadata.pkl`
- `anomaly_detector.py` → `anomaly_detector.pkl`, `scaler.pkl` (reference only)
- `generate_all_models.py` → `failure_predictor.pkl` (reference only)

**Fault Simulation**: The bearing fault simulator generates realistic fault conditions by modifying the baseline vibration data with characteristic fault frequencies for outer race, inner race, ball, and cage defects.

## Architecture

```
├── setup.py                       # AWS infrastructure setup
├── cleanup.py                     # Resource cleanup
├── runtime.py                     # Environment validation script
├── utils.py                       # Shared utilities and AWS helpers
├── maintenance-assistant-app/     # Sample application
│   ├── models/                    # ML models directory
│   ├── templates/                 # Chat interface templates
│   ├── api_server.py              # Fault detection API
│   ├── asset_api.py               # Asset management API with authentication
│   ├── chat_server.py             # Secure chat server with user credentials
│   ├── lstm_fault_classifier.py   # Neural network classifier
│   ├── bearing_fault_simulator.py # Equipment simulator
│   ├── start_all_servers.sh       # Unified server startup script
│   └── src/                       # React frontend with authentication
├── documents/                     # Knowledge base documents
├── openapi.json                   # MaintainX CMMS OpenAPI specification
└── lambda_function.py             # Knowledge base query function
```

### Generative AI Components

- **Amazon Bedrock**: Foundation model access with user-based credentials
  - AgentCore Gateway: Configurable model (default: Amazon Nova Pro)
  - Chat Server: Claude 3 Haiku for conversational AI
- **Amazon Bedrock Agent Core**: Gateway for tool integration with MCP support
- **Amazon Bedrock Knowledge Bases**: RAG for maintenance documentation
- **AWS Lambda**: Serverless knowledge base queries
- **Amazon OpenSearch Serverless**: Vector storage for documents
- **Amazon Cognito**: Authentication, authorization, and Identity Pool integration
- **Model Context Protocol (MCP)**: Tool integration and external system connectivity

## Quick Start

1. **Pre-requisite**  
For demonstrating Amazon Bedrock AgentCore MCP integration capability to an external 3rd party application, we will use an AWS Parter solution - [MaintainX](https://www.getmaintainx.com/), which is a Computerized Maintenance Management System(CMMS). It is free to sign-up without a credit card. You'll need to create an account and request for an API key to use this demo. The procedure to do this is mentioned in [this URL](https://api.getmaintainx.com/v1/docs). Usage of this application is governed by [MaintainX's Terms and Conditions](https://www.getmaintainx.com/terms-of-service).

2. **Configure AWS credentials and region**
   ```bash
   export AWS_ACCESS_KEY_ID=your_access_key
   export AWS_SECRET_ACCESS_KEY=your_secret_key
   export AWS_REGION=your_region
   ```

3. **Update `setup_config.json` with your parameters**
   - `AGENTCORE_GATEWAY_NAME`: Your gateway name
   - `USER_POOL_NAME`: Cognito user pool name
   - `MAINTAINX_API_KEY`: Your API key for MaintainX API integrations to Amazon Bedrock AgentCore
   - `MODEL`: Foundation model (e.g., "us.amazon.nova-pro-v1:0")

4. **Install dependencies and deploy infrastructure**
   ```bash
   pip install -r requirements.txt
   python setup.py
   ```

5. **Install React front-end web application dependencies**
   ```bash
   cd maintenance-assistant-app
   npm install
   ```

6. **Initialize sample data (optional but recommended)**
   ```bash
   cd maintenance-assistant-app
   python3 init_db.py
   ```
   This creates a SQLite database (`theme_park.db`) with sample data including:
   - **Theme Park Map**: Pre-configured facility layout with positioning
   - **Roller Coaster Asset**: Sample asset positioned on the map
   - **Simulator Configuration**: Ready-to-use fault simulation setup
   - **Asset Types and Models**: Complete demo environment
   
   **Without this step**: The application shows a "No Map Configured" message and requires manual setup through the admin panel.
   
   **With this step**: You get a fully working demo with interactive map, positioned assets, and fault simulation capabilities right away.

7. **Start the application (recommended approach)**
   ```bash
   cd maintenance-assistant-app
   chmod +x start_all_servers.sh
   ./start_all_servers.sh
   ```
   This script handles dependency checking, clean restarts, and provides detailed status feedback. The script performs a clean restart, so just run it again after configuration changes.

8. **Sign-up for a new user account**
   - Navigate to `http://localhost:3000`
   - Click "Create Account"
   - Fill in username, email, and password
   - Check your email for verification code
   - Enter the code to activate your account
   - Sign in with your credentials

9. **Access the admin panel to configure assets and maps**
   - Admin panel: `http://localhost:3000/admin`
   - Upload facility maps, create asset models based on asset simulators, create assets based on asset models (you'll need to attach one unique machine learning model file per asset), and finally position assets at their physical locations on the facility map

10. **Run simulators to generate fault scenarios**
   - Click on assets in the interactive map to view details
   - Simulate faults through the asset simulator landing page
   - Choose specific fault types or let the system select random conditions
   - Return to the homepage with the facility map
   - Alert indicators appear on the facility map when faults are detected
   - Click alert indicators to open the secure AI-powered chat interface
   - Chat with the maintenance assistant using your authenticated session

## Customization

### Industry Adaptation

1. **Branding**: Modify company name, description, and terminology through admin settings
2. **Simulators**: Create industry-specific simulators by extending base simulator class provided
3. **ML Models**: Train models on actual equipment data for production deployment
4. **Documentation**: Replace sample maintenance docs with industry-specific procedures
5. **Maps**: Upload facility layouts and position assets accordingly

### Simulator Development

Industry-specific simulators should implement:
- Normal operational parameter ranges
- Fault injection mechanisms
- Sensor data generation patterns
- Equipment-specific failure modes

Example simulator structure for manufacturing equipment:
```python
class ManufacturingEquipmentSimulator:
    def simulate_normal_operation(self):
        # Generate normal sensor readings
    
    def inject_bearing_fault(self):
        # Simulate bearing degradation
    
    def inject_electrical_fault(self):
        # Simulate electrical anomalies
```

## Testing

Run the test suite to verify your installation:

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html
```

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on how to submit pull requests, report issues, and contribute to the project.

## Security

See [SECURITY.md](SECURITY.md) for information about reporting security vulnerabilities and security best practices.

## Architecture

For detailed technical architecture information, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Deployment

For comprehensive deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a detailed history of changes and releases.

## License

This sample code is made available under the MIT-0 license. See the [LICENSE](LICENSE) file.

## Disclaimer

Sample code, software libraries, command line tools, proofs of concept, templates, or other related technology are provided as AWS Content or Third-Party Content under the AWS Customer Agreement, or the relevant written agreement between you and AWS (whichever applies). You should not use this AWS Content or Third-Party Content in your production accounts, or on production or other critical data. You are responsible for testing, securing, and optimizing the AWS Content or Third-Party Content, such as sample code, as appropriate for production grade use based on your specific quality control practices and standards. Deploying AWS Content or Third-Party Content may incur AWS charges for creating or using AWS chargeable resources, such as running Amazon EC2 instances or using Amazon S3 storage.