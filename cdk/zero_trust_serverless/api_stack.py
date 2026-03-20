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
    aws_iam as iam,
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
        table_key,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        ##################################################################################
        # Cognito JWT Authorizer
        # Every route in this API requires a valid JWT issued by our Cognito User Pool.
        # API Gateway validates the token at the edge — before Lambda ever runs.
        # This is the Zero Trust principle: never trust, always verify.
        ##################################################################################
        cognito_auth = authorizers.HttpJwtAuthorizer(
            "UserPoolAuthorizer",
            jwt_issuer=f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool.user_pool_id}",
            jwt_audience=[user_pool_client.user_pool_client_id],
        )

        allowed_origins = self.node.try_get_context("allowed_origins") or ["http://localhost:3000"]

        ##################################################################################
        # HTTP API with default JWT authorizer
        # default_authorizer applies Cognito JWT validation to ALL routes automatically.
        # No route can be called without a valid token — no per-route opt-in required.
        ##################################################################################
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

        ##################################################################################
        # PR4 Change 1: Dedicated GET Lambda — scoped to read-only execution role
        # Previously one Lambda handled both GET and POST under a single IAM role
        # with read+write access. Now GET has its own function and its own role.
        # Permissions are granted explicitly below — not via CDK managed grants.
        ##################################################################################
        get_notes_lambda = _lambda.Function(
            self,
            "GetNotesFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.get_notes_handler",  # Dedicated GET handler
            code=_lambda.Code.from_asset("../lambda"),
            environment={"TABLE_NAME": notes_table.table_name},
            tracing=_lambda.Tracing.ACTIVE,
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

        ##################################################################################
        # PR4 Change 2: Dedicated POST Lambda — scoped to write-only execution role
        # POST has its own function and its own role.
        # Permissions are granted explicitly below — not via CDK managed grants.
        ##################################################################################
        post_notes_lambda = _lambda.Function(
            self,
            "PostNotesFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.post_notes_handler",  # Dedicated POST handler
            code=_lambda.Code.from_asset("../lambda"),
            environment={"TABLE_NAME": notes_table.table_name},
            tracing=_lambda.Tracing.ACTIVE,
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

        ##################################################################################
        # PR4 Change 3: Action-level least privilege — explicit over convenient
        #
        # CDK's grant_read_data() grants 6 actions (Query, Scan, GetItem, BatchGetItem,
        # ConditionCheckItem, DescribeTable) even when the Lambda only needs 1 or 2.
        # grant_write_data() includes UpdateItem and DeleteItem — neither of which
        # this API needs.
        #
        # Instead we use add_to_role_policy() to grant only what each Lambda
        # actually calls:
        #   GET Lambda  → dynamodb:Query (userId lookup) + DescribeTable
        #   POST Lambda → dynamodb:PutItem (conditional write) + DescribeTable
        #
        # This is operation-level scoping, not just table-level scoping.
        # If GET Lambda is compromised, it cannot write data.
        # If POST Lambda is compromised, it cannot read other users' notes.
        # Blast radius is contained at the IAM policy level.
        ##################################################################################
        get_notes_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:Query", "dynamodb:DescribeTable"],
                resources=[notes_table.table_arn],
            )
        )

        post_notes_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:PutItem", "dynamodb:DescribeTable"],
                resources=[notes_table.table_arn],
            )
        )

        # KMS grants — required because DynamoDB table uses CUSTOMER_MANAGED CMK (PR3)
        # GET reads encrypted items -> needs decrypt
        table_key.grant_decrypt(get_notes_lambda)

        # POST writes encrypted items 
        table_key.grant_encrypt_decrypt(post_notes_lambda)
        
        ##################################################################################
        # Routes: each HTTP method wired to its dedicated Lambda
        # GET  /notes → GetNotesFunction  (Query + DescribeTable only)
        # POST /notes → PostNotesFunction (PutItem + DescribeTable only)
        ##################################################################################
        http_api.add_routes(
            path="/notes",
            methods=[apigw.HttpMethod.GET],
            integration=integrations.HttpLambdaIntegration("GetNotesIntegration", get_notes_lambda),
        )

        http_api.add_routes(
            path="/notes",
            methods=[apigw.HttpMethod.POST],
            integration=integrations.HttpLambdaIntegration("PostNotesIntegration", post_notes_lambda),
        )

        ##################################################################################
        # Access logs — structured JSON for every API request
        # Captures requestId (correlation), principalSub (identity), status, and route.
        # This is the audit trail that ties every action back to an authenticated identity.
        # dev: DESTROY for easy teardown. prod: change to RETAIN.
        ##################################################################################
        api_access_logs = logs.LogGroup(
            self,
            "HttpApiAccessLogs",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
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
            '"principalSub":"$context.authorizer.claims.sub",'
            '"principalSub_jwtPath":"$context.authorizer.jwt.claims.sub"'
            "}"
        )

        default_stage = http_api.default_stage.node.default_child
        default_stage.access_log_settings = apigw.CfnStage.AccessLogSettingsProperty(
            destination_arn=api_access_logs.log_group_arn,
            format=access_log_format,
        )

        CfnOutput(self, "HttpApiUrl", value=http_api.api_endpoint)