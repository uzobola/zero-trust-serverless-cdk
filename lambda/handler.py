
import json
import os
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])

def _resp(status: int, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }

def lambda_handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "")

    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )

    # Prefer stable identity: sub is immutable; email can change
    user_id = claims.get("sub") or claims.get("email")
    if not user_id:
        return _resp(401, {"message": "Unauthorized"})

    if method == "POST":
        try:
            body = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            return _resp(400, {"message": "Invalid JSON body"})

        note_id = body.get("noteId")
        content = body.get("content")

        if not note_id or not content:
            return _resp(400, {"message": "Missing required fields: noteId, content"})

        if len(content) > 4000:
            return _resp(400, {"message": "content too large"})

        table.put_item(Item={"userId": user_id, "noteId": note_id, "content": content})
        return _resp(200, {"message": "Note created"})

    if method == "GET":
        resp = table.query(KeyConditionExpression=Key("userId").eq(user_id))
        return _resp(200, {"items": resp.get("Items", [])})

    return _resp(405, {"message": "Method Not Allowed"})
