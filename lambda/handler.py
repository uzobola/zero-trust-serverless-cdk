

import json
import os
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])

def lambda_handler(event, context):
    method = event["requestContext"]["http"]["method"]

    if method == "POST":
        body = json.loads(event["body"])
        user_id = body.get("userId")
        note_id = body.get("noteId")
        content = body.get("content")

        if not (user_id and note_id and content):
            return {"statusCode": 400, "body": "Missing required fields."}

        table.put_item(Item={
            "userId": user_id,
            "noteId": note_id,
            "content": content
        })

        return {"statusCode": 200, "body": "Note created successfully."}

    elif method == "GET":
        # Securely extract the user identity from the JWT
        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["email"]

        response = table.query(
            KeyConditionExpression=Key("userId").eq(user_id)
        )

        return {
            "statusCode": 200,
            "body": json.dumps(response["Items"])
        }

    return {"statusCode": 405, "body": "Method Not Allowed"}
