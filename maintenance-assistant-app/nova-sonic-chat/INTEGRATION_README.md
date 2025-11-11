# Nova Sonic Chat Integration

This directory contains the Nova Sonic speech-to-speech chat interface integrated with the Maintenance Assistant application.

## Overview

The Nova Sonic chat provides real-time voice interaction for maintenance assistance. When users click on alert icons in the main application, this chat interface opens with the fault context pre-loaded.

## Phase 1 Implementation (Current)

### Features
- Speech-to-speech interaction using Amazon Nova Sonic
- Fault context passed from main application via URL parameters
- Standalone HTML interface served on port 5003
- AWS credentials via IAM role (temporary)

### Architecture
- **Server**: Node.js/TypeScript WebSocket server (`src/server.ts`)
- **Client**: HTML/JavaScript frontend (`public/`)
- **Port**: 5003 (configurable via .env)
- **Region**: us-east-1

### URL Parameters
The chat interface receives the following parameters from the main application:
- `asset`: Name of the asset with the alert
- `fault`: Type of fault detected
- `severity`: Severity level (high, medium, low)
- `alert`: Alert ID
- `token`: Cognito JWT token (for future use)

Example URL:
```
http://localhost:5003/?asset=Main%20Roller%20Coaster&fault=OUTER_RACE_FAULT&severity=high&alert=1&token=<JWT_TOKEN>
```

## Setup

### Prerequisites
- Node.js 18+ installed
- AWS credentials configured (via IAM role or environment variables)
- Access to Amazon Bedrock with Nova Sonic model

### Installation
Dependencies are automatically installed when running `start_all_servers.sh` from the parent directory.

Manual installation:
```bash
cd maintenance-assistant-app/nova-sonic-chat
npm install
npm run build
```

### Configuration
**No configuration needed!** The server automatically:
1. Reads Cognito configuration from `runtime_config.json`
2. Extracts JWT token from URL when user clicks alert icon
3. Uses Cognito Identity Pool to exchange JWT for temporary AWS credentials
4. Creates per-user Bedrock clients with those credentials

**Port**: Runs on port 5003 by default (configurable via PORT environment variable)

### Running
The server is automatically started by `start_all_servers.sh`.

Manual start:
```bash
cd maintenance-assistant-app/nova-sonic-chat
npm start
```

## Phase 2 Roadmap (Future)

### Planned Features
1. **AgentCore Integration**: Connect to AgentCore gateway for:
   - RAG-based knowledge base queries
   - MaintainX CMMS integration
3. **Enhanced Context**: Pass additional maintenance data to the AI
4. **Session Management**: Persist chat history across sessions

### Implementation Notes
- **Authentication**: JWT token from URL is used to get AWS credentials via Cognito Identity Pool
- **Per-User Credentials**: Each socket connection gets its own Bedrock client with user-specific credentials
- **Security**: Users can only access Nova Sonic with their own AWS permissions
- **No Shared Credentials**: Unlike Python chat, each user has isolated AWS credentials
- **Backup**: Python chat server (port 5002) remains unchanged as backup

## File Structure
```
nova-sonic-chat/
├── src/
│   ├── server.ts          # Modified WebSocket server with fault context
│   ├── client.ts          # Nova Sonic client (from example)
│   ├── consts.ts          # Constants
│   ├── types.ts           # TypeScript types
│   └── index-cli.ts       # CLI interface (unused)
├── public/
│   ├── index.html         # Main HTML page
│   └── src/
│       ├── main.js        # Modified client-side JavaScript
│       ├── style.css      # Styles with fault context display
│       └── lib/           # Audio player and utilities
├── dist/                  # Compiled JavaScript (generated)
├── package.json           # Node.js dependencies
├── tsconfig.json          # TypeScript configuration
├── .env.example           # Environment variables template
└── INTEGRATION_README.md  # This file
```

## Modifications from Original Example

### Server (`src/server.ts`)
- Changed port from 3000 to 5003
- Added middleware to extract fault context from URL parameters
- Modified session initialization to accept and store fault context
- Injected fault context into system prompt
- Updated AWS credentials to use IAM role (temporary)

### Client (`public/src/main.js`)
- Added fault context extraction from URL parameters
- Updated system prompt for maintenance assistant role
- Added fault context display in UI
- Modified session initialization to pass fault context to server

### Styles (`public/src/style.css`)
- Added fault context card styling
- Added severity level color coding

## Troubleshooting

### Server won't start
- Check `nova_sonic_chat.log` in parent directory
- Verify AWS credentials are configured
- Ensure port 5003 is not in use

### No audio output
- Check browser microphone permissions
- Verify WebSocket connection in browser console
- Check AWS Bedrock access and Nova Sonic model availability

### Fault context not displaying
- Verify URL parameters are being passed correctly
- Check browser console for JavaScript errors
- Ensure main application is passing token correctly

## Integration with Main Application

The main application (`maintenance-assistant-app/src/components/InteractiveMap.js`) has been updated to:
1. Open Nova Sonic chat instead of Python chat when alert icon is clicked
2. Pass fault context and JWT token via URL parameters
3. Open in new window with appropriate dimensions

No other changes were made to the main application to maintain backward compatibility.
