# PR3 Evidence: Data Protection (CMK Encryption + PITR + Stage Safety)

## Control objective
Protect the DynamoDB data layer with:
- **Customer-managed KMS encryption** (governance + revocation capability)
- **Point-in-time recovery (PITR)** for rollback after accidental/hostile writes
- **Stage-aware deletion safety** to prevent accidental data loss in prod

## What changed
These controls reduce blast radius (CMK governance), enable rollback (PITR), and prevent accidental data loss (prod guardrails).
- DynamoDB table encryption upgraded to **CUSTOMER_MANAGED** using a CMK (`alias/zero-trust-notes-table`)
- Enabled **PITR** (restore to any second within the last 35 days)
- Added **stage-aware guardrails**:
  - Dev: `DESTROY` for iteration
  - Prod: `RETAIN` + `DeletionProtectionEnabled=true`

## Evidence index
- `00-cdk-diff-datastack-kms-pitr.png` — IaC diff: CMK + PITR + removal policy change
- `01-cdk-diff-prod-safety.png` — IaC diff (prod): Retain + deletion protection posture
- `02-cdk-deploy-datastack-success.png` - Successful Deployment (CDK Output)
- `03-dynamodb-encryption-cmk.png` — Console: encryption uses customer-managed key
- `04-dynamodb-pitr-enabled.png` — Console: PITR enabled
- `05-kms-key-rotation-alias.png` — Console: CMK alias + rotation enabled
- `06-code-data-stack.png` — CDK code proof

## Validation performed
1. Confirmed IaC change set for CMK + PITR + removal policy via cdk diff DataStack (see `00-*`).
2. Confirmed prod safety posture via `cdk diff DataStack -c environment=prod` (see `01-*`).
3. Deployed DataStack successfully (see `02-*`).
4. Verified DynamoDB encryption uses a customer-managed CMK (see `03-*`).
5. Verified PITR enabled on the table (see `04-*`).
6. Verified CMK alias + rotation enabled (see `05-*`).
7. Verified controls enforced in CDK code (see `06-*`).


## Production Considerations
Changing DynamoDB SSE from AWS-managed to CMK can require table replacement; in production you’d plan a migration (backup/restore, dual-write, or cutover) to avoid data loss/downtime.
- Note: This project deploys in dev by default; `DeletionProtectionEnabled` and `RETAIN` are validated via -c environment=prod diff only.

## Key policy note (project scenario vs enterprise )
This project uses the default CDK key policy (account root as admin). In enterprise, restrict key admins to a security/admin role and grant key usage only to DynamoDB and the app role (separation of duties).