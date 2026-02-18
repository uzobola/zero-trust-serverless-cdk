# PR1 Evidence: AuthN/AuthZ Identity Binding + Correct IAM

## Control objective
Ensure only authenticated principals can invoke the API (**AuthN**), and ensure data access is scoped to the authenticated principal’s identity (**AuthZ**) to prevent BOLA/IDOR.


## Summary
This PR hardens the Notes API by enforcing **server-side identity binding** using validated JWT claims and correcting permissions to match runtime behavior. The key security fix prevents **horizontal privilege escalation** by ensuring clients cannot choose or spoof the `userId` used for DynamoDB reads/writes.

## What was vulnerable (before)
**POST** trusted a client-controlled identifier:
- The API accepted `userId` from the request body and wrote it directly to DynamoDB.
- This enabled **BOLA/IDOR**: any authenticated user could write notes under another user’s identity by sending a different `userId`.

Example of the vulnerable behavior:
- `user_id = body.get("userId")`
- `table.put_item(Item={"userId": user_id, ...})`

**GET** scoped reads to a JWT claim (`email`), which is better than trusting the body but not ideal because email can change.

## What changed (after)
### 1) Server-side identity binding (AuthZ)
- The Lambda now derives identity exclusively from validated JWT claims injected by API Gateway’s JWT authorizer:
  - Prefer `sub` (immutable unique subject) and fall back to `email` if needed.
- All data operations are scoped to that derived identity:
  - **POST** writes `userId` from JWT identity (not user input)
  - **GET** queries only items where `userId == <JWT identity>`

Security intent:
- AuthN comes from Cognito JWT validation at the edge
- AuthZ is enforced in the application by binding access to the token principal

### 2) Correct permissions (IAM)
- DynamoDB permissions were updated to match actual handler behavior:
  - GET uses `Query`
  - POST uses `PutItem`
- Temporary broader access via `grant_read_write_data()` is acceptable for PR1 functional correctness; PR4 splits functions to enforce strict least privilege per route.

## Why this matters (risk reduction)
- Prevents **horizontal privilege escalation** / **IDOR** where users can access or create resources belonging to other users.
- Establishes a baseline “zero trust” pattern: **never trust client-supplied identity attributes**.
- Improves auditability of ownership: `userId` in DynamoDB reflects the authenticated principal.

## Standards / Mappings
- **OWASP API Security Top 10:** API1:2019 / API1:2023 — **Broken Object Level Authorization (BOLA)**
- General principle: **AuthN ≠ AuthZ** (being authenticated does not mean the request is authorized)


## Evidence index (this folder)
- `02-unauthenticated-request.jpg` — Unauthenticated call denied (401/403)
- `03-cognito-signup-usersub.jpg` — Cognito sign-up output showing user `sub` (immutable identity)
- `04-token-issued.jpg` — JWT access token obtained
- `05-post-note.jpg` — Authorized POST succeeds
- `06-get-notes.jpg` — Authorized GET returns notes scoped to `sub` 
- `07-spoof-attempt.jpg` — POST with spoofed `userId` attempt
- `08-get-after-spoof.jpg` — GET proves stored `userId` still equals authenticated `sub`
- `09-code-identity-binding.jpg` — Handler binds identity to JWT claims (`sub`)
- `10-code-authorizer-and-routes.png` — CDK defines JWT authorizer + `/notes` routes + IAM grant
- `11-conditional-write-409.png` — Duplicate noteId returns 409 (prevents overwrite/clobber)

## Validation performed (evidence)
1. Confirmed API exists and routes/integrations are deployed (see `10-code-authorizer-and-routes.png` and `06-get-notes.jpg` for successful invocation). 
2. Confirmed unauthenticated requests are denied (401/403) (see `02-unauthenticated-request.jpg`).
3. Created/confirmed Cognito user and obtained JWT (see `03-cognito-signup-usersub.jpg`, `04-token-issued.jpg`).
4. Verified authorized POST creates a note (see `05-post-note.jpg`).
5. Verified authorized GET returns notes scoped to JWT identity (`sub`) (see `06-get-notes.jpg`).
6. Attempted spoofing (BOLA/IDOR):
   - Sent POST with `userId="someone-else"` in body (see `07-spoof-attempt.jpg`)
   - Confirmed stored/query `userId` remains authenticated principal (`sub`) (see `08-get-after-spoof.jpg`)
7. Verified application enforces identity binding in handler code (see `09-code-identity-binding.jpg`).
8. Verified IaC enforces JWT authorizer + explicit `/notes` routes + required IAM grants (see `10-code-authorizer-and-routes.png`).
9.  Verified duplicate noteId is rejected with 409 using DynamoDB conditional write (see `11-conditional-write-409.png`).

## Next improvements (planned)
- **PR2:** API access logging (structured), log retention, X-Ray tracing
- **PR3:** DynamoDB PITR + CMK (KMS) + stage-safe removal policies
- **PR4:** Split GET/POST into separate functions and apply true least privilege IAM per route
- **PR5:** Architecture doc + threat model + controls matrix + evidence packaging
