# SterlingStan — Maintainer Handoff Instructions

**For:** Incoming maintainer
**Prepared by:** [Outgoing maintainer name]
**Date of handoff:** [Date]

---

## Overview

This document is a step-by-step guide to taking over ownership of SterlingStan, the Sterling guild's AQW Discord bot. It covers getting access to everything you need, verifying the bot is healthy, making routine changes, and shutting the bot down if necessary.

The full technical design document is available in the GitHub repository. Read it if you want to understand how the system is built. This document assumes you haven't read it yet and tells you only what you need to know to take ownership and keep things running.

---

## What You're Taking Over

SterlingStan consists of three things:

- **A GitHub repository** — contains all the Python code and Terraform infrastructure scripts.
- **A Discord bot application** — registered on the Discord Developer Portal and invited to the Sterling server.
- **A dedicated AWS account** — hosts all the cloud infrastructure the bot runs on.

These three things are independent. You can change the code without touching Discord. You can rotate credentials without redeploying code. Keep that separation in mind as you work.

---

## Part 1 — Access Handoff

You need access to all three of the above before you can do anything else. Complete these in order.

### 1.1 GitHub Repository

The outgoing maintainer should add you as a collaborator on the repository, or transfer ownership to your GitHub account if you will be the sole maintainer going forward.

Once you have access:

```bash
git clone https://github.com/<org-or-user>/aqw-guild-bot.git
cd aqw-guild-bot
```

The repository contains a full technical design document (`AQW_Guild_Bot_Design_Document_Terraform.md`) at the root. Read it if you need to understand the system in depth.

### 1.2 AWS Account

The bot runs in a **dedicated AWS account** separate from any personal AWS accounts. The outgoing maintainer should either:

- Create an IAM user for you in the account and provide you with an Access Key ID and Secret Access Key, or
- Transfer root account ownership by updating the account's email address and password to ones you control.

For day-to-day work an IAM user with administrator permissions is sufficient. Root access is only needed for account-level operations like billing or account closure.

Once you have credentials, configure the AWS CLI:

```bash
aws configure --profile sterlingstan
# AWS Access Key ID: <your access key>
# AWS Secret Access Key: <your secret key>
# Default region: us-east-1
# Default output format: json
```

Using a named profile (`--profile sterlingstan`) keeps these credentials separate from any personal AWS credentials you may have. All commands in this document use this profile.

Verify access is working:

```bash
aws sts get-caller-identity --profile sterlingstan
```

You should see a JSON response showing the account ID and your IAM user. If this fails, your credentials are not set up correctly — do not proceed until this works.

### 1.3 Discord Bot Application

The bot is registered as an application in the **Discord Developer Portal** under the outgoing maintainer's Discord account. The outgoing maintainer should add your Discord account as a Team member on the application so you have access to its credentials without needing to use their personal account.

1. Go to https://discord.com/developers/applications.
2. Select the SterlingStan application.
3. Under **Team**, add your Discord account as a member with the Developer role.

Once added, you can view and regenerate the bot token, copy the Application ID and Public Key, and manage OAuth settings. Do not regenerate the bot token yet — doing so will break the live bot until you rotate the secret (covered in Part 3).

---

## Part 2 — Verifying the Handoff

Before the outgoing maintainer fully steps away, confirm that everything is working from your end.

### 2.1 Verify Terraform State Access

```bash
cd aqw-guild-bot/infrastructure
terraform init
```

Terraform will connect to the S3 remote state bucket and download the existing state. You should see output ending in `Terraform has been successfully initialized!`

If init fails with a credentials error, your AWS CLI profile is not configured correctly. If it fails mentioning the S3 bucket does not exist, the outgoing maintainer needs to confirm the correct bucket name — check `backend.tf` in the repository for the bucket name being used.

Once init succeeds, run a plan to confirm Terraform sees the live infrastructure:

```bash
terraform plan
```

The output should end with `No changes. Your infrastructure matches the configuration.` If it shows pending changes, discuss with the outgoing maintainer before applying anything.

### 2.2 Verify the Bot is Live

In the Sterling Discord server, run `/profile`. If you have a registered profile, you should see your profile card. If not, run `/register` with any character name. If the bot responds correctly, it is live and healthy.

### 2.3 Verify Log Access

```bash
aws logs tail /aws/lambda/sterlingstan-verifier \
  --profile sterlingstan \
  --since 1h \
  --follow
```

Then run a command in Discord. You should see a log entry appear in your terminal within a few seconds. Repeat for the executor log group:

```bash
aws logs tail /aws/lambda/sterlingstan-executor \
  --profile sterlingstan \
  --since 1h \
  --follow
```

If you can see logs flowing, your observability access is confirmed.

---

## Part 3 — Rotating Credentials

Once you have full access, rotate the bot token so it is no longer tied to the outgoing maintainer's portal access. **Do this before the outgoing maintainer removes themselves from the Discord application team.**

### Step 1 — Regenerate the Bot Token

1. Go to https://discord.com/developers/applications, open the SterlingStan application.
2. Under **Bot**, click **Reset Token** and confirm.
3. Copy the new token immediately — it will not be shown again.

### Step 2 — Update the Secret in AWS

```bash
aws secretsmanager update-secret \
  --profile sterlingstan \
  --secret-id sterlingstan/discord \
  --secret-string '{
    "DISCORD_BOT_TOKEN":  "<new token>",
    "DISCORD_PUBLIC_KEY": "<unchanged — copy from portal>",
    "DISCORD_APP_ID":     "<unchanged>",
    "DISCORD_GUILD_ID":   "<unchanged>",
    "OFFICER_ROLE_ID":    "<unchanged>"
  }'
```

To retrieve the current values of the unchanged fields before overwriting:

```bash
aws secretsmanager get-secret-value \
  --profile sterlingstan \
  --secret-id sterlingstan/discord \
  --query SecretString \
  --output text
```

Copy the output, update only `DISCORD_BOT_TOKEN`, and use the full JSON in the update command above.

### Step 3 — Force Lambda Refresh

The Lambdas cache the secret in memory for the lifetime of each execution environment. To ensure they pick up the new credentials without waiting for a natural restart, force a redeployment of all three Lambdas. Each caches a different part of the secret: the Verifier caches the public key, the Executor caches the bot token, and the Registrar caches the bot token.

```bash
cd aqw-guild-bot/infrastructure
terraform apply -replace='module.lambda.aws_lambda_function.verifier' \
  -replace='module.lambda.aws_lambda_function.executor' \
  -replace='module.lambda.aws_lambda_function.registrar'
```

Type `yes` when prompted. This redeploys only the three Lambdas, leaving everything else untouched.

### Step 4 — Verify

Run `/profile` in Discord again. If it responds, the new token is working correctly. The outgoing maintainer can now remove themselves from the Discord application team.

---

## Part 4 — Routine Maintenance

### Deploying a Code Change

All code changes go through GitHub. The workflow is:

```bash
# 1. Pull the latest code
git pull origin main

# 2. Make your changes to the Python files

# 3. Commit and push
git add .
git commit -m "Description of change"
git push origin main

# 4. Deploy — Terraform detects the changed zip hash and redeploys only affected Lambdas
cd infrastructure
terraform apply
# Type 'yes' when prompted
```

If you added or changed any slash commands, re-register them with Discord after deploying:

```bash
aws lambda invoke \
  --profile sterlingstan \
  --function-name sterlingstan-registrar \
  --region us-east-1 \
  --payload '{}' \
  response.json && cat response.json
```

### Updating the Officer Role

If the Discord role that grants officer-level bot permissions changes (renamed, replaced, or a different role is chosen), update the stored secret:

```bash
# Get current values
aws secretsmanager get-secret-value \
  --profile sterlingstan \
  --secret-id sterlingstan/discord \
  --query SecretString \
  --output text

# Update with new OFFICER_ROLE_ID (right-click the role in Discord → Copy Role ID)
aws secretsmanager update-secret \
  --profile sterlingstan \
  --secret-id sterlingstan/discord \
  --secret-string '{ ... all fields, with updated OFFICER_ROLE_ID ... }'
```

No code change is needed. Because the warmup ping keeps the Lambdas alive indefinitely, a natural cold start may never occur — force a redeployment as shown in Part 3 Step 3 to apply the change immediately.

### Checking Costs

```bash
aws ce get-cost-and-usage \
  --profile sterlingstan \
  --time-period Start=$(date -d "$(date +%Y-%m-01)" +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics UnblendedCost
```

Expected total is under $0.50/month. If you see a significant spike, check CloudWatch Logs for unexpected high-volume invocations.

### Investigating an Error

If the bot stops responding or a command fails, check the logs:

```bash
# Recent verifier logs (signature failures, routing errors)
aws logs tail /aws/lambda/sterlingstan-verifier \
  --profile sterlingstan \
  --since 30m

# Recent executor logs (command errors, DynamoDB issues)
aws logs tail /aws/lambda/sterlingstan-executor \
  --profile sterlingstan \
  --since 30m
```

For a broader search across all recent invocations, use the AWS Console's CloudWatch Logs Insights with this query against the `/aws/lambda/sterlingstan-executor` log group:

```
fields @timestamp, @message
| filter @message like /ERROR/
| sort @timestamp desc
| limit 20
```

---

## Part 5 — Shutting the Bot Down

If the guild dissolves, the bot is no longer needed, or you are passing ownership to someone else and they prefer to start fresh, here is how to cleanly shut everything down.

### Temporary Suspension (bot goes offline, data preserved)

Remove the Interactions Endpoint URL from the Discord Developer Portal:

1. Go to https://discord.com/developers/applications → SterlingStan → General Information.
2. Clear the **Interactions Endpoint URL** field and save.

Discord will stop sending commands to the bot. The AWS infrastructure remains deployed and the DynamoDB data is intact. Restore service at any time by re-entering the endpoint URL (visible via `terraform output interactions_endpoint`).

### Permanent Shutdown (destroys all infrastructure and data)

> ⚠️ This is irreversible. All roster data stored in DynamoDB will be permanently deleted.

```bash
cd aqw-guild-bot/infrastructure
terraform destroy
# Review the list of resources to be destroyed, then type 'yes'
```

This removes all Lambdas, API Gateway, DynamoDB table, EventBridge rule, IAM roles, Secrets Manager secret reference, and CloudWatch log groups. It does **not** delete the two resources that were bootstrapped manually and are not tracked by Terraform — those must be cleaned up separately if desired:

```bash
# Delete the Terraform state bucket (only after terraform destroy completes)
aws s3 rm s3://sterlingstan-terraform-state --recursive --profile sterlingstan
aws s3api delete-bucket \
  --bucket sterlingstan-terraform-state \
  --profile sterlingstan

# Delete the Terraform lock table
aws dynamodb delete-table \
  --table-name sterlingstan-terraform-locks \
  --region us-east-1 \
  --profile sterlingstan
```

After infrastructure is destroyed, remove the bot from the Discord server and delete the application in the Discord Developer Portal if it is no longer needed.

---

## Part 6 — Passing to Another Maintainer

When you are ready to hand off to someone else, follow this same document from the beginning. The things you need to provide to your successor are:

| Item | How to hand it off |
|---|---|
| GitHub repository access | Add them as collaborator, or transfer repo ownership |
| AWS account access | Create an IAM user for them, or transfer root account credentials |
| Discord application access | Add them to the application Team in the Developer Portal |
| Terraform state bucket name | Found in `infrastructure/backend.tf` — `sterlingstan-terraform-state` |
| AWS region | `us-east-1` |

Once they have completed Part 2 (Verification) successfully, rotate the bot token per Part 3, then remove yourself from the Discord application team and revoke your AWS IAM credentials.

---

## Quick Reference

| Task | Command / Location |
|---|---|
| Verify AWS access | `aws sts get-caller-identity --profile sterlingstan` |
| Sync Terraform state | `cd infrastructure && terraform init` |
| Check for infrastructure drift | `terraform plan` |
| Deploy a code change | `terraform apply` |
| Re-register slash commands | `aws lambda invoke --profile sterlingstan --function-name sterlingstan-registrar --payload '{}'` |
| View live verifier logs | `aws logs tail /aws/lambda/sterlingstan-verifier --profile sterlingstan --follow` |
| View live executor logs | `aws logs tail /aws/lambda/sterlingstan-executor --profile sterlingstan --follow` |
| Rotate bot token | Update secret → `terraform apply -replace` on verifier + executor + registrar |
| Get current secret values | `aws secretsmanager get-secret-value --profile sterlingstan --secret-id sterlingstan/discord --query SecretString --output text` |
| Get API Gateway URL | `cd infrastructure && terraform output interactions_endpoint` |
| Suspend bot (reversible) | Remove Interactions Endpoint URL in Discord Developer Portal |
| Destroy all infrastructure | `terraform destroy` |
