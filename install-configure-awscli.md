## Install AWS CLI

🔧 Step 1: Install AWS CLI (if it’s not already installed)
Go to:
https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html


🔧 Step 2: Confirm install
Close and reopen your terminal, then run:
- aws --version
- Expected output:
    aws-cli/2.x.x Python/3.x Windows/10 ...


🔧 Step 3: Configure your credentials
Now run:
aws configure
You’ll be prompted to enter:
    AWS Access Key ID	From your IAM user or role
    AWS Secret Access Key	From same IAM user
    Default region name	e.g. us-east-1 or us-west-2
    Default output format	json (or just press Enter)

✅ Test:
aws sts get-caller-identity
It should return your account ID and IAM identity.