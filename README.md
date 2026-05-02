# SterlingStan

A serverless Discord bot for the Sterling AdventureQuest Worlds guild. Members can link their Discord account to their AQW character name and list their favorite classes. Officers can look up any member, view the full roster, and manage records on behalf of others.

Built with Python 3.12, deployed to AWS via Terraform.

---

## Commands

| Command | Description | Who |
|---|---|---|
| `/register` | Link your Discord account to your AQW character name | All members |
| `/setclasses` | Set your favorite AQW classes (up to 5, comma-separated) | All members |
| `/update` | Update your character name and/or classes | All members |
| `/profile` | View your own profile card | All members |
| `/unregister` | Remove your own profile (requires confirmation) | All members |
| `/lookup` | Look up any member's profile by Discord mention | Officers |
| `/roster` | List all registered guild members | Officers |
| `/adminset` | Create or override any member's profile | Officers |
| `/adminremove` | Remove any member's profile (requires confirmation) | Officers |

Officer access is controlled by a Discord role. The role ID is stored in AWS Secrets Manager and can be updated without a code change or redeployment.

---

## Architecture

The bot uses Discord's HTTP Interactions Endpoint rather than a persistent WebSocket connection. Discord POSTs each slash command to an API Gateway URL; a Lambda function handles it and responds. No always-on process.

```
Discord Client
     │
     │  HTTPS POST (slash command interaction)
     ▼
┌─────────────────────────┐
│   API Gateway (HTTP)    │  ← Single endpoint, all interactions
└────────────┬────────────┘
             │ Invoke (sync)
             ▼
┌─────────────────────────┐
│   Verifier Lambda       │  ← Validates Discord signature
│   (Python 3.12)         │    Returns HTTP 200 + type:5 (DEFERRED)
│   Timeout: 3s           │    Then invokes Executor asynchronously
└────────────┬────────────┘
             │ InvokeAsync (fire-and-forget)
             ▼
┌─────────────────────────┐       ┌──────────────────────────┐
│   Executor Lambda       │──────▶│   DynamoDB               │
│   (Python 3.12)         │       │   (sterlingstan-members) │
│   Timeout: 30s          │       └──────────────────────────┘
└────────────┬────────────┘
             │ POST (follow-up webhook)
             ▼
Discord Interaction Webhook
(edits the "Bot is thinking…" message)
```

Discord requires an initial response within 3 seconds. The Verifier Lambda handles this by immediately returning a deferred acknowledgement, then invoking the Executor asynchronously. The Executor does the real work and posts the result back via Discord's follow-up webhook. An EventBridge scheduled rule pings the Verifier every 10 minutes to prevent cold-start delays.

**AWS services used:** API Gateway · Lambda (×3) · DynamoDB · Secrets Manager · EventBridge · CloudWatch Logs · S3 (Terraform state) · DynamoDB (Terraform state lock)

---

## Repository Structure

```
aqw-guild-bot/
├── infrastructure/                  # All Terraform code — the entire AWS stack
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── backend.tf
│   └── modules/
│       ├── dynamodb/
│       ├── secrets/
│       ├── iam/
│       ├── lambda/
│       ├── api_gateway/
│       └── eventbridge/
│
├── verifier/                        # Verifier Lambda source
│   ├── handler.py
│   └── requirements.txt             # PyNaCl only
│
├── executor/                        # Executor Lambda source
│   ├── handler.py
│   ├── requirements.txt
│   └── commands/
│       ├── __init__.py
│       ├── register.py              # /register, /setclasses, /update, /unregister
│       ├── profile.py               # /profile, /lookup
│       ├── roster.py                # /roster
│       └── admin.py                 # /adminset, /adminremove
│
├── registrar/                       # One-shot Lambda: registers slash commands with Discord
│   ├── handler.py
│   └── requirements.txt
│
├── shared/                          # Utilities shared across Lambda packages
│   ├── db.py                        # DynamoDB helper functions
│   ├── secrets.py                   # Secrets Manager client with in-memory cache
│   ├── embeds.py                    # Discord embed dict builders
│   └── checks.py                    # Officer role verification
│
├── tests/
│   ├── events/                      # Sample Lambda event payloads for local testing
│   │   ├── profile_command.json
│   │   └── register_command.json
│   ├── conftest.py                  # pytest fixtures: mocked AWS resources, interaction payloads
│   └── test_commands.py
│
├── requirements-dev.txt             # Dev/test dependencies (pytest, moto, etc.) — not packaged into Lambdas
│
└── documentation/
    ├── AQW_Guild_Bot_Design_Document_Terraform.md   # Full technical design document
    ├── SterlingStan_Handoff_Instructions.md         # Maintainer handoff guide
    └── SterlingStan_Guild_Overview.md               # Non-technical guild leadership overview
```

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.12 | [python.org](https://python.org) |
| Terraform | ≥ 1.6 | [developer.hashicorp.com/terraform/install](https://developer.hashicorp.com/terraform/install) |
| AWS CLI | v2 | [docs.aws.amazon.com/cli](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |

No Docker. No SAM CLI.

---

## First-Time Deployment

### 1. Discord Developer Portal

1. Create a new Application at https://discord.com/developers/applications and add a Bot.
2. Under **Bot**, copy the **Token**.
3. Under **General Information**, copy the **Application ID** and **Public Key**.
4. Under **OAuth2 → URL Generator**, select scopes `bot` and `applications.commands`, permissions `Send Messages` and `Embed Links`. Use the generated URL to invite the bot to your server.
5. Copy the guild's **Server ID** (right-click server → Copy Server ID; requires Developer Mode).
6. Copy the **Officer Role ID** (right-click role → Copy Role ID).

### 2. AWS CLI

```bash
aws configure
# Enter your Access Key ID, Secret Access Key, region (us-east-1), and output format (json)
```

### 3. Bootstrap Terraform Remote State

These two resources store Terraform's state file and prevent concurrent applies. Create them once manually — they are intentionally outside Terraform to avoid a bootstrap chicken-and-egg problem.

```bash
# S3 bucket for state
aws s3api create-bucket --bucket sterlingstan-terraform-state --region us-east-1
aws s3api put-bucket-versioning \
  --bucket sterlingstan-terraform-state \
  --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption \
  --bucket sterlingstan-terraform-state \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

# DynamoDB table for state locking
aws dynamodb create-table \
  --table-name sterlingstan-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

### 4. Store Discord Credentials

Credentials are stored in AWS Secrets Manager and never in code or Terraform files.

```bash
aws secretsmanager create-secret \
  --name sterlingstan/discord \
  --region us-east-1 \
  --secret-string '{
    "DISCORD_BOT_TOKEN":  "your_bot_token",
    "DISCORD_PUBLIC_KEY": "your_public_key",
    "DISCORD_APP_ID":     "your_app_id",
    "DISCORD_GUILD_ID":   "your_guild_id",
    "OFFICER_ROLE_ID":    "your_officer_role_id"
  }'
```

### 5. Deploy with Terraform

```bash
cd infrastructure
terraform init
terraform plan    # review what will be created
terraform apply   # type 'yes' to confirm
```

Terraform prints the `interactions_endpoint` URL on completion.

### 6. Connect Discord to the Endpoint

1. Copy the `interactions_endpoint` URL from Terraform's output.
2. In the Discord Developer Portal, go to **General Information → Interactions Endpoint URL**, paste it, and save.
3. Discord sends a verification PING — the Verifier Lambda handles it automatically.

### 7. Register Slash Commands

```bash
aws lambda invoke \
  --function-name sterlingstan-registrar \
  --region us-east-1 \
  --payload '{}' \
  response.json && cat response.json
```

The bot is now live.

---

## Ongoing Development

### Deploying a Code Change

```bash
cd infrastructure
terraform apply
```

Terraform detects the changed source zip hash and redeploys only the affected Lambda(s). If you added or changed slash commands, re-run the Registrar invocation from Step 7 above.

### Running Tests Locally

```bash
python -m pytest tests/
```

Test events in `tests/events/` can be used to invoke Lambdas locally without AWS.

### Updating a Secret Value

```bash
# Retrieve current values first
aws secretsmanager get-secret-value \
  --secret-id sterlingstan/discord \
  --query SecretString \
  --output text

# Write the full updated JSON
aws secretsmanager update-secret \
  --secret-id sterlingstan/discord \
  --secret-string '{ ...full updated JSON... }'
```

Because Lambdas cache secrets in memory, force a redeployment after rotating credentials:

```bash
cd infrastructure
terraform apply \
  -replace='module.lambda.aws_lambda_function.verifier' \
  -replace='module.lambda.aws_lambda_function.executor' \
  -replace='module.lambda.aws_lambda_function.registrar'
```

---

## Cost

~$0.40–$0.50/month at typical guild scale (50–150 members, ~200 commands/day). The Secrets Manager secret ($0.40/month) is the only real cost — Lambda, API Gateway, DynamoDB, EventBridge, and CloudWatch all fall within AWS's permanent free tier at this usage level.

---

## Documentation

| Document | Description |
|---|---|
| `documentation/AQW_Guild_Bot_Design_Document_Terraform.md` | Full technical design: architecture, data model, all Terraform modules, deployment, observability, and extension roadmap |
| `documentation/SterlingStan_Handoff_Instructions.md` | Step-by-step guide for transferring maintainership |
| `documentation/SterlingStan_Guild_Overview.md` | Non-technical overview for guild leadership |
