import json
import boto3

def lambda_handler(event, context):
    """
    Cognito Post Confirmation Trigger
    Automatically adds new users to the Administrators group
    """
    
    # Get user pool ID and username from the event
    user_pool_id = event['userPoolId']
    username = event['userName']
    
    # Create Cognito client
    cognito = boto3.client('cognito-idp')
    
    try:
        # Add user to Administrators group
        cognito.admin_add_user_to_group(
            UserPoolId=user_pool_id,
            Username=username,
            GroupName='Administrators'
        )
        
        print(f"Successfully added user {username} to Administrators group")
        
    except Exception as e:
        print(f"Error adding user {username} to group: {str(e)}")
        # Don't fail the confirmation process if group assignment fails
    
    # Return the event unchanged (required for Cognito triggers)
    return event