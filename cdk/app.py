#!/usr/bin/env python3
import os

import aws_cdk as cdk
from zero_trust_serverless.auth_stack import AuthStack
from zero_trust_serverless.data_stack import DataStack

app = cdk.App()

#Deploys Cognito User Pool
auth_stack = AuthStack(app, "AuthStack")
# Deploys DynamoDB table for storing notes
data_stack = DataStack(app, "DataStack")
from zero_trust_serverless.api_stack import ApiStack

# Deploys Lambda + API Gateway + Cognito Authorize
api_stack = ApiStack(app, "ApiStack",
    user_pool=auth_stack.user_pool,
    user_pool_client=auth_stack.user_pool_client,
    notes_table=data_stack.table
)



# This is the main entry point for the CDK application.


#	Triggers CloudFormation generation
app.synth()
