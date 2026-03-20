# PR4 Evidence: Least Privilege per Route (Split Lambdas + Scoped IAM + CMK Grants)

## Control objective
Enforce true least privilege at the IAM layer by:
- Splitting GET and POST into separate Lambda functions (separate execution roles)
- Granting each function only the DynamoDB actions it needs
- Ensuring KMS permissions are scoped appropriately because DynamoDB is encrypted with a customer-managed CMK (PR3)

This reduces blast radius if a function or role is compromised:
- GET cannot write or mutate data
- POST cannot query/read other users' notes
- Both functions can access DynamoDB only through the required KMS key grants

---

## What changed

### 1. Split the API into two Lambdas (per route)
- `GET /notes` → `GetNotesFunction` (`handler.get_notes_handler`)
- `POST /notes` → `PostNotesFunction` (`handler.post_notes_handler`)

### 2. IAM policies are action-scoped (not `grant_read_write_data`)
Instead of broad CDK grants, each Lambda role gets explicit, minimal actions:

**GetNotesFunction**
- `dynamodb:Query`
- `dynamodb:DescribeTable`

**PostNotesFunction**
- `dynamodb:PutItem`
- `dynamodb:DescribeTable`

### 3. KMS permissions added for CMK-encrypted DynamoDB (PR3 dependency)
Because the table uses `CUSTOMER_MANAGED` encryption, the Lambda roles also need KMS permissions:
- GET needs `kms:Decrypt` to read encrypted items
- POST needs `kms:Encrypt` + `kms:GenerateDataKey` (+ `kms:Decrypt`) to write encrypted items

---

## Why this matters (risk reduction)
- Limits impact of credential compromise (blast radius)
- Prevents accidental privilege creep over time (no "read/write everywhere" defaults)
- Creates clear separation of duties: read path vs write path
- Ensures encryption controls are actually usable in production (correct CMK grants)

---

## Evidence index

- `01-cdk-diff-apistack-split-lambda.png` — IaC diff: old combined Lambda/resources removed; new GET/POST Lambdas + integrations created
- `02-cdk-diff-iam-least-privilege-per-route.png` — IAM diff: GET role shows `Query/DescribeTable`; POST role shows `PutItem/DescribeTable`
- `iam-policy-diff.png` — IAM policy table: confirms old `NotesFunction` role removed, new `GetNotesFunction` and `PostNotesFunction` roles added with separate execution roles
- `03-code-split-iam_.png` — Code proof (api_stack.py): explicit IAM statements + CMK grants
- `04-code-split-lambdas.png` — Code proof (api_stack.py): two Lambdas, two integrations
- `05-unauth-401.png` — Runtime proof: unauthenticated request denied (authorizer still enforced)
- `06-cdk-diff-kms-grants-per-route.png` — IAM diff: GET role has `kms:Decrypt`; POST role has `kms:Encrypt` + `kms:GenerateDataKey`
- `07-cdk-deploy-success.png` — Successful deployment: all resources UPDATE_COMPLETE, KMS grants applied
- `08-post-note-200.png` — Runtime proof: authenticated POST returns 200, note created
- `09-get-notes-200.png` — Runtime proof: authenticated GET returns 200, notes listed including pr4-1

---

## Validation performed
1. Confirmed IaC defines two Lambdas and routes are wired correctly (see `01-*` and `04-*`).
2. Confirmed IAM policies are least-privilege per route (see `02-*` and `iam-policy-diff.*`).
3. Confirmed KMS permissions are present to support CMK-encrypted DynamoDB (see `06-*`).
4. Invoked API:
   - Unauthenticated request returns 401 (see `05-*`)
   - Authenticated POST returns 200 and creates a note (see `08-*`)
   - Authenticated GET returns 200 and lists notes including `pr4-1` (see `09-*`)
5. Confirmed no KMS `AccessDeniedException` errors after adding key grants.

---

## Production considerations
- This PR intentionally prefers explicit action-level IAM over CDK convenience grants to prevent over-permissioning.
- Because the DynamoDB table is encrypted with a CMK (PR3), each Lambda role must be granted the minimum KMS permissions required for its operation.
- In enterprise environments, key policy and grants should be tightly controlled — separation of duties between key admins and app roles.

---

## Post-review update: KMS grants constrained to DynamoDB service only

After PR review, KMS grants were tightened with IAM condition keys to prevent 
Lambda from calling KMS directly outside of DynamoDB:

- `kms:ViaService` — KMS calls must originate from DynamoDB, not Lambda directly
- `kms:CallerAccount` — Locks key usage to this AWS account only
- `kms:EncryptionContext:aws:dynamodb:tableName` — Scopes to this specific table only

This ensures the KMS grants are only usable through the DynamoDB service path — 
consistent with the least-privilege principle applied throughout this PR.