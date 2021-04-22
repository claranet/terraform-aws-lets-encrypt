variable "name" {
  description = "Name used for Terraform resources."
  type        = string
}

variable "domains" {
  description = "Domain names to apply. The first domain provided will be the subject CN of the certificate, and all domains will be Subject Alternative Names on the certificate."
  type        = list
}

variable "email_address" {
  description = "Email used for Let's Encrypt registration and recovery contact."
  type        = string
}

variable "hosted_zone_id" {
  description = "Route53 Hosted Zone ID for the domains."
  type        = string
}

variable "staging" {
  description = "Use Let's Encrypt staging environment (use this while testing)."
  type        = bool
  default     = true
}
