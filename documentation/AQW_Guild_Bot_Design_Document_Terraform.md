# AQW Guild Discord Bot — Design Document (AWS Serverless + Terraform Edition)

**Project Name:** AQW Guild Bot (working title: `SterlingStan`)
**Language:** Python 3.12
**Hosting:** AWS Serverless (Lambda + API Gateway + DynamoDB + Secrets Manager)
**Infrastructure-as-Code:** Terraform
**Version:** 3.0

---

## 1. Project Overview

SterlingStan is a purpose-built Discord bot for AdventureQuest Worlds (AQW) guilds. Members can link their Discord account to their in-game character name and record their favorite classes. Officers can look up, manage, and export the roster. The bot is designed to grow: the data model and Lambda structure make it straightforward to add new features — attendance tracking, officer notes, class-based queries, event sign-ups — without touching existing code.

### Why Serverless on AWS?

Running a Discord bot on a dedicated machine or VPS means paying for idle compute around the clock. For a guild bot that gets a handful of commands per hour at most, that is wasteful. A serverless approach on AWS means:

- **Pay only for actual invocations.** At guild-scale traffic, the monthly cost is typically under $1 — often within AWS's permanent free tier.
- **No server to maintain.** No OS patches, no reboots, no worrying about the machine going offline.
- **Built-in high availability.** Lambda and API Gateway are managed, multi-AZ AWS services with SLAs measured in nines.
- **Practical cloud experience.** The architecture uses native AWS services that map directly to real-world serverless patterns.

### Why Terraform for Infrastructure-as-Code?

The previous version used AWS SAM, which is excellent for AWS-native workflows but requires familiarity with SAM's CLI and CloudFormation conventions. Terraform is the better choice here for several reasons:

- **Provider-agnostic and widely understood.** If guild leadership changes hands, the next maintainer is far more likely to have seen Terraform HCL than AWS SAM templates. It is the most commonly used IaC tool in the industry.
- **Explicit resource graph.** Every AWS resource — Lambda, API Gateway, DynamoDB, IAM roles, Secrets Manager — is declared individually in HCL. There is no "magic" that abstracts resources away. A new maintainer can read the `.tf` files and see exactly what exists in the account.
- **State file as a handoff artifact.** Terraform tracks deployed infrastructure in a remote state file (stored in S3). Handing off the project means sharing AWS access and the state bucket — the next maintainer can run `terraform plan` immediately and see exactly what is deployed without logging into the console.
- **Destroy is one command.** `terraform destroy` tears down every resource cleanly. If the project is ever shut down, nothing is left running or accruing charges.
- **No SAM CLI, no Docker required for deployment.** Terraform itself handles packaging and uploading Lambda code. The only prerequisite is `terraform` and `aws configure`.

### Discord's Interaction Model

Traditional Discord bots use a persistent WebSocket connection (the "Gateway") — this is what `discord.py` uses and why it requires an always-on process. The serverless approach instead uses Discord's **HTTP Interactions Endpoint**: Discord POSTs every slash command to a URL you provide, your Lambda handles it and returns a response, and the connection closes. No persistent process, no WebSocket.

The one constraint this introduces is Discord's **3-second response deadline**: your endpoint must acknowledge an interaction within 3 seconds or Discord marks it as failed. The architecture addresses this with a two-Lambda pattern described in Section 5.

---

## 2. Feature Scope — Version 1.0

| Command | Description | Who |
|---|---|---|
| `/register` | Link your Discord account to an AQW character name | All members |
| `/setclasses` | Set your favorite/main AQW classes (up to 5) | All members |
| `/update` | Update your character name and/or classes | All members |
| `/profile` | View your own linked profile card | All members |
| `/unregister` | Remove your own profile (with confirmation) | All members |
| `/lookup` | Look up any member's profile by Discord mention | Officers |
| `/roster` | List all registered guild members | Officers |
| `/adminset` | Create or override any member's profile | Officers |
| `/adminremove` | Remove any member's profile (with confirmation) | Officers |

### Planned for Future Versions

- AQW character name verification via game API
- Automated "Registered" role assignment on `/register`
- Officer notes per member
- Event attendance and sign-up tracking
- Class-based roster filtering (`/roster class:Stonecrusher`)
- Web dashboard for officers

---

## 3. AWS Architecture Overview

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

### How a Command Flows

1. A member types `/profile` in Discord.
2. Discord POSTs the interaction payload to the API Gateway URL.
3. The **Verifier Lambda** fires. It validates the request signature using the bot's public key (from Secrets Manager) to prove the request really came from Discord. If the signature fails, it returns HTTP 401.
4. If valid, Verifier immediately returns `{ type: 5 }` — a "deferred response" — back to Discord within the 3-second window. Discord shows "SterlingStan is thinking…" to the user.
5. Verifier then invokes the **Executor Lambda** asynchronously (fire-and-forget), passing the full interaction payload.
6. Executor reads the command name from the payload, calls the appropriate handler, queries DynamoDB, builds a response embed, and POSTs it back to Discord via the interaction's follow-up webhook URL. Discord edits "SterlingStan is thinking…" into the actual response.
7. Both Lambdas exit. No compute runs until the next command.

---

## 4. Technology Stack

| Component | AWS Service | Purpose |
|---|---|---|
| HTTP endpoint | API Gateway (HTTP API) | Receives Discord interaction POSTs |
| Request verification & routing | Lambda — Verifier | Validates signatures, returns deferred ACK, dispatches Executor |
| Command logic | Lambda — Executor | Runs all command handlers |
| Database | DynamoDB (On-Demand) | Stores member profiles and class lists |
| Secrets | AWS Secrets Manager | Stores bot token and public key securely |
| Logging | CloudWatch Logs | Auto-captured Lambda logs for debugging |
| Infrastructure-as-Code | **Terraform** | Declares and manages all AWS resources |
| Terraform remote state | S3 + DynamoDB lock table | Stores `terraform.tfstate`; prevents concurrent applies |
| Command registration | Lambda — Registrar (one-shot) | Registers slash commands with Discord on deploy |
| Warmup scheduling | EventBridge Scheduled Rule | Pings Verifier every 10 minutes to prevent cold starts |
| Local dev / testing | `python -m pytest` + mock events | Unit-tests command handlers without AWS |

### Why DynamoDB Over SQLite/RDS?

On AWS, SQLite is not viable — Lambda functions have no persistent local storage. The serverless-native choice is DynamoDB:

- **No connection pool problem.** RDS requires a persistent TCP connection. Lambda spawns many concurrent instances, which can exhaust an RDS connection limit. The standard fix (RDS Proxy) adds ~$15–30/month — more than the rest of this stack combined. DynamoDB uses stateless HTTP calls, so there is no connection limit.
- **True pay-per-use.** DynamoDB On-Demand charges per read/write operation and per GB stored. At guild scale, the monthly bill is effectively $0.00 (within the permanent free tier of 25 GB storage and 200 million requests/month).
- **Millisecond latency.** Single-item lookups by primary key return in under 5ms.
- **Managed, no maintenance.** No patching, no vacuuming, no backups to configure — AWS handles everything, with Point-in-Time Recovery configurable in one Terraform line.

---

## 5. Lambda Design

### 5.1 Verifier Lambda

**Role:** Fast path — validate the Discord request signature, send a deferred ACK, trigger Executor.

**Key constraint:** Must complete within Discord's 3-second window.

**Runtime:** Python 3.12 | **Memory:** 128 MB | **Timeout:** 3 seconds

```python
# verifier/handler.py
import json, os, boto3
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

lambda_client = boto3.client("lambda")
secrets_client = boto3.client("secretsmanager")
_secret_cache = None  # cached after first cold-start fetch

def get_secret():
    global _secret_cache
    if not _secret_cache:
        raw = secrets_client.get_secret_value(SecretId=os.environ["SECRET_NAME"])
        _secret_cache = json.loads(raw["SecretString"])
    return _secret_cache

def handler(event, context):
    signature = event["headers"].get("x-signature-ed25519", "")
    timestamp  = event["headers"].get("x-signature-timestamp", "")
    body       = event["body"] or ""

    try:
        verify_key = VerifyKey(bytes.fromhex(get_secret()["DISCORD_PUBLIC_KEY"]))
        verify_key.verify(f"{timestamp}{body}".encode(), bytes.fromhex(signature))
    except BadSignatureError:
        return {"statusCode": 401, "body": "invalid signature"}

    payload = json.loads(body)

    # Respond to Discord's PING (used when first setting the Interactions Endpoint URL)
    if payload.get("type") == 1:
        return {"statusCode": 200, "body": json.dumps({"type": 1})}

    # For all slash commands: send DEFERRED response, then dispatch Executor async
    lambda_client.invoke(
        FunctionName=os.environ["EXECUTOR_FUNCTION_NAME"],
        InvocationType="Event",  # async fire-and-forget
        Payload=json.dumps(payload).encode()
    )

    return {"statusCode": 200, "body": json.dumps({"type": 5})}
```

### 5.2 Executor Lambda

**Role:** Slow path — run command logic, query DynamoDB, POST result back to Discord.

**Runtime:** Python 3.12 | **Memory:** 256 MB | **Timeout:** 30 seconds

```python
# executor/handler.py
import json, os, urllib.request, boto3
from commands import register, profile, roster, admin

secrets_client = boto3.client("secretsmanager")
_secret_cache = None

def get_secret():
    global _secret_cache
    if not _secret_cache:
        raw = secrets_client.get_secret_value(SecretId=os.environ["SECRET_NAME"])
        _secret_cache = json.loads(raw["SecretString"])
    return _secret_cache

DISPATCH = {
    "register":    register.handle,
    "setclasses":  register.handle_classes,
    "update":      register.handle_update,
    "unregister":  register.handle_unregister,
    "profile":     profile.handle,
    "lookup":      profile.handle_lookup,
    "roster":      roster.handle,
    "adminset":    admin.handle_set,
    "adminremove": admin.handle_remove,
}

def post_followup(app_id, token, data):
    url = f"https://discord.com/api/v10/webhooks/{app_id}/{token}/messages/@original"
    req = urllib.request.Request(
        url, data=json.dumps(data).encode(), method="PATCH",
        headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req)

def handler(event, context):
    command_name = event["data"]["name"]
    handler_fn = DISPATCH.get(command_name)
    response_data = handler_fn(event) if handler_fn else {"content": f"Unknown command: `{command_name}`"}
    post_followup(event["application_id"], event["token"], response_data)
```

### 5.3 Registrar Lambda (One-Shot)

A utility Lambda that calls Discord's API to register all slash commands with the guild. Invoked manually once after the initial deploy, and again whenever commands change. It has no API Gateway trigger and is never called by users.

---

## 6. DynamoDB Data Model

The design uses a **single-table pattern** with a composite primary key, which is idiomatic for DynamoDB and enables all access patterns without cross-table joins.

### Table: `sterlingstan-members`

| Attribute | Type | Description |
|---|---|---|
| `PK` (Partition Key) | `String` | `MEMBER#<discord_id>` |
| `SK` (Sort Key) | `String` | `PROFILE` for the base record; `CLASS#<order>` for class entries |
| `discord_tag` | `String` | Discord username, for display |
| `ign` | `String` | AQW in-game name |
| `class_name` | `String` | Class name (only on `CLASS#` items) |
| `registered_at` | `String` | ISO 8601 UTC timestamp |
| `updated_at` | `String` | ISO 8601 UTC timestamp |

### Access Patterns

| Query | DynamoDB Operation |
|---|---|
| Get a member's full profile + all classes | `Query` on `PK = MEMBER#<id>` |
| Check if a member exists | `GetItem` on `PK = MEMBER#<id>`, `SK = PROFILE` |
| List all members (roster) | `Scan` (fine at guild scale) |
| Delete a member and all their data | `BatchWriteItem` for all `PK = MEMBER#<id>` items |

---

## 7. Secrets Management

Bot credentials are stored in **AWS Secrets Manager**, never in environment variables, source code, or `.tf` files.

**Secret name:** `sterlingstan/discord`

**Secret value (JSON):**
```json
{
  "DISCORD_BOT_TOKEN":  "your_bot_token_here",
  "DISCORD_PUBLIC_KEY": "your_app_public_key_here",
  "DISCORD_APP_ID":     "your_application_id_here",
  "DISCORD_GUILD_ID":   "your_guild_id_here",
  "OFFICER_ROLE_ID":    "your_officer_role_id_here"
}
```

The secret ARN is passed to Lambdas via an environment variable (`SECRET_NAME`). Lambdas fetch and cache the secret at cold-start — Secrets Manager is called once per Lambda instance spin-up, not once per invocation.

The secret itself is created outside of Terraform (via the AWS CLI, see Section 10) to avoid storing sensitive values in the Terraform state file. Terraform only references the secret by name.

---

## 8. Terraform Infrastructure

### 8.1 Module Structure

```
infrastructure/
├── main.tf               # Root: calls all modules, wires outputs together
├── variables.tf          # Input variables (region, project name, etc.)
├── outputs.tf            # Outputs: API Gateway URL printed after apply
├── backend.tf            # Remote state config (S3 + DynamoDB lock)
│
└── modules/
    ├── dynamodb/
    │   ├── main.tf       # aws_dynamodb_table resource
    │   └── outputs.tf    # table_name, table_arn
    │
    ├── secrets/
    │   ├── main.tf       # aws_secretsmanager_secret data source (read-only reference)
    │   └── outputs.tf    # secret_arn
    │
    ├── iam/
    │   ├── main.tf       # IAM roles and policies for each Lambda
    │   └── outputs.tf    # role ARNs
    │
    ├── lambda/
    │   ├── main.tf       # aws_lambda_function for verifier, executor, registrar
    │   ├── variables.tf
    │   └── outputs.tf    # function ARNs and names
    │
    ├── api_gateway/
    │   ├── main.tf       # aws_apigatewayv2_api, integration, route, stage
    │   └── outputs.tf    # invoke_url
    │
    └── eventbridge/
        └── main.tf       # Scheduled warmup rule, target, and Lambda permission
```

### 8.2 Remote State (`backend.tf`)

Terraform state must be stored remotely so any maintainer can pick up where the last one left off. This requires an S3 bucket and a DynamoDB table for state locking — both are created **once manually** before any other Terraform work (a "bootstrap" step).

```hcl
# infrastructure/backend.tf
terraform {
  backend "s3" {
    bucket         = "sterlingstan-terraform-state"   # created in bootstrap step
    key            = "sterlingstan/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "sterlingstan-terraform-locks"   # created in bootstrap step
    encrypt        = true
  }
}
```

### 8.3 Root Configuration (`main.tf`)

```hcl
# infrastructure/main.tf
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  required_version = ">= 1.6"
}

provider "aws" {
  region = var.aws_region
}

module "dynamodb" {
  source       = "./modules/dynamodb"
  project_name = var.project_name
}

module "secrets" {
  source      = "./modules/secrets"
  secret_name = var.secret_name   # "sterlingstan/discord"
}

module "iam" {
  source         = "./modules/iam"
  project_name   = var.project_name
  table_arn      = module.dynamodb.table_arn
  secret_arn     = module.secrets.secret_arn
  executor_arn   = module.lambda.executor_arn
}

module "lambda" {
  source                  = "./modules/lambda"
  project_name            = var.project_name
  secret_name             = var.secret_name
  verifier_role_arn       = module.iam.verifier_role_arn
  executor_role_arn       = module.iam.executor_role_arn
  registrar_role_arn      = module.iam.registrar_role_arn
  table_name              = module.dynamodb.table_name
}

module "api_gateway" {
  source               = "./modules/api_gateway"
  project_name         = var.project_name
  verifier_invoke_arn  = module.lambda.verifier_invoke_arn
  verifier_function_arn = module.lambda.verifier_function_arn
}

module "eventbridge" {
  source                = "./modules/eventbridge"
  project_name          = var.project_name
  verifier_function_arn = module.lambda.verifier_function_arn
}
```

### 8.4 Variables (`variables.tf`)

```hcl
# infrastructure/variables.tf
variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Prefix applied to all resource names (e.g. 'sterlingstan')."
  type        = string
  default     = "sterlingstan"
}

variable "secret_name" {
  description = "Name of the Secrets Manager secret holding Discord credentials."
  type        = string
  default     = "sterlingstan/discord"
}
```

### 8.5 DynamoDB Module (`modules/dynamodb/main.tf`)

```hcl
resource "aws_dynamodb_table" "members" {
  name         = "${var.project_name}-members"
  billing_mode = "PAY_PER_REQUEST"  # On-Demand: no capacity planning needed

  hash_key  = "PK"
  range_key = "SK"

  attribute {
    name = "PK"
    type = "S"
  }
  attribute {
    name = "SK"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true  # 35-day rolling backup, no additional config
  }

  tags = {
    Project = var.project_name
  }
}
```

### 8.6 IAM Module (`modules/iam/main.tf`)

Each Lambda gets its own IAM role with only the permissions it needs. This is the principle of least privilege — if a Lambda is compromised, the blast radius is limited to what that role can do.

```hcl
# Shared assume-role policy for all Lambda functions
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# ── Verifier Role ──────────────────────────────────────────────────────────────
resource "aws_iam_role" "verifier" {
  name               = "${var.project_name}-verifier-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy" "verifier" {
  role = aws_iam_role.verifier.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # CloudWatch Logs (basic Lambda execution)
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        # Read Discord credentials from Secrets Manager
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = var.secret_arn
      },
      {
        # Invoke Executor asynchronously — but ONLY the Executor
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = var.executor_arn
      }
    ]
  })
}

# ── Executor Role ──────────────────────────────────────────────────────────────
resource "aws_iam_role" "executor" {
  name               = "${var.project_name}-executor-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy" "executor" {
  role = aws_iam_role.executor.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = var.secret_arn
      },
      {
        # Full CRUD on the members table — no access to other tables
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem", "dynamodb:Query", "dynamodb:Scan",
                    "dynamodb:BatchWriteItem"]
        Resource = var.table_arn
      }
    ]
  })
}

# ── Registrar Role (one-shot, minimal permissions) ────────────────────────────
resource "aws_iam_role" "registrar" {
  name               = "${var.project_name}-registrar-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy" "registrar" {
  role = aws_iam_role.registrar.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = var.secret_arn
      }
      # No DynamoDB access — the registrar only talks to Discord's API
    ]
  })
}
```

### 8.7 Lambda Module (`modules/lambda/main.tf`)

Terraform packages Lambda code by zipping the source directory automatically using the `archive_file` data source.

```hcl
# ── Zip the source directories ─────────────────────────────────────────────────
data "archive_file" "verifier" {
  type        = "zip"
  source_dir  = "${path.root}/../verifier"
  output_path = "${path.module}/builds/verifier.zip"
}

data "archive_file" "executor" {
  type        = "zip"
  source_dir  = "${path.root}/../executor"
  output_path = "${path.module}/builds/executor.zip"
}

data "archive_file" "registrar" {
  type        = "zip"
  source_dir  = "${path.root}/../registrar"
  output_path = "${path.module}/builds/registrar.zip"
}

# ── Verifier Lambda ────────────────────────────────────────────────────────────
resource "aws_lambda_function" "verifier" {
  function_name    = "${var.project_name}-verifier"
  role             = var.verifier_role_arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.verifier.output_path
  source_code_hash = data.archive_file.verifier.output_base64sha256
  memory_size      = 128
  timeout          = 3

  environment {
    variables = {
      SECRET_NAME             = var.secret_name
      EXECUTOR_FUNCTION_NAME  = aws_lambda_function.executor.function_name
    }
  }
}

# ── Executor Lambda ────────────────────────────────────────────────────────────
resource "aws_lambda_function" "executor" {
  function_name    = "${var.project_name}-executor"
  role             = var.executor_role_arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.executor.output_path
  source_code_hash = data.archive_file.executor.output_base64sha256
  memory_size      = 256
  timeout          = 30

  environment {
    variables = {
      SECRET_NAME = var.secret_name
      TABLE_NAME  = var.table_name
    }
  }
}

# ── Registrar Lambda ───────────────────────────────────────────────────────────
resource "aws_lambda_function" "registrar" {
  function_name    = "${var.project_name}-registrar"
  role             = var.registrar_role_arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.registrar.output_path
  source_code_hash = data.archive_file.registrar.output_base64sha256
  memory_size      = 128
  timeout          = 30

  environment {
    variables = {
      SECRET_NAME = var.secret_name
    }
  }
}
```

### 8.8 API Gateway Module (`modules/api_gateway/main.tf`)

```hcl
resource "aws_apigatewayv2_api" "sterlingstan" {
  name          = "${var.project_name}-api"
  protocol_type = "HTTP"
  description   = "SterlingStan Discord interactions endpoint"
}

resource "aws_apigatewayv2_integration" "verifier" {
  api_id                 = aws_apigatewayv2_api.sterlingstan.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.verifier_invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "interactions" {
  api_id    = aws_apigatewayv2_api.sterlingstan.id
  route_key = "POST /interactions"
  target    = "integrations/${aws_apigatewayv2_integration.verifier.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.sterlingstan.id
  name        = "$default"
  auto_deploy = true
}

# Grant API Gateway permission to invoke the Verifier Lambda
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.verifier_function_arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.sterlingstan.execution_arn}/*/*"
}

output "invoke_url" {
  value       = "${aws_apigatewayv2_stage.default.invoke_url}/interactions"
  description = "Paste this into Discord Developer Portal > Interactions Endpoint URL"
}
```

### 8.9 Root Outputs (`outputs.tf`)

```hcl
# infrastructure/outputs.tf
output "interactions_endpoint" {
  description = "Paste this URL into Discord Developer Portal > Interactions Endpoint URL"
  value       = module.api_gateway.invoke_url
}

output "registrar_function_name" {
  description = "Use this to invoke the Registrar manually after deploy"
  value       = module.lambda.registrar_function_name
}
```

---

## 9. Project Structure

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
├── registrar/                       # One-shot command registration Lambda
│   ├── handler.py
│   └── requirements.txt
│
├── shared/                          # Shared utilities (copied into Lambda zips as needed)
│   ├── db.py                        # DynamoDB helper functions
│   ├── secrets.py                   # Secrets Manager client with in-memory cache
│   ├── embeds.py                    # Discord embed dict builders
│   └── checks.py                    # Officer role verification
│
└── tests/
    ├── events/                      # Sample Lambda event payloads for local testing
    │   ├── profile_command.json
    │   └── register_command.json
    └── test_commands.py             # Unit tests for command handlers
```

---

## 10. Setup and Deployment

### Prerequisites

| Tool | Purpose | Install |
|---|---|---|
| Terraform ≥ 1.6 | Deploy infrastructure | [developer.hashicorp.com/terraform/install](https://developer.hashicorp.com/terraform/install) |
| AWS CLI v2 | Authenticate and run one-off commands | [docs.aws.amazon.com/cli](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |
| Python 3.12 | Run and test Lambda code locally | [python.org](https://python.org) |

No Docker. No SAM CLI. No additional tooling.

### Step 1 — Discord Developer Portal Setup

1. Go to https://discord.com/developers/applications and create a new Application.
2. Under **Bot**, copy the **Token**.
3. Under **General Information**, copy the **Application ID** and **Public Key**.
4. Under **OAuth2 → URL Generator**, select scopes: `bot` and `applications.commands`. Bot permissions: `Send Messages`, `Embed Links`. Use the URL to invite the bot to your guild.
5. Copy the guild's **Server ID** (right-click server icon → Copy Server ID with Developer Mode on).
6. Copy the **Officer Role ID** (right-click the role → Copy Role ID).

### Step 2 — AWS Account Setup

```bash
# Configure AWS CLI with your credentials
aws configure
# AWS Access Key ID: ...
# AWS Secret Access Key: ...
# Default region: us-east-1
# Default output format: json
```

### Step 3 — Bootstrap Remote State (one-time only)

This creates the S3 bucket and DynamoDB table that Terraform uses to store state. Run these commands once, then never again — these resources are intentionally managed outside of Terraform to avoid a chicken-and-egg problem.

```bash
# Create the S3 bucket for Terraform state
aws s3api create-bucket \
  --bucket sterlingstan-terraform-state \
  --region us-east-1

# Enable versioning (allows rolling back to previous state files)
aws s3api put-bucket-versioning \
  --bucket sterlingstan-terraform-state \
  --versioning-configuration Status=Enabled

# Enable server-side encryption
aws s3api put-bucket-encryption \
  --bucket sterlingstan-terraform-state \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

# Create the DynamoDB table for state locking
aws dynamodb create-table \
  --table-name sterlingstan-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

### Step 4 — Store Discord Secrets

The secret is created via CLI so the sensitive values never appear in a `.tf` file or the Terraform state.

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

To update a secret value later:
```bash
aws secretsmanager update-secret \
  --secret-id sterlingstan/discord \
  --secret-string '{ ... updated JSON ... }'
```

### Step 5 — Deploy with Terraform

```bash
cd infrastructure

# Download the AWS provider plugin
terraform init

# Preview every resource that will be created — review before applying
terraform plan

# Create all AWS resources
terraform apply
# Type 'yes' when prompted.
# When complete, Terraform prints the Interactions Endpoint URL.
```

### Step 6 — Connect Discord to the Endpoint

1. Copy the `interactions_endpoint` URL from Terraform's output.
2. In the Discord Developer Portal, go to **General Information → Interactions Endpoint URL**, paste it, and click **Save Changes**.
3. Discord sends a PING to the endpoint. The Verifier Lambda handles it automatically and Discord confirms the URL is valid.

### Step 7 — Register Slash Commands (one-time)

```bash
aws lambda invoke \
  --function-name sterlingstan-registrar \
  --region us-east-1 \
  --payload '{}' \
  response.json && cat response.json
```

The bot is now live. Test `/register` in your Discord server.

### Updating the Bot

```bash
# After any code change to a Lambda:
cd infrastructure
terraform apply
# Terraform detects the changed zip hash and redeploys only the affected Lambda.

# After adding or modifying slash commands, re-invoke the Registrar:
aws lambda invoke --function-name sterlingstan-registrar --payload '{}' response.json
```

### Tearing Everything Down

```bash
cd infrastructure
terraform destroy
# Type 'yes'. All Lambda, API Gateway, DynamoDB, EventBridge, and IAM resources are deleted.
# The S3 state bucket and DynamoDB lock table (bootstrapped manually) must be
# deleted manually if desired, as they are not tracked by this Terraform config.
```

### Handing Off to a New Maintainer

1. Give the new maintainer AWS IAM credentials with sufficient permissions (or transfer account ownership).
2. Share the name of the state bucket (`sterlingstan-terraform-state`) and region.
3. They clone the repo, run `aws configure`, update `backend.tf` if needed, and run `terraform init` — Terraform downloads the existing state and they are immediately in sync with what is deployed.
4. They update the Discord secret if the bot token needs to be rotated:
   ```bash
   aws secretsmanager update-secret --secret-id sterlingstan/discord --secret-string '{ ... }'
   ```

---

## 11. Permission System

Permissions are enforced inside the Executor Lambda by inspecting the `member.roles` array in Discord's interaction payload — Discord includes this on every interaction automatically.

```python
# shared/checks.py
from shared.secrets import get_secret

def is_officer(interaction: dict) -> bool:
    officer_role_id = get_secret()["OFFICER_ROLE_ID"]
    member_roles = interaction.get("member", {}).get("roles", [])
    return officer_role_id in member_roles
```

Every officer-only command handler calls `is_officer(interaction)` first and returns an ephemeral error embed if it returns `False`. The officer role ID is stored in Secrets Manager alongside the bot token — changing which role has officer permissions is a one-line secret update, not a code change or redeployment.

---

## 12. Command Specifications

All responses are ephemeral (visible only to the invoking user) unless otherwise noted.

### `/register`
Checks the user isn't already registered. Validates `ign` is 3–20 alphanumeric characters. Writes a `PROFILE` item to DynamoDB. Confirms with a profile card embed.

### `/setclasses`
Parses comma-separated input, validates 1–5 non-empty entries. Deletes existing `CLASS#` items for the user, then batch-writes the new list in order.

### `/update`
Accepts optional `ign` and/or `classes` parameters (at least one required). Updates only the provided fields via DynamoDB `UpdateItem`.

### `/profile`
Queries all items under `PK = MEMBER#<user_id>`. Renders a Discord embed with the member's IGN, classes, and registration date.

```
╔═══════════════════════════╗
║  🗡️  HeroOfLore           ║
║  Discord: @HeroPlayer     ║
║  Member since: 2025-04-01 ║
║                           ║
║  Favorite Classes:        ║
║  1. Void Highlord         ║
║  2. Stonecrusher          ║
║  3. Archpaladin           ║
╚═══════════════════════════╝
```

### `/lookup`
Officer only. Accepts a Discord member mention. Queries and renders a profile card for the target user.

### `/roster`
Officer only. Scans the DynamoDB table for all `SK = PROFILE` items. Returns a paginated embed (10 members per page) showing Discord tag and AQW IGN.

### `/unregister` and `/adminremove`
Both send a confirmation embed with "Yes, remove it" / "Cancel" buttons before deleting. On confirm, all `PK = MEMBER#<id>` items are batch-deleted.

### `/adminset`
Officer only. Takes a Discord member mention plus optional `ign` and/or `classes`. Creates a profile if the target user has none.

---

## 13. Cost Estimate

At typical AQW guild scale (50–150 members, ~200 commands/day):

| Service | Usage | Monthly Cost |
|---|---|---|
| Lambda | ~6,000 invocations/month, ~200ms avg | **$0.00** (free tier: 1M invocations/month) |
| API Gateway | ~3,000 requests/month | **$0.00** (free tier: 1M requests/month) |
| DynamoDB | ~6,000 ops/month, <1 MB storage | **$0.00** (free tier: 25 GB, 200M requests/month) |
| Secrets Manager | 1 secret + ~500 API calls/month | **~$0.40** ($0.40/secret/month + $0.05/10K calls) |
| CloudWatch Logs | ~10 MB logs/month | **$0.00** (free tier: 5 GB) |
| S3 (Terraform state) | <1 MB, <100 operations/month | **$0.00** (free tier: 5 GB, 20K GET requests) |
| DynamoDB (Terraform locks) | <10 ops/month | **$0.00** |
| **Total** | | **~$0.40–$0.50/month** |

The Secrets Manager secret is the only real cost. Everything else falls within AWS's permanent free tier at this scale.

---

## 14. Observability

All Lambda invocations produce logs automatically in CloudWatch Logs:

- `/aws/lambda/sterlingstan-verifier` — signature failures, dispatch events
- `/aws/lambda/sterlingstan-executor` — command results, DynamoDB errors, Discord webhook failures

Add structured logging in both Lambdas for searchable, queryable logs:

```python
import json, logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

logger.info(json.dumps({
    "event": "command_executed",
    "command": "register",
    "user_id": interaction["member"]["user"]["id"],
    "ign": ign
}))
```

Use **CloudWatch Logs Insights** to query across invocations:

```
fields @timestamp, event, command, user_id
| filter event = "command_executed"
| sort @timestamp desc
| limit 50
```

AWS X-Ray can be added later for full request tracing between Verifier and Executor — this is a two-line addition to the Terraform Lambda resources.

---

## 15. Warmup Strategy

Lambda functions that haven't been invoked recently are shut down by AWS to save resources. When a completely idle function receives a request, it takes a moment to spin back up — this is called a cold start. For the Verifier Lambda, a slow cold start can push past Discord's 3-second response deadline, causing the user to see "The application did not respond."

To prevent this, an **EventBridge scheduled rule** fires every 10 minutes and invokes the Verifier Lambda with a dummy warmup payload. The Lambda recognizes the ping, does nothing, and exits. This keeps the execution environment alive between real commands, eliminating cold starts without adding any meaningful cost (a few thousand scheduled invocations per month fall well within the free tier).

### Verifier Handler Change

The Verifier handler needs one additional check at the top to detect and discard warmup events before attempting signature validation:

```python
def handler(event, context):
    # Discard EventBridge warmup pings immediately
    if event.get("source") == "sterlingstan.warmup":
        return {"statusCode": 200, "body": "warm"}

    signature = event["headers"].get("x-signature-ed25519", "")
    # ... rest of handler unchanged
```

### EventBridge Module (`modules/eventbridge/main.tf`)

```hcl
# Scheduled rule: fires every 10 minutes
resource "aws_cloudwatch_event_rule" "warmup" {
  name                = "${var.project_name}-warmup"
  description         = "Keeps the Verifier Lambda warm to prevent cold-start timeouts"
  schedule_expression = "rate(10 minutes)"
}

# The warmup payload — recognized and discarded by the Verifier handler
resource "aws_cloudwatch_event_target" "warmup" {
  rule  = aws_cloudwatch_event_rule.warmup.name
  arn   = var.verifier_function_arn
  input = jsonencode({ source = "sterlingstan.warmup" })
}

# Grant EventBridge permission to invoke the Verifier Lambda
resource "aws_lambda_permission" "eventbridge_warmup" {
  statement_id  = "AllowEventBridgeWarmup"
  action        = "lambda:InvokeFunction"
  function_name = var.verifier_function_arn
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.warmup.arn
}
```

### IAM Addition

The EventBridge service invokes the Verifier directly using its own AWS-managed permissions (granted by `aws_lambda_permission` above) — no changes to the Verifier's IAM role are needed. The Verifier role does not need to be able to invoke itself.

---

## 16. Extension Roadmap

New commands are new handler functions in `executor/commands/`. New data fields are new DynamoDB attributes (no schema migration). New AWS resources are new Terraform resources in the relevant module.

| Phase | Feature | Changes Required |
|---|---|---|
| v1.1 | Class autocomplete | New Lambda Layer with class list; update `modules/lambda/main.tf` |
| v1.2 | Auto "Registered" Discord role on `/register` | Discord Bot API call in `register.py` |
| v1.3 | Officer notes per member | New `NOTE#<timestamp>` SK items; new commands in `admin.py` |
| v1.4 | Event attendance tracking | New `EVENT#` items; `/event` and `/checkin` commands |
| v2.0 | Automated slash command registration on deploy | Terraform `null_resource` + `local-exec` to invoke Registrar after apply |
| v2.1 | Web dashboard for officers | New Terraform module: S3 + CloudFront + Cognito + API Gateway |

---

## 17. Key Design Principles

1. **Discord user ID is the primary key** — usernames change; Discord's internal snowflake ID does not.
2. **Deferred responses are mandatory** — every command returns `type: 5` from Verifier within 3 seconds, then posts the real result via follow-up webhook. This is the only reliable pattern for serverless Discord bots.
3. **Separation of concerns across Lambdas** — Verifier validates and routes only. Executor runs command logic only. Registrar manages slash command registration only. Each function has one job.
4. **Least-privilege IAM** — each Lambda role is scoped to exactly what it needs. Verifier cannot touch DynamoDB. Executor cannot invoke other Lambdas. Defined explicitly in `modules/iam/main.tf`.
5. **Everything in Terraform, always** — every AWS resource is declared in HCL. Nothing is created by clicking in the console. The entire stack can be reviewed, reproduced, or destroyed by anyone with AWS credentials and the repo.
6. **Secrets outside of Terraform state** — Discord credentials are created via AWS CLI and only referenced by name in Terraform. They never appear in `.tf` files or `terraform.tfstate`.
7. **Remote state enables handoff** — the S3 backend means any future maintainer can clone the repo, run `terraform init`, and immediately have full visibility into and control over what is deployed.
