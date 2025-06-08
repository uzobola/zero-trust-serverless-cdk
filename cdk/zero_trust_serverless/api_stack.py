# from aws_cdk import (
#     Stack,
#     CfnOutput,
#     aws_lambda as _lambda,
#     aws_apigatewayv2 as apigw,
#     aws_apigatewayv2_integrations as integrations,
#     aws_apigatewayv2_authorizers as authorizers,
#     aws_iam as iam
# )
# from constructs import Construct

# class ApiStack(Stack):
#     def __init__(self, scope: Construct, id: str, *, user_pool, user_pool_client, notes_table, **kwargs):
#         super().__init__(scope, id, **kwargs)  # Add this line!

#         # Lambda function
#         note_lambda = _lambda.Function(
#             self, "CreateNoteFunction",
#             runtime=_lambda.Runtime.PYTHON_3_12,
#             handler="handler.lambda_handler",
#             code=_lambda.Code.from_asset("../lambda"),
#             environment={
#                 "TABLE_NAME": notes_table.table_name
#             }
#         )

#         # Least-privilege: allow only PutItem
#         notes_table.grant_write_data(note_lambda)

#         # Cognito authorizer
#         # Note: user_pool_client is now passed as a parameter to the ApiStack
#         # This is necessary to ensure the authorizer can validate tokens
#         cognito_auth = authorizers.HttpUserPoolAuthorizer(
#             "UserPoolAuthorizer",
#             user_pool,  # positional parameter
            
# )

#         # HTTP API Gateway
#         api = apigw.HttpApi(
#             self, "NotesApi",
#             default_authorizer=cognito_auth,
#             default_integration=integrations.HttpLambdaIntegration(
#                 "LambdaIntegration", note_lambda
        #     )
        # )

        # # self.api_url = api.api_endpoint
        
        # CfnOutput(self, "HttpApiUrl", value=api.api_endpoint)


from aws_cdk import (
    Stack,
    CfnOutput,
    aws_lambda as _lambda,
    aws_apigatewayv2 as apigw,
    aws_apigatewayv2_integrations as integrations,
    aws_apigatewayv2_authorizers as authorizers,
    aws_iam as iam
)
from constructs import Construct

class ApiStack(Stack):
    def __init__(self, scope: Construct, id: str, *, user_pool, user_pool_client, notes_table, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Lambda function
        note_lambda = _lambda.Function(
            self, "CreateNoteFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("../lambda"),
            environment={
                "TABLE_NAME": notes_table.table_name
            }
        )

        # Least-privilege: allow only PutItem
        notes_table.grant_write_data(note_lambda)

        # Use HttpJwtAuthorizer instead of HttpUserPoolAuthorizer
        cognito_auth = authorizers.HttpJwtAuthorizer(
            "UserPoolAuthorizer",
            jwt_issuer=f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool.user_pool_id}",
            jwt_audience=[user_pool_client.user_pool_client_id]
        )

        # HTTP API Gateway
        api = apigw.HttpApi(
            self, "NotesApi",
            default_authorizer=cognito_auth,
            default_integration=integrations.HttpLambdaIntegration(
                "LambdaIntegration", note_lambda
            )
        )
        
        CfnOutput(self, "HttpApiUrl", value=api.api_endpoint)