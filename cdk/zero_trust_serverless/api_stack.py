
from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
    RemovalPolicy,
    aws_lambda as _lambda,
    aws_apigatewayv2 as apigw,
    aws_apigatewayv2_integrations as integrations,
    aws_apigatewayv2_authorizers as authorizers,
    aws_logs as logs,
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

        note_lambda = _lambda.Function(
            self,
            "NotesFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("../lambda"),
            environment={"TABLE_NAME": notes_table.table_name},
            tracing=_lambda.Tracing.ACTIVE,
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

        notes_table.grant_read_write_data(note_lambda)

        cognito_auth = authorizers.HttpJwtAuthorizer(
            "UserPoolAuthorizer",
            jwt_issuer=f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool.user_pool_id}",
            jwt_audience=[user_pool_client.user_pool_client_id],
        )

        allowed_origins = self.node.try_get_context("allowed_origins") or ["http://localhost:3000"]

        http_api = apigw.HttpApi(
            self,
            "NotesApi",
            default_authorizer=cognito_auth,
            cors_preflight=apigw.CorsPreflightOptions(
                allow_origins=allowed_origins,
                allow_methods=[CorsHttpMethod.GET, CorsHttpMethod.POST, CorsHttpMethod.OPTIONS],
                allow_headers=["authorization", "content-type"],
                max_age=Duration.hours(1),
            ),
        )

        # Routes first (helps ensure default stage exists in all CDK versions)
        http_api.add_routes(
            path="/notes",
            methods=[apigw.HttpMethod.POST],
            integration=integrations.HttpLambdaIntegration("PostNotesIntegration", note_lambda),
        )

        http_api.add_routes(
            path="/notes",
            methods=[apigw.HttpMethod.GET],
            integration=integrations.HttpLambdaIntegration("GetNotesIntegration", note_lambda),
        )

        # Access logs (audit and debugging)
        api_access_logs = logs.LogGroup(
            self,
            "HttpApiAccessLogs",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,  # dev-friendly; prod would be RETAIN
        )

        access_log_format = (
            "{"
            '"requestId":"$context.requestId",'
            '"ip":"$context.identity.sourceIp",'
            '"requestTime":"$context.requestTime",'
            '"httpMethod":"$context.httpMethod",'
            '"routeKey":"$context.routeKey",'
            '"path":"$context.path",'
            '"status":"$context.status",'
            '"responseLength":"$context.responseLength",'
            '"integrationError":"$context.integrationErrorMessage",'
            '"userAgent":"$context.identity.userAgent",'
            '"principalSub":"$context.authorizer.claims.sub"'
            "}"
        )

        default_stage = http_api.default_stage.node.default_child  # CfnStage
        default_stage.access_log_settings = apigw.CfnStage.AccessLogSettingsProperty(
            destination_arn=api_access_logs.log_group_arn,
            format=access_log_format,
        )

        CfnOutput(self, "HttpApiUrl", value=http_api.api_endpoint)
