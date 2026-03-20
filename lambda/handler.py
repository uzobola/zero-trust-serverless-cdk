import json
import os
import time
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])


##################################################################################
# Structured logging helper
# Every log entry is a JSON object with a timestamp, event type, and context fields.
# This makes logs queryable in CloudWatch Logs Insights — filter by userId,
# requestId, or event type to trace any request end-to-end.
##################################################################################
def _log(event_type: str, **fields):
    entry = {"ts": int(time.time()), "event": event_type, **fields}
    print(json.dumps(entry))


##################################################################################
# Response helper
# Consistent JSON response shape across all handlers.
# Content-Type header ensures API Gateway and clients parse the body correctly.
##################################################################################
def _resp(status: int, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


##################################################################################
# Identity extraction — Zero Trust core
# Extracts the verified user identity from Cognito JWT claims in the request context.
# userId is always pulled from the JWT (sub or email) — NEVER from the request body.
#
# Why this matters: trusting the client to supply userId is a BOLA vulnerability.
# A malicious user could pass in another user's ID and access their data.
# Extracting from JWT claims means the identity was verified by Cognito at the edge
# before this Lambda ever ran. You cannot forge a claim.
#
# Returns: (user_id, request_id, route_key, claims)
# If no valid identity is found, user_id is None — callers must handle this.
##################################################################################
def _identity(event):
    req_ctx = event.get("requestContext", {})
    request_id = req_ctx.get("requestId")
    route_key = req_ctx.get("routeKey")

    claims = (
        req_ctx.get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )

    user_id = claims.get("sub") or claims.get("email")
    if not user_id:
        _log("request.unauthorized", requestId=request_id, routeKey=route_key)
        return None, request_id, route_key, claims

    _log("request.authenticated", requestId=request_id, routeKey=route_key, userId=user_id)
    return user_id, request_id, route_key, claims


##################################################################################
# POST /notes handler — write-only Lambda
# PR4: This function runs under an IAM role that only allows dynamodb:PutItem
# and dynamodb:DescribeTable. It cannot read, query, or delete data.
#
# Input validation is thorough and intentional:
# - Type checks prevent unexpected data types reaching DynamoDB
# - Length limits prevent oversized payloads (storage abuse / cost risk)
# - Empty string guards prevent storing meaningless data
# - Conditional write (attribute_not_exists) prevents overwriting existing notes
#   and also acts as an idempotency guard
##################################################################################
def post_notes_handler(event, context):
    user_id, request_id, route_key, claims = _identity(event)
    if not user_id:
        return _resp(401, {"message": "Unauthorized"})

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        _log("request.bad_json", requestId=request_id, userId=user_id, routeKey=route_key)
        return _resp(400, {"message": "Invalid JSON body"})

    note_id = body.get("noteId")
    content = body.get("content")

    # Presence check — both fields required
    if note_id is None or content is None:
        _log("request.missing_fields", requestId=request_id, userId=user_id, routeKey=route_key)
        return _resp(400, {"message": "Missing required fields: noteId, content"})

    # Type checks — reject non-string values before they reach DynamoDB
    if not isinstance(note_id, str):
        _log("request.invalid_noteId_type", requestId=request_id, userId=user_id)
        return _resp(400, {"message": "noteId must be a string"})
    if not isinstance(content, str):
        _log("request.invalid_content_type", requestId=request_id, userId=user_id)
        return _resp(400, {"message": "content must be a string"})

    # Sanitize and validate noteId
    note_id = note_id.strip()
    if not note_id:
        _log("request.empty_noteId", requestId=request_id, userId=user_id)
        return _resp(400, {"message": "noteId cannot be empty"})
    if len(note_id) > 128:
        _log("request.noteId_too_long", requestId=request_id, userId=user_id, noteId=note_id, routeKey=route_key)
        return _resp(400, {"message": "noteId too long"})

    # Validate content
    if not content.strip():
        _log("request.empty_content", requestId=request_id, userId=user_id, noteId=note_id)
        return _resp(400, {"message": "content cannot be empty"})
    if len(content) > 4000:
        _log("request.content_too_large", requestId=request_id, userId=user_id, noteId=note_id)
        return _resp(400, {"message": "content too large"})

    try:
        # Conditional write: only succeeds if this (userId, noteId) pair doesn't exist.
        # Prevents overwriting existing notes and acts as a natural idempotency guard.
        table.put_item(
            Item={"userId": user_id, "noteId": note_id, "content": content},
            ConditionExpression="attribute_not_exists(userId) AND attribute_not_exists(noteId)",
        )
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code == "ConditionalCheckFailedException":
            # Note already exists — return 409 conflict, not 500
            _log("notes.conflict", requestId=request_id, userId=user_id, noteId=note_id)
            return _resp(409, {"message": "noteId already exists"})
        _log("notes.ddb_error", requestId=request_id, userId=user_id, noteId=note_id, errorCode=code)
        return _resp(500, {"message": "Internal server error"})

    _log("notes.created", requestId=request_id, userId=user_id, noteId=note_id, routeKey=route_key)
    return _resp(200, {"message": "Note created"})


##################################################################################
# GET /notes handler — read-only Lambda
# PR4: This function runs under an IAM role that only allows dynamodb:Query
# and dynamodb:DescribeTable. It cannot write, update, or delete data.
#
# Identity is always scoped to the authenticated user — a user can only
# query their own notes. The userId from JWT claims is the partition key filter;
# there is no way to query another user's data.
#
# The email fallback handles the case where notes were written using email
# as userId (legacy compatibility) vs the Cognito sub field.
##################################################################################
def get_notes_handler(event, context):
    user_id, request_id, route_key, claims = _identity(event)
    if not user_id:
        return _resp(401, {"message": "Unauthorized"})

    # Query scoped strictly to the authenticated user's partition key
    resp = table.query(KeyConditionExpression=Key("userId").eq(user_id))
    items = resp.get("Items", [])

    # Email fallback: if no items found via sub, try querying by email.
    # Handles legacy notes written before sub-based identity binding was enforced.
    if not items:
        email = claims.get("email")
        if email and email != user_id:
            resp2 = table.query(KeyConditionExpression=Key("userId").eq(email))
            items = resp2.get("Items", [])

    _log("notes.listed", requestId=request_id, userId=user_id, itemCount=len(items), routeKey=route_key)
    return _resp(200, {"items": items})