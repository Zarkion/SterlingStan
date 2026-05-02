terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
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
  secret_name = var.secret_name
}

module "iam" {
  source       = "./modules/iam"
  project_name = var.project_name
  table_arn    = module.dynamodb.table_arn
  secret_arn   = module.secrets.secret_arn
  executor_arn = module.lambda.executor_arn
}

module "lambda" {
  source             = "./modules/lambda"
  project_name       = var.project_name
  secret_name        = var.secret_name
  verifier_role_arn  = module.iam.verifier_role_arn
  executor_role_arn  = module.iam.executor_role_arn
  registrar_role_arn = module.iam.registrar_role_arn
  table_name         = module.dynamodb.table_name
}

module "api_gateway" {
  source                = "./modules/api_gateway"
  project_name          = var.project_name
  verifier_invoke_arn   = module.lambda.verifier_invoke_arn
  verifier_function_arn = module.lambda.verifier_function_arn
}

module "eventbridge" {
  source                = "./modules/eventbridge"
  project_name          = var.project_name
  verifier_function_arn = module.lambda.verifier_function_arn
}
