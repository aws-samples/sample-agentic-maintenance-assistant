# Third-Party Licenses

This document lists the third-party dependencies and their licenses used in this sample.

## Python Dependencies

### Core AWS and ML Libraries
- **boto3** - Apache License 2.0 - AWS SDK for Python
- **botocore** - Apache License 2.0 - Low-level interface to AWS services
- **tensorflow** - Apache License 2.0 - Machine learning framework
- **scikit-learn** - BSD 3-Clause - Machine learning library
- **pandas** - BSD 3-Clause - Data manipulation and analysis
- **numpy** - BSD 3-Clause - Numerical computing

### Web Framework and APIs
- **flask** - BSD 3-Clause - Web framework
- **flask-cors** - MIT License - Cross-origin resource sharing for Flask
- **requests** - Apache License 2.0 - HTTP library

### Database and Storage
- **sqlalchemy** - MIT License - SQL toolkit and ORM

### Utilities
- **joblib** - BSD 3-Clause - Lightweight pipelining
- **scipy** - BSD 3-Clause - Scientific computing
- **retrying** - Apache License 2.0 - Retry library
- **opensearch-py** - Apache License 2.0 - OpenSearch client

### Agent Frameworks
- **strands-agents** - Apache License 2.0 - Framework for agentic workflows

## JavaScript/Node.js Dependencies

### React Framework
- **react** - MIT License - JavaScript library for building user interfaces
- **react-dom** - MIT License - React DOM rendering
- **react-scripts** - MIT License - Create React App scripts

### UI Components and Visualization
- **recharts** - MIT License - Composable charting library for React
- **axios** - MIT License - Promise-based HTTP client

### Development Tools
- **react-scripts** - MIT License - Create React App build tools (includes Babel, ESLint, Webpack)
- **serve** - MIT License - Static file serving (if used for production builds)

## Data Sources

### Baseline Vibration Data
- **Factor Robotics Roller Coaster SLAM Dataset** - CC0 Public Domain Dedication
  - Source: https://github.com/Factor-Robotics/Roller-Coaster-SLAM-Dataset
  - License:  Creative Commons Zero v1.0 (CC0) Public Domain Dedication
  - Usage: Baseline accelerometer data for fault simulation
  - Note: CC0 waives copyright and dedicates work to worldwide public domain

## License Compatibility

All third-party dependencies are compatible with the MIT-0 license used by this sample:

- **MIT License**: Compatible - Permissive license allowing commercial and private use
- **BSD 3-Clause**: Compatible - Permissive license similar to MIT
- **Apache License 2.0**: Compatible - Permissive license with patent grant
- **CC0 Public Domain**: Compatible - Public domain dedication, no restrictions

## Notes

1. **Strands Agents**: Apache 2.0 licensed framework for building agentic workflows
2. **Amazon Bedrock AgentCore**: Infrastructure service for deploying and operating AI agents securely at scale, with framework flexibility and specialized agent infrastructure
3. **Factor Robotics Dataset**: CC0 public domain data used as baseline for realistic vibration patterns
4. **CC0 License**: Similar to Unlicense, waives all copyright and places work in public domain
5. **Development Dependencies**: Only used during development, not distributed with sample

## Compliance

This sample complies with all third-party license requirements:
- Attribution provided where required
- No GPL or copyleft licenses that would conflict with MIT-0
- All dependencies are from reputable sources
- No modifications made to third-party code that would require license changes

For the most up-to-date license information, refer to:
- Python dependencies: `requirements.txt` and package documentation
- Node.js dependencies: `maintenance-assistant-app/package.json` and npm registry
- Individual package licenses in `maintenance-assistant-app/node_modules/*/LICENSE` files