import json
import boto3
import logging
import os
from botocore.exceptions import ClientError

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Lambda function to query Knowledge Base for maintenance documentation
    """
    
    logger.info(f"Received event: {json.dumps(event)}")
    
    # Get Knowledge Base ID from environment variable
    KB_ID = os.environ.get('KNOWLEDGE_BASE_ID')
    
    # Initialize Bedrock Agent Runtime client
    bedrock_client = boto3.client('bedrock-agent-runtime', region_name='us-east-1')
    
    try:
        # Extract query from event - handle both direct and MCP tool call formats
        query = event.get('query', '')
        
        # If no direct query, check for MCP tool call format
        if not query and 'arguments' in event:
            query = event['arguments'].get('query', '')
        
        # Also check for nested parameters structure
        if not query and 'parameters' in event:
            query = event['parameters'].get('query', '')
            
        if not query:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Query parameter is required',
                    'received_event': event  # Debug info
                })
            }
        
        logger.info(f"Querying Knowledge Base with: {query}")
        
        # Query the Knowledge Base
        response = bedrock_client.retrieve(
            knowledgeBaseId=KB_ID,
            retrievalQuery={'text': query},
            retrievalConfiguration={
                'vectorSearchConfiguration': {
                    'numberOfResults': 5
                }
            }
        )
        
        logger.info(f"Knowledge Base response: {len(response.get('retrievalResults', []))} results")
        
        # Format results
        results = []
        for result in response.get('retrievalResults', []):
            content = result.get('content', {}).get('text', '')
            score = result.get('score', 0)
            location = result.get('location', {})
            source = location.get('s3Location', {}).get('uri', 'Unknown source')
            
            results.append({
                'content': content,
                'score': score,
                'source': source
            })
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'query': query,
                'results': results,
                'total_results': len(results)
            })
        }
        
    except ClientError as e:
        logger.error(f"AWS Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'AWS Error: {str(e)}'})
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Unexpected error: {str(e)}'})
        }