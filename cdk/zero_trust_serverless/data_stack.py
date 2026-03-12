from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_dynamodb as dynamodb,
    aws_kms as kms,
)
from constructs import Construct


class DataStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        ##################################################################################
        # PR3: Stage-aware safety defaults
        # Reads "environment" from cdk.json context or CLI: cdk deploy -c environment=prod
        # Dev keeps DESTROY for easy sandbox cleanup.
        # Prod flips to RETAIN — CloudFormation will never auto-delete the table or key.
        ##################################################################################
        env_name = self.node.try_get_context("environment") or "dev"
        is_prod = env_name.lower() == "prod"
        table_removal = RemovalPolicy.RETAIN if is_prod else RemovalPolicy.DESTROY
        key_removal = RemovalPolicy.RETAIN if is_prod else RemovalPolicy.DESTROY


        ##################################################################################
        # PR3 Change 1: Customer Managed Key (CMK) for DynamoDB encryption at rest
        # Upgrade from AWS_MANAGED → CUSTOMER_MANAGED gives us:
        # - Full audit trail: every encrypt/decrypt operation appears in CloudTrail
        # - Revocation capability: disabling this key immediately blocks all data access
        # - Key rotation control: annual rotation of key material enabled below
        # - Human-readable alias: visible in AWS console without hunting for key IDs

        ##################################################################################
        # Note: (lab vs enterprise): CDK default key policy grants admin to account root.
        # In enterprise, restrict key admins to a security/admin role and grant key usage 
        # only to DynamoDB + the application role (separation of duties).
        ##################################################################################
        self.table_key = kms.Key(
            self,
            "NotesTableKey",
            description="CMK for Zero Trust Notes DynamoDB table — encryption at rest",
            enable_key_rotation=True,            # Rotates key material annually
            alias="alias/zero-trust-notes-table", # Named alias for console visibility
            removal_policy=key_removal,           # RETAIN in prod, DESTROY in dev
        )


        ##################################################################################
        # PR3 Change 2–4: DynamoDB table with CMK encryption, PITR, billing mode,
        # and stage-aware deletion protection
        ##################################################################################
        self.table = dynamodb.Table(
            self,
            "NotesTable",
            partition_key=dynamodb.Attribute(
                name="userId",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="noteId",
                type=dynamodb.AttributeType.STRING,
            ),

            ##################################################################################
            # PR3 Change 2: On-demand billing — no capacity planning required.
            # PAY_PER_REQUEST means we pay per read/write, not for provisioned capacity.
            # Zero traffic = zero cost. Correct default for a portfolio/dev workload.
            ###################################################################################
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,


            ##################################################################################
            # PR3 Change 3: Enable Point-in-Time Recovery (PITR)
            # Allows restoring the table to any second within the last 35 days.
            # Critical for a Zero Trust architecture — if a compromised identity
            # corrupts or deletes data, we can recover to the exact moment before it.
            ##################################################################################
            point_in_time_recovery=True,


            ##################################################################################
            # PR3 Change 4: Upgrade encryption from AWS_MANAGED to CUSTOMER_MANAGED
            # AWS_MANAGED = reduced control over key policy/rotation.
            # CUSTOMER_MANAGED = we control it. Provides explicit governance 
            # (policy, rotation, disable/revoke) controls.
            # Note: In enterprise: restrict key admin to security/admin role; restrict key 
            # usage to DynamoDB service + app role via grants.
            ##################################################################################
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=self.table_key,


            ##################################################################################
            # PR3 Change 5: Stage-aware removal policy
            # Dev: DESTROY — easy CloudFormation teardown during iteration.
            # Prod: RETAIN — table survives even if the stack is accidentally deleted.
            ##################################################################################
            removal_policy=table_removal,

            ##################################################################################
            # PR3 Change 6: CloudFormation-level deletion protection in prod.
            # A second guardrail on top of RemovalPolicy — requires explicit override
            # to delete the table via CloudFormation in production environments.
            ##################################################################################
            deletion_protection=is_prod,

            ##################################################################################
            # Note: Changing DynamoDB encryption from AWS-managed to customer-managed 
            # may force the table to be replaced depending on existing resource state.
            # In real-time scenario, we would plan this change carefully, to avoid 
            # unintended downtime or data loss. E.g backup/restore, dual-write, migration cutover.
            ##################################################################################
        )