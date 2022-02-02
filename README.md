# terraform-aws-lets-encrypt

This Terraform module creates Let's Encrypt certificates with AWS Lambda and Route 53.

Inspired by [Arkadiy Tetelman's blog post and code](https://arkadiyt.com/2018/01/26/deploying-effs-certbot-in-aws-lambda/).

Certificates are imported into ACM, with the certificate's private key stored in the SSM Parameter Store.

The Lambda function returns the latest certificate. If no certificate exists, it will create one. If the existing certificate has expired or has less than 30 days left, it will create a new one and return that.

## Why use this?

* You want to use SSL but don't want to pay for a load balancer
* You are using auto scaling groups (Certbot does not suit them)
* You want client certificates (ELB/ALB does not handle that)

Our solution involves the following:

* EC2 instances run in an auto scaling group
* Nginx uses certificate files in a predefined path
* A boot script uses the Lambda function to install a certificate before Nginx starts
* A cron job uses the Lambda function regularly, installing new certificates and reloading Nginx
* Monitoring checks Nginx SSL certificates to ensure the whole thing works

## Usage

```hcl
module "lets_encrypt_cert" {
  source = "github.com/claranet/terraform-aws-lets-encrypt"

  name = "lets-encrypt-claranet"

  domains = [
    "claranet.co.uk",
    "www.claranet.co.uk",
  ]

  email_address  = "${var.email_address}"
  hosted_zone_id = "${data.aws_route53_zone.claranet.zone_id}"
}
```

This will create a Lambda function that generates and returns SSL certificates. An [example](./example/) of how to use the certificates has been included but setting this up is left as an exercise for the reader.

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|:----:|:-----:|:-----:|
| domains | Domain names to apply. The first domain provided will be the subject CN of the certificate, and all domains will be Subject Alternative Names on the certificate. | list | - | yes |
| email_address | Email used for Let's Encrypt registration and recovery contact. | string | - | yes |
| hosted_zone_id | Route53 Hosted Zone ID for the domains. | string | - | yes |
| name | Name used for Terraform resources. | string | - | yes |
| staging | Use Let's Encrypt staging environment (use this while testing). | string | `true` | no |

## Outputs

| Name | Description |
|------|-------------|
| lambda_function_arn | The ARN of the Lambda function. |
| lambda_function_name | The name of the Lambda function. |

## Generating new zip archive
 ### Install dependencies
 ```
 pip install --target ./certbot-1.22 --no-cache-dir certbot==1.22 certbot-dns-route53==1.22
```
 ### ZIP up dependencies
```
 cd certbot-1.22
 zip -r ../certbot-1.22.zip .
```
 ## Add code to root of zip
```
 zip -g certbot-1.22.zip lambda.py
```
 ### Use new zip file for Lambda and check into git. 