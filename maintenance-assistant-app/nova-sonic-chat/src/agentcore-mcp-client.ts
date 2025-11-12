import axios, { AxiosInstance } from 'axios';
import { CognitoIdentityProviderClient, DescribeUserPoolClientCommand } from '@aws-sdk/client-cognito-identity-provider';

/**
 * AgentCore MCP Client
 * Handles communication with AgentCore Gateway using MCP protocol
 */
export class AgentCoreMCPClient {
    private axiosClient: AxiosInstance;
    private accessToken: string | null = null;
    private tokenExpiry: number = 0;
    private availableTools: any[] = [];

    constructor(
        private gatewayUrl: string,
        private clientId: string,
        private clientSecret: string,
        private tokenEndpoint: string
    ) {
        this.axiosClient = axios.create({
            baseURL: gatewayUrl,
            headers: {
                'Content-Type': 'application/json'
            }
        });
    }

    /**
     * Get M2M access token from Cognito
     */
    private async getAccessToken(): Promise<string> {
        // Check if we have a valid token
        if (this.accessToken && Date.now() < this.tokenExpiry) {
            return this.accessToken as string;
        }

        console.log('Fetching new M2M access token from Cognito...');

        try {
            const params: any = {
                grant_type: 'client_credentials',
                client_id: this.clientId,
                client_secret: this.clientSecret
            };

            // Add scope if RESOURCE_SERVER_ID is available
            // Scope format: {RESOURCE_SERVER_ID}/gateway:read {RESOURCE_SERVER_ID}/gateway:write
            const resourceServerId = process.env.RESOURCE_SERVER_ID;
            if (resourceServerId) {
                params.scope = `${resourceServerId}/gateway:read ${resourceServerId}/gateway:write`;
                console.log('Using scope:', params.scope);
            } else {
                console.warn('RESOURCE_SERVER_ID not set, token request may fail');
            }

            console.log('Requesting token from:', this.tokenEndpoint);
            console.log('Client ID:', this.clientId);

            const response = await axios.post(
                this.tokenEndpoint,
                new URLSearchParams(params).toString(),
                {
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    }
                }
            );

            this.accessToken = response.data.access_token;
            // Set expiry to 5 minutes before actual expiry for safety
            const expiresIn = response.data.expires_in || 3600;
            this.tokenExpiry = Date.now() + (expiresIn - 300) * 1000;

            console.log('M2M access token obtained successfully');
            return this.accessToken as string;
        } catch (error: any) {
            console.error('Error fetching M2M access token:', error);
            if (error.response) {
                console.error('Response status:', error.response.status);
                console.error('Response data:', error.response.data);
                console.error('Response headers:', error.response.headers);
            }
            console.error('Token endpoint:', this.tokenEndpoint);
            console.error('Client ID:', this.clientId);
            throw new Error(`Failed to obtain M2M access token: ${error.response?.data?.error || error.message}`);
        }
    }

    /**
     * Initialize the MCP client and list available tools
     */
    async initialize(): Promise<void> {
        console.log('Initializing AgentCore MCP Client...');
        
        // Get access token
        await this.getAccessToken();

        // List available tools
        await this.listTools();

        console.log(`AgentCore MCP Client initialized with ${this.availableTools.length} tools`);
    }

    /**
     * List all available tools from AgentCore Gateway
     */
    async listTools(): Promise<any[]> {
        const token = await this.getAccessToken();

        try {
            const response = await this.axiosClient.post('', {
                jsonrpc: '2.0',
                id: 'list-tools-request',
                method: 'tools/list',
                params: {}
            }, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.data.result && response.data.result.tools) {
                this.availableTools = response.data.result.tools;
                console.log('Available tools from AgentCore:', this.availableTools.map(t => t.name));
                return this.availableTools;
            }

            return [];
        } catch (error) {
            console.error('Error listing tools from AgentCore:', error);
            throw error;
        }
    }

    /**
     * Call a specific tool in AgentCore Gateway
     */
    async callTool(toolName: string, toolArguments: any): Promise<any> {
        const token = await this.getAccessToken();

        console.log(`Calling AgentCore tool: ${toolName} with arguments:`, toolArguments);

        try {
            const response = await this.axiosClient.post('', {
                jsonrpc: '2.0',
                id: `call-tool-${Date.now()}`,
                method: 'tools/call',
                params: {
                    name: toolName,
                    arguments: toolArguments
                }
            }, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.data.result) {
                console.log(`Tool ${toolName} executed successfully`);
                
                // MCP result format has content array
                // Extract the actual content from MCP response
                const result = response.data.result;
                if (result.content && Array.isArray(result.content)) {
                    // Return the text content from the first content item
                    const textContent = result.content.find((c: any) => c.type === 'text');
                    if (textContent && textContent.text) {
                        console.log(`Extracted text content from MCP response`);
                        
                        // Try to parse as JSON if it looks like JSON
                        const text = textContent.text;
                        if (text.trim().startsWith('{') || text.trim().startsWith('[')) {
                            try {
                                return JSON.parse(text);
                            } catch (e) {
                                // If parsing fails, return as-is
                                return text;
                            }
                        }
                        return text;
                    }
                }
                
                return response.data.result;
            }

            if (response.data.error) {
                console.error(`Tool ${toolName} returned error:`, response.data.error);
                throw new Error(response.data.error.message || 'Tool execution failed');
            }

            return response.data;
        } catch (error) {
            console.error(`Error calling tool ${toolName}:`, error);
            throw error;
        }
    }

    /**
     * Get available tools
     */
    getAvailableTools(): any[] {
        return this.availableTools;
    }
}

/**
 * Create and initialize AgentCore MCP Client from runtime config
 */
export async function createAgentCoreMCPClient(
    gatewayUrl: string,
    clientId: string,
    clientSecret: string,
    userPoolId: string,
    region: string = 'us-east-1'
): Promise<AgentCoreMCPClient> {
    // Construct token endpoint from user pool ID
    // Format: https://{user_pool_id_without_underscore}.auth.{region}.amazoncognito.com/oauth2/token
    const userPoolIdWithoutUnderscore = userPoolId.replace(/_/g, '');
    const tokenEndpoint = `https://${userPoolIdWithoutUnderscore}.auth.${region}.amazoncognito.com/oauth2/token`;

    console.log('Token endpoint:', tokenEndpoint);

    const client = new AgentCoreMCPClient(
        gatewayUrl,
        clientId,
        clientSecret,
        tokenEndpoint
    );

    await client.initialize();

    return client;
}
