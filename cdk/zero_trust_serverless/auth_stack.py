from aws_cdk import (
    Stack,
    aws_cognito as cognito,
)
from constructs import Construct

class AuthStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # ✅ User pool
        self.user_pool = cognito.UserPool(
            self, "ZeroTrustUserPool",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            standard_attributes={
                "email": cognito.StandardAttribute(required=True, mutable=False)
            }
        )

        # ✅ App client
        self.user_pool_client = self.user_pool.add_client(
            "AppClient",
            auth_flows=cognito.AuthFlow(user_password=True)
        )

        # ✅ Domain (moved *inside* __init__)
        cognito.CfnUserPoolDomain(
            self,
            "CognitoDomain",
            domain="zerotrust-notes-api-userpool",  # ❗ must be globally unique
            user_pool_id=self.user_pool.user_pool_id  # ❗ 
        )
