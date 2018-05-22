variable "top_domain" {
  type = "string"
}

variable "email" {
  type = "string"
}

data "aws_route53_zone" "zone" {
  name = "${var.top_domain}."
}

resource "random_id" "name" {
  byte_length = 4
  prefix      = "tf-aws-lets-encrypt-test-"
}

module "lets_encrypt_cert" {
  source = ".."

  name = "${random_id.name.hex}"

  domains = [
    "${random_id.name.hex}-1.${var.top_domain}",
    "${random_id.name.hex}-2.${var.top_domain}",
  ]

  email_address  = "${var.email}"
  hosted_zone_id = "${data.aws_route53_zone.zone.zone_id}"
}
