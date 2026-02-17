# Updated Version

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



# OLD CODE


# import json
# import os
# import boto3
# from boto3.dynamodb.conditions import Key

# dynamodb = boto3.resource("dynamodb")
# table = dynamodb.Table(os.environ["TABLE_NAME"])

# def lambda_handler(event, context):
#    method = event["requestContext"]["http"]["method"]

#    if method == "POST":
#        body = json.loads(event["body"])
#        user_id = body.get("userId")
#        note_id = body.get("noteId")
#        content = body.get("content")

#        if not (user_id and note_id and content):
#            return {"statusCode": 400, "body": "Missing required fields."}

#        table.put_item(Item={
#            "userId": user_id,
#            "noteId": note_id,
#            "content": content
#        })

#        return {"statusCode": 200, "body": "Note created successfully."}

#    elif method == "GET":
#        # Securely extract the user identity from the JWT
#        user_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["email"]

#        response = table.query(
#            KeyConditionExpression=Key("userId").eq(user_id)
#        )

#        return {
#            "statusCode": 200,
#            "body": json.dumps(response["Items"])
#        }

#    return {"statusCode": 405, "body": "Method Not Allowed"}
