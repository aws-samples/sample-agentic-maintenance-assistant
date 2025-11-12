# Phase 2 Architecture Diagram

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           User Interface                                 │
│                                                                          │
│  ┌──────────────┐         ┌──────────────┐        ┌──────────────┐    │
│  │   Browser    │         │  Microphone  │        │   Speaker    │    │
│  │   (React)    │◄────────┤   (Audio)    │────────►│   (Audio)    │    │
│  └──────┬───────┘         └──────────────┘        └──────────────┘    │
│         │                                                               │
│         │ WebSocket (Socket.IO)                                        │
└─────────┼───────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Nova Sonic Server (Node.js)                         │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                    Socket.IO Handler                            │    │
│  │  • Receives audio chunks                                        │    │
│  │  • Manages session lifecycle                                    │    │
│  │  • Injects fault context                                        │    │
│  └────────────────┬───────────────────────────────────────────────┘    │
│                   │                                                     │
│                   ▼                                                     │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │         NovaSonicBidirectionalStreamClient                      │    │
│  │  • Manages bidirectional streaming                              │    │
│  │  • Handles tool use events                                      │    │
│  │  • Routes to appropriate tool handler                           │    │
│  └────────────┬───────────────────────────┬───────────────────────┘    │
│               │                           │                             │
│               │ User JWT                  │ Tool Calls                  │
│               │ (per-user)                │                             │
└───────────────┼───────────────────────────┼─────────────────────────────┘
                │                           │
                ▼                           ▼
┌───────────────────────────┐   ┌──────────────────────────────────────┐
│   Amazon Bedrock          │   │   AgentCore MCP Client               │
│   (Nova Sonic Model)      │   │   • M2M Authentication               │
│                           │   │   • Token Management                 │
│   • Speech-to-Text        │   │   • MCP Protocol Handler             │
│   • LLM Processing        │   └──────────┬───────────────────────────┘
│   • Tool Selection        │              │
│   • Text-to-Speech        │              │ M2M Token
│                           │              │ (service-level)
└───────────────────────────┘              │
                                           ▼
                              ┌────────────────────────────────────────┐
                              │   AgentCore Gateway                    │
                              │   • MCP Server                         │
                              │   • Tool Routing                       │
                              │   • Authorization                      │
                              └──────────┬─────────────┬───────────────┘
                                         │             │
                                         ▼             ▼
                        ┌────────────────────┐  ┌─────────────────────┐
                        │  RAG Target        │  │  MaintainX Target   │
                        │  (Lambda)          │  │  (Lambda)           │
                        │                    │  │                     │
                        │  • Knowledge Base  │  │  • Asset API        │
                        │  • Vector Search   │  │  • Work Orders      │
                        │  • Document Retrieval│  │  • Parts Inventory│
                        └────────────────────┘  └─────────────────────┘
```

## Authentication Flow

```
┌──────────────┐
│   User       │
└──────┬───────┘
       │ 1. Login
       ▼
┌──────────────────┐
│  Cognito User    │
│  Pool            │
└──────┬───────────┘
       │ 2. JWT Token
       ▼
┌──────────────────┐         ┌──────────────────┐
│  Nova Sonic      │         │  AgentCore MCP   │
│  Server          │         │  Client          │
└──────┬───────────┘         └──────┬───────────┘
       │                            │
       │ 3. User JWT                │ 4. M2M Credentials
       │    (per-user)              │    (service-level)
       ▼                            ▼
┌──────────────────┐         ┌──────────────────┐
│  Cognito         │         │  Cognito OAuth2  │
│  Identity Pool   │         │  Token Endpoint  │
└──────┬───────────┘         └──────┬───────────┘
       │                            │
       │ 5. AWS Credentials         │ 6. Access Token
       ▼                            ▼
┌──────────────────┐         ┌──────────────────┐
│  Amazon Bedrock  │         │  AgentCore       │
│  (Nova Sonic)    │         │  Gateway         │
└──────────────────┘         └──────────────────┘
```

## Tool Execution Flow

```
User Speech: "How do I replace a bearing?"
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│  1. Speech-to-Text (Nova Sonic)                          │
│     Output: "How do I replace a bearing?"                │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│  2. LLM Processing (Nova Sonic)                          │
│     • Analyzes query                                     │
│     • Decides to use searchKnowledgeBase tool            │
│     • Generates tool call                                │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│  3. Tool Use Event                                       │
│     {                                                    │
│       toolName: "searchKnowledgeBase",                   │
│       toolUseContent: {                                  │
│         content: '{"query": "bearing replacement"}'     │
│       }                                                  │
│     }                                                    │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│  4. processToolUse() in client.ts                        │
│     • Parses tool name: "searchknowledgebase"            │
│     • Extracts query: "bearing replacement"              │
│     • Routes to AgentCore MCP Client                     │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│  5. AgentCore MCP Client                                 │
│     • Gets/refreshes M2M token                           │
│     • Calls: knowledge-base-lambda-target___search_...   │
│     • Sends MCP request to Gateway                       │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│  6. AgentCore Gateway                                    │
│     • Validates token                                    │
│     • Routes to RAG target                               │
│     • Invokes Lambda function                            │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│  7. RAG Target (Lambda)                                  │
│     • Queries Knowledge Base                             │
│     • Performs vector search                             │
│     • Retrieves relevant documents                       │
│     • Returns: "Bearing Replacement SOP..."              │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│  8. Tool Result Event                                    │
│     {                                                    │
│       toolUseId: "...",                                  │
│       result: {                                          │
│         content: "Step 1: Shut down equipment..."        │
│       }                                                  │
│     }                                                    │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│  9. LLM Processing (Nova Sonic)                          │
│     • Receives tool result                               │
│     • Generates natural language response                │
│     • Synthesizes speech                                 │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│  10. Text-to-Speech (Nova Sonic)                         │
│      Output: Audio stream with instructions              │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼
              User hears response
```

## Meta-Tool Pattern

```
┌─────────────────────────────────────────────────────────┐
│              Nova Sonic Session Start                    │
│                                                          │
│  Tools Defined (Static):                                │
│  ┌────────────────────────────────────────────────┐    │
│  │  1. getDateAndTimeTool (built-in)              │    │
│  │  2. getWeatherTool (built-in)                  │    │
│  │  3. searchKnowledgeBase (meta-tool) ◄──────────┼────┼─ Routes to
│  │  4. queryMaintainX (meta-tool) ◄───────────────┼────┼─ AgentCore
│  └────────────────────────────────────────────────┘    │
│                                                          │
└─────────────────────────────────────────────────────────┘
                                │
                                │ Tool calls routed at runtime
                                ▼
┌─────────────────────────────────────────────────────────┐
│           AgentCore Gateway (Dynamic)                    │
│                                                          │
│  Available Tools (Discovered at Runtime):               │
│  ┌────────────────────────────────────────────────┐    │
│  │  • knowledge-base-lambda-target___search_...    │    │
│  │  • maintainx-lambda-mcp-target___list_assets   │    │
│  │  • maintainx-lambda-mcp-target___get_asset     │    │
│  │  • maintainx-lambda-mcp-target___list_work_... │    │
│  │  • maintainx-lambda-mcp-target___get_work_...  │    │
│  │  • maintainx-lambda-mcp-target___search        │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Session Lifecycle

```
1. User Connects
   ├─ WebSocket established
   ├─ JWT token provided
   └─ Fault context passed

2. Session Initialization
   ├─ Create Bedrock client (user JWT)
   ├─ Attach AgentCore MCP client (M2M token)
   ├─ Create Nova Sonic session
   └─ Define tools (including meta-tools)

3. Prompt Start
   ├─ Inject system prompt
   ├─ Add fault context
   ├─ Add tool usage instructions
   └─ Set toolChoice: "any"

4. Audio Start
   ├─ Configure audio input
   ├─ Start bidirectional streaming
   └─ Ready for user speech

5. Conversation Loop
   ├─ User speaks
   ├─ Nova Sonic processes
   ├─ Tool calls (if needed)
   │  ├─ Meta-tool invoked
   │  ├─ Routed to AgentCore
   │  └─ Result returned
   ├─ Response generated
   └─ Speech synthesized

6. Session End
   ├─ Stop audio
   ├─ End prompt
   ├─ Close session
   └─ Cleanup resources
```

## Error Handling

```
┌─────────────────────────────────────────────────────────┐
│                    Error Scenarios                       │
└─────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│ AgentCore     │ │ Tool          │ │ Token         │
│ Unavailable   │ │ Execution     │ │ Refresh       │
│               │ │ Failure       │ │ Failure       │
└───────┬───────┘ └───────┬───────┘ └───────┬───────┘
        │                 │                 │
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│ Graceful      │ │ Error to      │ │ Retry with    │
│ Degradation   │ │ Nova Sonic    │ │ New Token     │
│               │ │               │ │               │
│ • Use default │ │ • User        │ │ • Automatic   │
│   tools only  │ │   informed    │ │   refresh     │
│ • Log warning │ │ • Retry       │ │ • Transparent │
│ • Continue    │ │   possible    │ │   to user     │
└───────────────┘ └───────────────┘ └───────────────┘
```

## Key Design Decisions

### 1. Meta-Tool Pattern
**Why:** Nova Sonic requires tools at session start, but AgentCore tools are dynamic
**Solution:** Two static meta-tools that route to dynamic AgentCore tools at runtime

### 2. Dual Authentication
**Why:** Different security contexts for user actions vs. service actions
**Solution:** User JWT for Bedrock, M2M token for AgentCore

### 3. Tool Choice Enforcement
**Why:** Prevent hallucination, ensure grounded responses
**Solution:** `toolChoice: "any"` forces Nova Sonic to use at least one tool

### 4. Graceful Degradation
**Why:** System should work even if AgentCore is unavailable
**Solution:** Server continues with default tools, logs warning

### 5. Token Caching
**Why:** Reduce latency and API calls
**Solution:** Cache M2M token with 5-minute safety margin before expiry
