locals {
  shared_files = fileset("${path.root}/../shared", "*.py")
}

# ── Verifier ──────────────────────────────────────────────────────────────────
data "archive_file" "verifier" {
  type        = "zip"
  output_path = "${path.module}/builds/verifier.zip"

  dynamic "source" {
    for_each = fileset("${path.root}/../verifier", "*.py")
    content {
      content  = file("${path.root}/../verifier/${source.value}")
      filename = source.value
    }
  }

  source {
    content  = file("${path.root}/../verifier/requirements.txt")
    filename = "requirements.txt"
  }

  dynamic "source" {
    for_each = local.shared_files
    content {
      content  = file("${path.root}/../shared/${source.value}")
      filename = "shared/${source.value}"
    }
  }
}

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
      SECRET_NAME            = var.secret_name
      EXECUTOR_FUNCTION_NAME = aws_lambda_function.executor.function_name
    }
  }
}

# ── Executor ──────────────────────────────────────────────────────────────────
data "archive_file" "executor" {
  type        = "zip"
  output_path = "${path.module}/builds/executor.zip"

  dynamic "source" {
    for_each = fileset("${path.root}/../executor", "**/*.py")
    content {
      content  = file("${path.root}/../executor/${source.value}")
      filename = source.value
    }
  }

  dynamic "source" {
    for_each = local.shared_files
    content {
      content  = file("${path.root}/../shared/${source.value}")
      filename = "shared/${source.value}"
    }
  }
}

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

# ── Registrar ─────────────────────────────────────────────────────────────────
data "archive_file" "registrar" {
  type        = "zip"
  output_path = "${path.module}/builds/registrar.zip"

  dynamic "source" {
    for_each = fileset("${path.root}/../registrar", "*.py")
    content {
      content  = file("${path.root}/../registrar/${source.value}")
      filename = source.value
    }
  }

  dynamic "source" {
    for_each = local.shared_files
    content {
      content  = file("${path.root}/../shared/${source.value}")
      filename = "shared/${source.value}"
    }
  }
}

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
