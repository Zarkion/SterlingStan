terraform {
  backend "s3" {
    bucket         = "sterlingstan-terraform-state"
    key            = "sterlingstan/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "sterlingstan-terraform-locks"
    encrypt        = true
  }
}
