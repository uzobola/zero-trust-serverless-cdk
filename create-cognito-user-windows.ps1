# PREREQ's:
# CDK stacks have been deployed
# You have:
# User Pool ID
# App Client ID
# Temporary password
# AWS CLI is configured (aws configure)


# Variables — replace with your actual values
$userPoolId = "us-east-1_XXXXXXXX" # Replace with your actual User Pool ID
$clientId = "<3ee6...your client id>"   # Replace with your actual client ID
$username = "your username or email that you want to create"  # Replace with the desired username or email
$tempPassword = "Temp1234!" # Replace with a temporary password
$newPassword = "SuperSecure456!"  # Replace with thea secure new password

# Step 1: Create user
aws cognito-idp admin-create-user `
  --user-pool-id $userPoolId `
  --username $username `
  --user-attributes Name=email,Value=$username Name=email_verified,Value=true `
  --temporary-password $tempPassword `
  --message-action SUPPRESS

# Step 2: Initiate Auth
$session = aws cognito-idp initiate-auth `
  --auth-flow USER_PASSWORD_AUTH `
  --client-id $clientId `
  --auth-parameters USERNAME=$username,PASSWORD=$tempPassword `
  --query 'Session' `
  --output text

# Step 3: Respond to new password challenge
aws cognito-idp respond-to-auth-challenge `
  --client-id $clientId `
  --challenge-name NEW_PASSWORD_REQUIRED `
  --challenge-responses USERNAME=$username,NEW_PASSWORD=$newPassword,PASSWORD=$tempPassword `
  --session $session
