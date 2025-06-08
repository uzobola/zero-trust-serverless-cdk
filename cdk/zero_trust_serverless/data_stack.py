from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_dynamodb as dynamodb
)

from constructs import Construct

class DataStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Create a DynamoDB table for storing notes
        # The removal_policy is set to DESTROY to allow the table to be deleted
        self.table = dynamodb.Table(
            self, "NotesTable",
            partition_key={"name": "userId", "type": dynamodb.AttributeType.STRING},
            sort_key={"name": "noteId", "type": dynamodb.AttributeType.STRING},
            removal_policy=RemovalPolicy.DESTROY,  # <-- now fixed
            encryption=dynamodb.TableEncryption.AWS_MANAGED
        )
