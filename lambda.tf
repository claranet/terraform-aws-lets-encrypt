module "lambda" {
  source = "github.com/claranet/terraform-aws-lambda?ref=v0.8.3"

  function_name = "${var.name}"
  description   = "Let's Encrypt certificate management"
  handler       = "lambda.lambda_handler"
  runtime       = "python3.6"
  memory_size   = 512
  timeout       = 300

  reserved_concurrent_executions = 1

  source_path = "${path.module}/lambda.py"

  attach_policy = true
  policy        = "${data.aws_iam_policy_document.lambda.json}"

  environment {
    variables {
      DOMAINS       = "${jsonencode(var.domains)}"
      EMAIL_ADDRESS = "${var.email_address}"
      FUNCTION_NAME = "${var.name}"
      STAGING       = "${var.staging ? 1 : 0}"
    }
  }
}

data "aws_iam_policy_document" "lambda" {
  statement {
    effect = "Allow"

    actions = [
      "acm:DescribeCertificate",
      "acm:GetCertificate",
      "acm:ImportCertificate",
      "acm:ListCertificates",
      "route53:ListHostedZones",
    ]

    resources = [
      "*",
    ]
  }

  statement {
    effect = "Allow"

    actions = [
      "route53:ChangeResourceRecordSets",
      "route53:GetChange",
      "ssm:GetParameter*",
      "ssm:PutParameter*",
    ]

    resources = [
      "arn:aws:route53:::change/*",
      "arn:aws:route53:::hostedzone/${var.hosted_zone_id}",
      "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter/${var.name}/*",
    ]
  }
}
