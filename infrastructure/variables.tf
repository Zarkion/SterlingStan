variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Prefix applied to all resource names."
  type        = string
  default     = "sterlingstan"
}

variable "secret_name" {
  description = "Name of the Secrets Manager secret holding Discord credentials."
  type        = string
  default     = "sterlingstan/discord"
}
