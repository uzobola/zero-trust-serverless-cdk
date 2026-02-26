# Updated Version

import json
import os
import time
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])


def _log(event_type: str, **fields):
    entry = {"ts": int(time.time()), "event": event_type, **fields}
    print(json.dumps(entry))


def _resp(status: int, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def lambda_handler(event, context):
    req_ctx = event.get("requestContext", {})
    request_id = req_ctx.get("requestId")
    route_key = req_ctx.get("routeKey")
    method = req_ctx.get("http", {}).get("method", "")

    claims = (
        req_ctx.get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )


    user_id = claims.get("sub") or claims.get("email")
    if not user_id:
        _log("request.unauthorized", requestId=request_id, routeKey=route_key)
        return _resp(401, {"message": "Unauthorized"})

    _log("request.authenticated", requestId=request_id, routeKey=route_key, userId=user_id)

    if method == "POST":
        try:
            body = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            _log("request.bad_json", requestId=request_id, userId=user_id)
            return _resp(400, {"message": "Invalid JSON body"})

        note_id = body.get("noteId")
        content = body.get("content")


        if note_id is None or content is None:
            _log("request.missing_fields", requestId=request_id, userId=user_id)
            return _resp(400, {"message": "Missing required fields: noteId, content"})


        if not isinstance(note_id, str):
            _log("request.invalid_noteId_type", requestId=request_id, userId=user_id)
            return _resp(400, {"message": "noteId must be a string"})
        if not isinstance(content, str):
            _log("request.invalid_content_type", requestId=request_id, userId=user_id)
            return _resp(400, {"message": "content must be a string"})


        note_id = note_id.strip()
        if not note_id:
            _log("request.empty_noteId", requestId=request_id, userId=user_id)
            return _resp(400, {"message": "noteId cannot be empty"})
        if len(note_id) > 128:
            _log("request.noteId_too_long", requestId=request_id, userId=user_id)
            return _resp(400, {"message": "noteId too long"})

        if not content.strip():
            _log("request.empty_content", requestId=request_id, userId=user_id, noteId=note_id)
            return _resp(400, {"message": "content cannot be empty"})
        if len(content) > 4000:
            _log("request.content_too_large", requestId=request_id, userId=user_id, noteId=note_id)
            return _resp(400, {"message": "content too large"})

        try:
            table.put_item(
                Item={"userId": user_id, "noteId": note_id, "content": content},
                ConditionExpression="attribute_not_exists(userId) AND attribute_not_exists(noteId)",
            )
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code == "ConditionalCheckFailedException":
                _log("notes.conflict", requestId=request_id, userId=user_id, noteId=note_id)
                return _resp(409, {"message": "noteId already exists"})
            _log("notes.ddb_error", requestId=request_id, userId=user_id, noteId=note_id, errorCode=code)
            return _resp(500, {"message": "Internal server error"})

        _log("notes.created", requestId=request_id, userId=user_id, noteId=note_id)
        return _resp(200, {"message": "Note created"})


    if method == "GET":
        resp = table.query(KeyConditionExpression=Key("userId").eq(user_id))
        items = resp.get("Items", [])

        if not items:
            email = claims.get("email")
            if email and email != user_id:
                resp2 = table.query(KeyConditionExpression=Key("userId").eq(email))
                items = resp2.get("Items", [])

        _log("notes.listed", requestId=request_id, userId=user_id, itemCount=len(items))
        return _resp(200, {"items": items})

    _log("request.method_not_allowed", requestId=request_id, userId=user_id, routeKey=route_key)
    return _resp(405, {"message": "Method Not Allowed"})


# OLD Version ( for reference)
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
