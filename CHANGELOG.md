# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.1] - 09-10-2026

### Fixed
- **Text chat startup failure on newer `mcp` versions**: `chat_server.py` imported
  `streamablehttp_client` from `mcp.client.streamable_http`, which `mcp` 2.x renamed to
  `streamable_http_client` and changed to drop the `headers` argument in favour of a
  pre-configured `httpx2.AsyncClient`. The import and transport helper are now version
  adaptive, so the Python chat server starts and initializes its AgentCore MCP client on
  both older and newer `mcp` releases.
- **Voice-mode work order creation failing with "Error processing response stream"**: the
  Nova Sonic `queryMaintainX` handler now normalizes `create_work_order` parameters —
  synthesizing the MaintainX-required `title` when the model omits it and mapping
  `asset_id` to the API's camelCase `assetId`. The `queryMaintainX` tool description was
  clarified so the model supplies the correct fields. Non-JSON tool results (such as
  MaintainX validation errors) are now wrapped in JSON so a tool error no longer crashes
  the bidirectional response stream.

### Notes
- Voice (Nova Sonic) and text chat remain independent backends and do not share
  conversation context; a request in one mode is not aware of the other. Cross-mode shared
  context is not implemented.
- The Bedrock model is configured via the `MODEL` value in `runtime_config.json`. The
  previously referenced `anthropic.claude-3-haiku-20240307-v1:0` has been retired; use a
  currently available model or inference-profile ID for your account (for example
  `us.anthropic.claude-haiku-4-5-20251001-v1:0`).

## [2.0.0] - 11-12-2025

### Added
- Nova Sonic speech-to-speech interface replacing text-based chat
- Real-time voice interaction with maintenance assistant
- WebSocket-based audio streaming for low-latency responses

### Changed
- Enhanced setup.py with automatic credential provider management
- Improved error handling
- Temporarily removed text-based chat functionality. Will be added back in the next release, so both text and audio can be used together

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