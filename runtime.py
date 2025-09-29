import sys
import os
import boto3
from strands.models import BedrockModel
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient
from strands import Agent
import logging
import json
import utils

os.environ['AWS_DEFAULT_REGION'] = os.environ.get('AWS_REGION', 'us-east-1')
runtime_config_filepath = 'runtime_config.json'

# Load project configuration data
try:
    with open(runtime_config_filepath, 'r') as config_file:
        config_data = json.load(config_file)
        print("Runtime configuration loaded successfully.")
        USER_POOL_ID = config_data['USER_POOL_ID']
        CLIENT_ID = config_data['CLIENT_ID']
        CLIENT_SECRET = config_data['CLIENT_SECRET']
        RESOURCE_SERVER_ID = config_data['RESOURCE_SERVER_ID']
        GATEWAY_URL = config_data['GATEWAY_URL']
        MODEL = config_data['MODEL']
        AGENTCORE_GATEWAY_TARGET_NAME = config_data['AGENTCORE_GATEWAY_TARGET_NAME']
except FileNotFoundError:
    print("Error: setup_config.json not found.")
    exit(1)
except json.JSONDecodeError:
    print("Error: Invalid JSON format in setup_config.json.")
    exit(1)

REGION = os.environ['AWS_DEFAULT_REGION']
scopeString = f"{RESOURCE_SERVER_ID}/gateway:read {RESOURCE_SERVER_ID}/gateway:write"

print("Requesting the access token from Amazon Cognito.")
token_response = utils.get_token(USER_POOL_ID, CLIENT_ID, CLIENT_SECRET, scopeString, REGION)
token = token_response["access_token"]
print("Token response:", token)

def create_streamable_http_transport():
    return streamablehttp_client(GATEWAY_URL, headers={"Authorization": f"Bearer {token}"})

client = MCPClient(create_streamable_http_transport)

# The IAM group/user/ configured in ~/.aws/credentials should have access to Bedrock model
model = BedrockModel(
    model_id=MODEL,
    temperature=0.7,
)

# Configure the root strands logger. Change it to DEBUG if you are debugging the issue.
logging.getLogger("strands").setLevel(logging.INFO)

# Add a handler to see the logs
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s", 
    handlers=[logging.StreamHandler()]
)

with client:
    # Call the listTools 
    tools = client.list_tools_sync()
    # Create an Agent with the model and tools
    agent = Agent(model=model, tools=tools)  # you can replace with any model you like
    print(f"Tools loaded in the agent are {agent.tool_names}")
    # print(f"Tools configuration in the agent are {agent.tool_config}")
    # Invoke the agent with the sample prompt. This will only invoke  MCP 
    # listTools and retrieve the list of tools the LLM has access to.
    # The below does not actually call any tool.
    # agent("Hi , can you list all tools available to you")
    agent("list open workorders")
    # Invoke the agent with sample prompt, invoke the tool and display the response
    # Call the MCP tool explicitly. The MCP Tool name and arguments must match with your AWS Lambda function or the OpenAPI/Smithy API
    # result = client.call_tool_sync(
    #     tool_use_id="get-insight-weather-1",  # You can replace this with unique identifier. 
    #     name=AGENTCORE_GATEWAY_TARGET_NAME+"___listWorkOrders",  # This is the tool name based on AWS Lambda target types. This will change based on the target name
    #     arguments={"ver": "1.0", "feedtype": "json"}
    # )
    # Print the MCP Tool response
    # print(f"Tool Call result: {result['content'][0]['text']}")
