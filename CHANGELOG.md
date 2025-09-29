# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 09-29-2025

### Added
- Initial release of Industry-Agnostic Generative AI Maintenance Assistant
- LSTM-based bearing fault classification system
- Real-time asset monitoring and fault simulation
- Interactive facility mapping with alert visualization
- Conversational AI interface using Amazon Bedrock
- RAG-powered maintenance documentation system
- Integration with MaintainX API for work order management
- Admin interface for asset and model management
- Support for multiple industry verticals (Manufacturing, Energy, Transportation, Healthcare)
- Comprehensive ML pipeline with TensorFlow/Keras
- AWS infrastructure automation with CloudFormation-like setup
- Knowledge Base integration with Amazon Bedrock and OpenSearch Serverless
- Authentication and authorization using Amazon Cognito
- Comprehensive documentation and deployment guides

### Features
- **Asset-Model Context**: Each asset has dedicated ML models
- **Fault Detection**: Real-time bearing fault classification (Normal, Outer Race, Inner Race, Ball, Cage)
- **Interactive Maps**: Facility layouts with positioned assets and alert indicators
- **Conversational AI**: Context-aware maintenance assistance
- **Knowledge Base**: RAG system for maintenance documentation
- **External Integration**: MaintainX API for work order management
- **Admin Panel**: Web-based configuration interface
- **Multi-Industry**: Adaptable to various industrial use cases

### Technical Stack
- **Backend**: Python Flask APIs
- **Frontend**: React.js with interactive mapping
- **ML/AI**: TensorFlow, scikit-learn, Amazon Bedrock
- **Database**: SQLite with SQLAlchemy ORM
- **Cloud**: AWS (Bedrock, Lambda, S3, OpenSearch, Cognito)
- **Authentication**: Amazon Cognito with JWT
- **Documentation**: Markdown with comprehensive guides