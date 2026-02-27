# PR2 Evidence: Observability (Access Logs + Retention + Correlation) 

## Control objective
Provide audit-grade visibility for API calls and Lambda execution with retention and request correlation to support incident response. 

## What changed 
- Enabled HTTP API access logs (structured JSON) → CloudWatch Logs 
- Enforced log retention (Lambda + API log group) 
- Added structured Lambda logs with `requestId` correlation 
- Enabled Lambda X-Ray tracing (Lambda-level) 

## Evidence index 
- `01-api-access-logs-401-200.png` — Access logs show 401 + 200 with `requestId`, `routeKey`, `status` 
- `02-api-access-logs-200-409.png` — Access logs show 200 + 409 with `requestId`, `routeKey`, `status` 
- `03-lambda-structured-logs.png` — Lambda structured logs include same `requestId` (correlation) + X-Ray TraceId 
- `04-accesslog-authorizer-sub.png` — Access logs capture authenticated principal `sub` via `$context.authorizer.claims.sub` (authorizerSubAlt)
- `05-correlation-requestid.png` — Same `requestId` observed in API access logs and Lambda structured logs (end-to-end correlation)

## Validation performed 
1. Generated unauthenticated traffic → 401 and confirmed access logs recorded it. 
2. Generated authenticated GET/POST traffic → 200 and confirmed access logs recorded `routeKey/status`. 
3. Triggered duplicate `noteId` → 409 and confirmed access logs recorded it. 
4. Verified Lambda emitted structured JSON logs including `requestId` matching API access logs. 
5. Verified Lambda X-Ray tracing enabled (X-Ray TraceId present in REPORT log line).
6. Verified access logs capture the authenticated principal `sub` (see `04-accesslog-authorizer-sub.png`).
7. Verified end-to-end correlation using `requestId` across API access logs and Lambda logs (see `05-correlation-requestid.png`).