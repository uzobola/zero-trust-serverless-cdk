from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
    aws_lambda as _lambda,
    aws_apigatewayv2 as apigw,
    aws_apigatewayv2_integrations as integrations,
    aws_apigatewayv2_authorizers as authorizers,
)
from aws_cdk.aws_apigatewayv2 import CorsHttpMethod
from constructs import Construct


class ApiStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        user_pool,
        user_pool_client,
        notes_table,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        # Lambda function (handles GET + POST for now)
        note_lambda = _lambda.Function(
            self,
            "NotesFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("../lambda"),
            environment={"TABLE_NAME": notes_table.table_name},
        )

        # PR4:  Will split into 2 lambdas for true least privilege. WIP for now
        notes_table.grant_read_write_data(note_lambda)

        # JWT authorizer for HTTP API (Cognito User Pool)
        cognito_auth = authorizers.HttpJwtAuthorizer(
            "UserPoolAuthorizer",
            jwt_issuer=f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool.user_pool_id}",
            jwt_audience=[user_pool_client.user_pool_client_id],
        )
        allowed_origins = self.node.try_get_context("allowed_origins") or ["http://localhost:3000"]

        api = apigw.HttpApi(
            self,
            "NotesApi",
            default_authorizer=cognito_auth,
            cors_preflight=apigw.CorsPreflightOptions(
                allow_origins= allowed_origins,  # this is for dev only
                allow_methods=[CorsHttpMethod.GET, CorsHttpMethod.POST, CorsHttpMethod.OPTIONS],
                allow_headers=["authorization", "content-type"],
                max_age=Duration.hours(1),
            ),
        )

        api.add_routes(
            path="/notes",
            methods=[apigw.HttpMethod.POST],
            integration=integrations.HttpLambdaIntegration(
                "PostNotesIntegration",
                note_lambda,
            ),
        )

        api.add_routes(
            path="/notes",
            methods=[apigw.HttpMethod.GET],
            integration=integrations.HttpLambdaIntegration(
                "GetNotesIntegration",
                note_lambda,
            ),
        )

        CfnOutput(self, "HttpApiUrl", value=api.api_endpoint)
