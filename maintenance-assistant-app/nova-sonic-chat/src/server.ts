import express from 'express';
import http from 'http';
import path from 'path';
import { Server } from 'socket.io';
import { fromCognitoIdentityPool } from "@aws-sdk/credential-providers";
import { NovaSonicBidirectionalStreamClient, StreamSession } from './client';
import { createAgentCoreMCPClient, AgentCoreMCPClient } from './agentcore-mcp-client';
import { Buffer } from 'node:buffer';
import * as fs from 'fs';

// Load runtime config to get Cognito configuration
const runtimeConfigPath = path.join(__dirname, '../../../runtime_config.json');
const runtimeConfig = JSON.parse(fs.readFileSync(runtimeConfigPath, 'utf-8'));

const REGION = 'us-east-1';
const IDENTITY_POOL_ID = runtimeConfig.IDENTITY_POOL_ID;
const USER_POOL_ID = runtimeConfig.USER_POOL_ID;
const GATEWAY_URL = runtimeConfig.GATEWAY_URL;
const CLIENT_ID = runtimeConfig.CLIENT_ID;
const CLIENT_SECRET = runtimeConfig.CLIENT_SECRET;
const RESOURCE_SERVER_ID = runtimeConfig.RESOURCE_SERVER_ID;

// Set environment variable for MCP client to access
if (RESOURCE_SERVER_ID) {
    process.env.RESOURCE_SERVER_ID = RESOURCE_SERVER_ID;
}

console.log('Cognito Configuration:');
console.log('  Identity Pool ID:', IDENTITY_POOL_ID);
console.log('  User Pool ID:', USER_POOL_ID);
console.log('  Gateway URL:', GATEWAY_URL);

// Create Express app and HTTP server
const app = express();
const server = http.createServer(app);
const io = new Server(server);

// Store Bedrock clients per socket (each user gets their own client with their JWT credentials)
const socketBedrockClients = new Map<string, NovaSonicBidirectionalStreamClient>();

// Global AgentCore MCP Client (uses M2M token for service authentication)
let agentCoreMCPClient: AgentCoreMCPClient | undefined;

// Initialize AgentCore MCP Client on server startup
(async () => {
    try {
        console.log('Initializing AgentCore MCP Client...');
        agentCoreMCPClient = await createAgentCoreMCPClient(
            GATEWAY_URL,
            CLIENT_ID,
            CLIENT_SECRET,
            USER_POOL_ID,
            REGION
        );
        console.log('AgentCore MCP Client initialized successfully');
    } catch (error) {
        console.error('Failed to initialize AgentCore MCP Client:', error);
        console.log('Server will continue without AgentCore integration');
    }
})();

// Middleware to parse URL parameters and inject fault context
app.use((req, res, next) => {
    // Extract fault context from URL parameters
    const asset = req.query.asset as string;
    const fault = req.query.fault as string;
    const severity = req.query.severity as string;
    const alert = req.query.alert as string;
    const token = req.query.token as string;

    // Store context in request for later use
    if (asset || fault || severity || alert || token) {
        (req as any).faultContext = {
            asset: asset || 'Unknown Asset',
            fault: fault || 'Unknown Fault',
            severity: severity || 'unknown',
            alert: alert || '',
            token: token || ''
        };
    }
    next();
});

// Function to create Bedrock client with user's JWT token
function createBedrockClientForUser(jwtToken: string): NovaSonicBidirectionalStreamClient {
    console.log('Creating Bedrock client with user JWT token');
    
    const credentials = fromCognitoIdentityPool({
        clientConfig: { region: REGION },
        identityPoolId: IDENTITY_POOL_ID,
        logins: {
            [`cognito-idp.${REGION}.amazonaws.com/${USER_POOL_ID}`]: jwtToken
        }
    });

    return new NovaSonicBidirectionalStreamClient({
        requestHandlerConfig: {
            maxConcurrentStreams: 10,
        },
        clientConfig: {
            region: REGION,
            credentials: credentials
        },
        agentCoreMCPClient: agentCoreMCPClient
    });
}

// Note: We no longer create a single global bedrockClient
// Each socket connection will have its own client with user-specific credentials

// Track active sessions per socket
const socketSessions = new Map<string, StreamSession>();

// Session states
enum SessionState {
    INITIALIZING = 'initializing',
    READY = 'ready',
    ACTIVE = 'active',
    CLOSED = 'closed'
}

const sessionStates = new Map<string, SessionState>();
const cleanupInProgress = new Map<string, boolean>();

// Store fault context per socket
const socketContexts = new Map<string, any>();

// Periodically check for and close inactive sessions (every minute)
// Sessions with no activity for over 5 minutes will be force closed
setInterval(() => {
    console.log("Session cleanup check");
    const now = Date.now();

    // Check all socket clients for inactive sessions
    socketBedrockClients.forEach((client, socketId) => {
        client.getActiveSessions().forEach(sessionId => {
            const lastActivity = client.getLastActivityTime(sessionId);

            // If no activity for 5 minutes, force close
            if (now - lastActivity > 5 * 60 * 1000) {
                console.log(`Closing inactive session ${sessionId} after 5 minutes of inactivity`);
                try {
                    client.forceCloseSession(sessionId);
                } catch (error) {
                    console.error(`Error force closing inactive session ${sessionId}:`, error);
                }
            }
        });
    });
}, 60000);

// Serve static files from the public directory
app.use(express.static(path.join(__dirname, '../public')));

// Helper function to create and initialize a new session
async function createNewSession(socket: any, faultContext?: any): Promise<StreamSession> {
    const sessionId = socket.id;

    try {
        console.log(`Creating new session for client: ${sessionId}`);
        if (faultContext) {
            console.log(`Fault context: Asset=${faultContext.asset}, Fault=${faultContext.fault}, Severity=${faultContext.severity}`);
        }
        sessionStates.set(sessionId, SessionState.INITIALIZING);

        // Get the Bedrock client for this socket (created with user's JWT)
        const bedrockClient = socketBedrockClients.get(sessionId);
        if (!bedrockClient) {
            throw new Error(`No Bedrock client found for socket ${sessionId}`);
        }

        // Create session with the correct API
        const session = bedrockClient.createStreamSession(sessionId);

        // Set up event handlers
        setupSessionEventHandlers(session, socket);

        // Store the session (don't initiate AWS Bedrock connection yet)
        socketSessions.set(sessionId, session);
        sessionStates.set(sessionId, SessionState.READY);

        console.log(`Session ${sessionId} created and ready, stored in maps`);
        console.log(`Session map size: ${socketSessions.size}, States map size: ${sessionStates.size}`);
        console.log(`Stored session for ${sessionId}:`, !!socketSessions.get(sessionId));
        
        return session;
    } catch (error) {
        console.error(`Error creating session for ${sessionId}:`, error);
        sessionStates.set(sessionId, SessionState.CLOSED);
        throw error;
    }
}

// Helper function to set up event handlers for a session
function setupSessionEventHandlers(session: StreamSession, socket: any) {
    session.onEvent('usageEvent', (data) => {
        console.log('usageEvent:', data);
        socket.emit('usageEvent', data);
    });

    session.onEvent('completionStart', (data) => {
        console.log('completionStart:', data);
        socket.emit('completionStart', data);
    });

    session.onEvent('contentStart', (data) => {
        console.log('contentStart:', data);
        socket.emit('contentStart', data);
    });

    session.onEvent('textOutput', (data) => {
        console.log('Text output:', data);
        socket.emit('textOutput', data);
    });

    session.onEvent('audioOutput', (data) => {
        console.log('Audio output received, sending to client');
        socket.emit('audioOutput', data);
    });

    session.onEvent('error', (data) => {
        console.error('Error in session:', data);
        socket.emit('error', data);
    });

    session.onEvent('toolUse', (data) => {
        console.log('Tool use detected:', data.toolName);
        socket.emit('toolUse', data);
    });

    session.onEvent('toolResult', (data) => {
        console.log('Tool result received');
        socket.emit('toolResult', data);
    });

    session.onEvent('contentEnd', (data) => {
        console.log('Content end received: ', data);
        socket.emit('contentEnd', data);
    });

    session.onEvent('streamComplete', () => {
        console.log('Stream completed for client:', socket.id);
        socket.emit('streamComplete');
        sessionStates.set(socket.id, SessionState.CLOSED);
    });
}

// Socket.IO connection handler
io.on('connection', (socket) => {
    console.log('New client connected:', socket.id);

    // Don't create session immediately - wait for client to request it
    sessionStates.set(socket.id, SessionState.CLOSED);

    // Connection count logging (only set up once per connection)
    const connectionInterval = setInterval(() => {
        const connectionCount = Object.keys(io.sockets.sockets).length;
        console.log(`Active socket connections: ${connectionCount}`);
    }, 60000);

    // Handle session initialization request with fault context
    socket.on('initializeConnection', async (faultContext, callback) => {
        try {
            const currentState = sessionStates.get(socket.id);
            console.log(`Initializing session for ${socket.id}, current state: ${currentState}`);
            
            // Store fault context for this socket
            if (faultContext) {
                socketContexts.set(socket.id, faultContext);
                console.log(`Stored fault context for ${socket.id}:`, faultContext);
                
                // Create Bedrock client with user's JWT token
                if (faultContext.token) {
                    console.log(`Creating Bedrock client for ${socket.id} with JWT token`);
                    const bedrockClient = createBedrockClientForUser(faultContext.token);
                    socketBedrockClients.set(socket.id, bedrockClient);
                } else {
                    throw new Error('No JWT token provided in fault context');
                }
            } else {
                throw new Error('No fault context provided');
            }
            
            if (currentState === SessionState.INITIALIZING || currentState === SessionState.READY || currentState === SessionState.ACTIVE) {
                console.log(`Session already exists for ${socket.id}, state: ${currentState}`);
                if (callback) callback({ success: true });
                return;
            }

            await createNewSession(socket, faultContext);

            // Get the Bedrock client for this socket
            const bedrockClient = socketBedrockClients.get(socket.id);
            if (!bedrockClient) {
                throw new Error('Bedrock client not initialized');
            }

            // Start the AWS Bedrock connection
            console.log(`Starting AWS Bedrock connection for ${socket.id}`);
            bedrockClient.initiateBidirectionalStreaming(socket.id);

            // Update state to active
            sessionStates.set(socket.id, SessionState.ACTIVE);

            if (callback) callback({ success: true });

        } catch (error) {
            console.error('Error initializing session:', error);
            sessionStates.set(socket.id, SessionState.CLOSED);
            if (callback) callback({ success: false, error: error instanceof Error ? error.message : String(error) });
            socket.emit('error', {
                message: 'Failed to initialize session',
                details: error instanceof Error ? error.message : String(error)
            });
        }
    });

    // Handle starting a new chat (after stopping previous one)
    socket.on('startNewChat', async () => {
        try {
            const currentState = sessionStates.get(socket.id);
            console.log(`Starting new chat for ${socket.id}, current state: ${currentState}`);
            
            // Get the Bedrock client for this socket
            const bedrockClient = socketBedrockClients.get(socket.id);
            if (!bedrockClient) {
                throw new Error('No Bedrock client found for socket');
            }
            
            // Clean up existing session if any
            const existingSession = socketSessions.get(socket.id);
            if (existingSession && bedrockClient.isSessionActive(socket.id)) {
                console.log(`Cleaning up existing session for ${socket.id}`);
                try {
                    await existingSession.endAudioContent();
                    await existingSession.endPrompt();
                    await existingSession.close();
                } catch (cleanupError) {
                    console.error(`Error during cleanup for ${socket.id}:`, cleanupError);
                    bedrockClient.forceCloseSession(socket.id);
                }
                socketSessions.delete(socket.id);
            }

            // Get stored fault context
            const faultContext = socketContexts.get(socket.id);

            // Create new session
            await createNewSession(socket, faultContext);
        } catch (error) {
            console.error('Error starting new chat:', error);
            socket.emit('error', {
                message: 'Failed to start new chat',
                details: error instanceof Error ? error.message : String(error)
            });
        }
    });

    // Audio input handler with session validation
    socket.on('audioInput', async (audioData) => {
        try {
            const session = socketSessions.get(socket.id);
            const currentState = sessionStates.get(socket.id);

            if (!session || currentState !== SessionState.ACTIVE) {
                console.error(`Invalid session state for audio input: session=${!!session}, state=${currentState}`);
                socket.emit('error', {
                    message: 'No active session for audio input',
                    details: `Session exists: ${!!session}, Session state: ${currentState}. Session must be ACTIVE to receive audio.`
                });
                return;
            }

            // Convert base64 string to Buffer
            const audioBuffer = typeof audioData === 'string'
                ? Buffer.from(audioData, 'base64')
                : Buffer.from(audioData);

            // Stream the audio
            await session.streamAudio(audioBuffer);

        } catch (error) {
            console.error('Error processing audio:', error);
            socket.emit('error', {
                message: 'Error processing audio',
                details: error instanceof Error ? error.message : String(error)
            });
        }
    });

    socket.on('promptStart', async () => {
        try {
            const session = socketSessions.get(socket.id);
            const currentState = sessionStates.get(socket.id);
            console.log(`Prompt start received for ${socket.id}, session exists: ${!!session}, state: ${currentState}`);
            
            if (!session) {
                console.error(`No session found for promptStart: ${socket.id}`);
                socket.emit('error', { message: 'No active session for prompt start' });
                return;
            }

            await session.setupSessionAndPromptStart();
            console.log(`Prompt start completed for ${socket.id}`);
        } catch (error) {
            console.error('Error processing prompt start:', error);
            socket.emit('error', {
                message: 'Error processing prompt start',
                details: error instanceof Error ? error.message : String(error)
            });
        }
    });

    socket.on('systemPrompt', async (data) => {
        try {
            const session = socketSessions.get(socket.id);
            const currentState = sessionStates.get(socket.id);
            console.log(`System prompt received for ${socket.id}, session exists: ${!!session}, state: ${currentState}`);
            
            if (!session) {
                console.error(`No session found for systemPrompt: ${socket.id}`);
                socket.emit('error', { message: 'No active session for system prompt' });
                return;
            }

            // Get fault context and inject it into system prompt
            const faultContext = socketContexts.get(socket.id);
            let systemPromptText = data;
            
            if (faultContext) {
                const contextPrefix = `\n\nCurrent Alert Context:\n- Asset: ${faultContext.asset}\n- Fault Type: ${faultContext.fault}\n- Severity: ${faultContext.severity}\n- Alert ID: ${faultContext.alert}\n\nPlease assist the user with this specific maintenance issue.`;
                systemPromptText = data + contextPrefix;
                console.log(`Injected fault context into system prompt for ${socket.id}`);
            }

            // Add tool usage instructions if AgentCore is available
            if (agentCoreMCPClient) {
                const toolInstructions = `\n\nYou have access to maintenance tools that provide current, facility-specific information:

1. searchKnowledgeBase - Use for repair procedures, troubleshooting guides, and technical documentation
2. queryMaintainX - Use for asset locations, work order status, and team information

When the user asks about asset locations or "where is" something, use queryMaintainX with action "list_assets".
When the user asks how to fix or repair something, use searchKnowledgeBase.

After using a tool, provide a clear, concise answer based on the results. Do not call multiple tools unless the user's question requires it.`;
                systemPromptText = systemPromptText + toolInstructions;
                console.log(`Added tool usage instructions to system prompt for ${socket.id}`);
            }

            await session.setupSystemPrompt(undefined, systemPromptText);
            console.log(`System prompt completed for ${socket.id}`);
        } catch (error) {
            console.error('Error processing system prompt:', error);
            socket.emit('error', {
                message: 'Error processing system prompt',
                details: error instanceof Error ? error.message : String(error)
            });
        }
    });

    socket.on('audioStart', async (data) => {
        try {
            const session = socketSessions.get(socket.id);
            const currentState = sessionStates.get(socket.id);
            console.log(`Audio start received for ${socket.id}, session exists: ${!!session}, state: ${currentState}`);
            
            if (!session) {
                console.error(`No session found for audioStart: ${socket.id}`);
                socket.emit('error', { message: 'No active session for audio start' });
                return;
            }

            // Set up audio configuration
            await session.setupStartAudio();
            console.log(`Audio start setup completed for ${socket.id}`);

            // Emit confirmation that session is fully ready for audio
            socket.emit('audioReady');
        } catch (error) {
            console.error('Error processing audio start:', error);
            sessionStates.set(socket.id, SessionState.CLOSED);
            socket.emit('error', {
                message: 'Error processing audio start',
                details: error instanceof Error ? error.message : String(error)
            });
        }
    });

    socket.on('stopAudio', async () => {
        try {
            const session = socketSessions.get(socket.id);
            if (!session || cleanupInProgress.get(socket.id)) {
                console.log('No active session to stop or cleanup already in progress');
                return;
            }

            console.log('Stop audio requested, beginning proper shutdown sequence');
            cleanupInProgress.set(socket.id, true);
            sessionStates.set(socket.id, SessionState.CLOSED);

            // Chain the closing sequence with timeout protection
            const cleanupPromise = Promise.race([
                (async () => {
                    await session.endAudioContent();
                    await session.endPrompt();
                    await session.close();
                    console.log('Session cleanup complete');
                })(),
                new Promise((_, reject) =>
                    setTimeout(() => reject(new Error('Session cleanup timeout')), 5000)
                )
            ]);

            await cleanupPromise;

            // Remove from tracking
            socketSessions.delete(socket.id);
            cleanupInProgress.delete(socket.id);

            // Notify client that session is closed and ready for new chat
            socket.emit('sessionClosed');

        } catch (error) {
            console.error('Error processing streaming end events:', error);

            // Force cleanup on error
            try {
                const bedrockClient = socketBedrockClients.get(socket.id);
                if (bedrockClient) {
                    bedrockClient.forceCloseSession(socket.id);
                }
                socketSessions.delete(socket.id);
                cleanupInProgress.delete(socket.id);
                sessionStates.set(socket.id, SessionState.CLOSED);
            } catch (forceError) {
                console.error('Error during force cleanup:', forceError);
            }

            socket.emit('error', {
                message: 'Error processing streaming end events',
                details: error instanceof Error ? error.message : String(error)
            });
        }
    });

    // Handle disconnection
    socket.on('disconnect', async () => {
        console.log('Client disconnected abruptly:', socket.id);

        // Clear the connection interval
        clearInterval(connectionInterval);

        const session = socketSessions.get(socket.id);
        const sessionId = socket.id;
        const bedrockClient = socketBedrockClients.get(socket.id);

        if (session && bedrockClient && bedrockClient.isSessionActive(sessionId) && !cleanupInProgress.get(socket.id)) {
            try {
                console.log(`Beginning cleanup for abruptly disconnected session: ${socket.id}`);
                cleanupInProgress.set(socket.id, true);

                // Add explicit timeouts to avoid hanging promises
                const cleanupPromise = Promise.race([
                    (async () => {
                        await session.endAudioContent();
                        await session.endPrompt();
                        await session.close();
                    })(),
                    new Promise((_, reject) =>
                        setTimeout(() => reject(new Error('Session cleanup timeout')), 3000)
                    )
                ]);

                await cleanupPromise;
                console.log(`Successfully cleaned up session after abrupt disconnect: ${socket.id}`);
            } catch (error) {
                console.error(`Error cleaning up session after disconnect: ${socket.id}`, error);
                try {
                    bedrockClient.forceCloseSession(sessionId);
                    console.log(`Force closed session: ${sessionId}`);
                } catch (e) {
                    console.error(`Failed even force close for session: ${sessionId}`, e);
                }
            }
        }

        // Clean up tracking maps
        socketSessions.delete(socket.id);
        sessionStates.delete(socket.id);
        cleanupInProgress.delete(socket.id);
        socketContexts.delete(socket.id);
        socketBedrockClients.delete(socket.id);

        console.log(`Cleanup complete for disconnected client: ${socket.id}`);
    });
});

// Health check endpoint
app.get('/health', (_req, res) => {
    let totalActiveSessions = 0;
    socketBedrockClients.forEach((client) => {
        totalActiveSessions += client.getActiveSessions().length;
    });
    
    const socketConnections = Object.keys(io.sockets.sockets).length;
    const bedrockClients = socketBedrockClients.size;

    res.status(200).json({
        status: 'ok',
        timestamp: new Date().toISOString(),
        activeSessions: totalActiveSessions,
        socketConnections,
        bedrockClients
    });
});

// Start the server on port 5003
const PORT = process.env.PORT || 5003;
server.listen(PORT, () => {
    console.log(`Nova Sonic Chat Server listening on port ${PORT}`);
    console.log(`Open http://localhost:${PORT} in your browser to access the application`);
});

process.on('SIGINT', async () => {
    console.log('Shutting down server...');

    const forceExitTimer = setTimeout(() => {
        console.error('Forcing server shutdown after timeout');
        process.exit(1);
    }, 5000);

    try {
        // First close Socket.IO server which manages WebSocket connections
        await new Promise(resolve => io.close(resolve));
        console.log('Socket.IO server closed');

        // Then close all active sessions for all clients
        let totalSessions = 0;
        await Promise.all(Array.from(socketBedrockClients.entries()).map(async ([socketId, client]) => {
            const activeSessions = client.getActiveSessions();
            totalSessions += activeSessions.length;
            
            await Promise.all(activeSessions.map(async (sessionId) => {
                try {
                    await client.closeSession(sessionId);
                    console.log(`Closed session ${sessionId} for socket ${socketId} during shutdown`);
                } catch (error) {
                    console.error(`Error closing session ${sessionId}:`, error);
                    client.forceCloseSession(sessionId);
                }
            }));
        }));
        
        console.log(`Closed ${totalSessions} active sessions`);

        // Now close the HTTP server with a promise
        await new Promise(resolve => server.close(resolve));
        clearTimeout(forceExitTimer);
        console.log('Server shut down');
        process.exit(0);
    } catch (error) {
        console.error('Error during server shutdown:', error);
        process.exit(1);
    }
});
