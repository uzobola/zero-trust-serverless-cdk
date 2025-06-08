#!/bin/bash

# PREREQ's:
# CDK stacks have been deployed
# You have:
# User Pool ID
# App Client ID
# Temporary password
# AWS CLI is configured (aws configure)



# Variables — replace these values
USER_POOL_ID="us-east-1_9GsAX7Sgp"
CLIENT_ID="<3ee6...your client id>"   # Replace with your actual client ID
USERNAME="your username or email that you want to create"  # Replace with the desired username or email
TEMP_PASSWORD="Temp1234!" # Replace with a temporary password
NEW_PASSWORD="SuperSecure456!"  # Replace with thea secure new password

# Step 1: Admin create user
aws cognito-idp admin-create-user \
  --user-pool-id "$USER_POOL_ID" \
  --username "$USERNAME" \
  --user-attributes Name=email,Value="$USERNAME" Name=email_verified,Value=true \
  --temporary-password "$TEMP_PASSWORD" \
  --message-action SUPPRESS

# Step 2: Initiate auth
SESSION=$(aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id "$CLIENT_ID" \
  --auth-parameters USERNAME="$USERNAME",PASSWORD="$TEMP_PASSWORD" \
  --query 'Session' \
  --output text)

# Step 3: Respond to new password challenge
aws cognito-idp respond-to-auth-challenge \
  --client-id "$CLIENT_ID" \
  --challenge-name NEW_PASSWORD_REQUIRED \
  --challenge-responses USERNAME="$USERNAME",NEW_PASSWORD="$NEW_PASSWORD",PASSWORD="$TEMP_PASSWORD" \
  --session "$SESSION"
