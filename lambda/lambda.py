import boto3
import collections
import datetime
import json
import os
import subprocess
import tempfile


DOMAINS = json.loads(os.environ['DOMAINS'])
SUBJECT = DOMAINS[0]
EMAIL_ADDRESS = os.environ['EMAIL_ADDRESS']
FUNCTION_NAME = os.environ['FUNCTION_NAME']
STAGING = os.environ['STAGING'] == '1'

Certificate = collections.namedtuple(
    typename='Certificate',
    field_names=(
        'Certificate',
        'CertificateArn',
        'CertificateChain',
        'NotAfter',
        'PrivateKey',
    ),
)

acm = boto3.client('acm')
ssm = boto3.client('ssm')


def find_latest_cert():
    """
    Find and return the latest active ACM certificate for this domain.

    """

    latest_cert_info = None
    latest_private_key = None

    # List valid certificates.
    paginator = acm.get_paginator('list_certificates')
    pages = paginator.paginate(CertificateStatuses=['ISSUED'])
    for page in pages:
        for cert_summary in page['CertificateSummaryList']:

            # Exclude certificates for a different domain.
            if cert_summary['DomainName'] != SUBJECT:
                continue

            cert_arn = cert_summary['CertificateArn']
            response = acm.describe_certificate(CertificateArn=cert_arn)
            cert_info = response['Certificate']

            # Exclude ACM certificates.
            if not cert_info.get('ImportedAt'):
                continue

            # Exclude older certificates.
            if latest_cert_info:
                if cert_info['ImportedAt'] <= latest_cert_info['ImportedAt']:
                    continue

            # Exclude certificates with different domains.
            cert_domains = set(cert_info['SubjectAlternativeNames'])
            expected_domains = set(DOMAINS)
            if cert_domains != expected_domains:
                continue

            # Exclude certificates with the wrong issuer. When using the
            # staging option, Certbot uses staging servers that create
            # certificates with "Fake" in the issuer value. Use that to
            # detect staging vs real certificates.
            cert_staging = 'fake' in cert_info['Issuer'].lower()
            if cert_staging != STAGING:
                continue

            # Get the associated private key from SSM.
            private_key = get_private_key(cert_arn)
            if not private_key:
                continue

            latest_cert_info = cert_info
            latest_private_key = private_key

    if not latest_cert_info:
        log('No ACM certificate found')
        return None

    cert_arn = latest_cert_info['CertificateArn']

    log('Found ACM certificate {}', cert_arn)

    # Get the actual certificate and chain.
    cert_data = acm.get_certificate(CertificateArn=cert_arn)

    return Certificate(
        Certificate=cert_data['Certificate'],
        CertificateArn=cert_arn,
        CertificateChain=cert_data['CertificateChain'],
        NotAfter=latest_cert_info['NotAfter'],
        PrivateKey=latest_private_key,
    )


def get_days_remaining(cert):
    """
    Returns the number of days left until an ACM certificate expires.

    """

    today = datetime.date.today()
    expire_date = datetime.date(
        cert.NotAfter.year,
        cert.NotAfter.month,
        cert.NotAfter.day,
    )
    days_remaining = (expire_date - today).days

    log(
        'Certificate has {} {} remaining',
        days_remaining,
        'day' if days_remaining == 1 else 'days',
    )

    return days_remaining


def get_private_key(cert_arn):
    """
    Checks if an ACM certificate has an associated private key
    stored in an SSM parameters, and returns the value.

    """

    param_name = get_ssm_param_name(cert_arn)

    try:
        response = ssm.get_parameter(
            Name=param_name,
            WithDecryption=True,
        )
    except ssm.exceptions.ParameterNotFound:
        return None
    else:
        return response['Parameter']['Value']


def get_ssm_param_name(cert_arn):
    """
    Returns the SSM parameter name to use for an ACM certificate's
    private key.

    """

    cert_id = cert_arn.split('/')[-1]

    return '/{}/{}/PrivateKey'.format(FUNCTION_NAME, cert_id)


def import_cert(cert_data):
    """
    Imports a certificate into ACM.

    """

    log('Importing certificate into ACM')

    response = acm.import_certificate(**cert_data)
    cert_arn = response['CertificateArn']

    log('Storing private key in SSM')

    param_name = get_ssm_param_name(cert_arn)
    param_desc = 'Private key for {}'.format(cert_arn)

    ssm.put_parameter(
        Name=param_name,
        Description=param_desc,
        Value=cert_data['PrivateKey'],
        Type='SecureString',
        Overwrite=True,
    )

    response = acm.describe_certificate(CertificateArn=cert_arn)
    not_after = response['Certificate']['NotAfter']

    return Certificate(
        Certificate=cert_data['Certificate'],
        CertificateArn=cert_arn,
        CertificateChain=cert_data['CertificateChain'],
        NotAfter=not_after,
        PrivateKey=cert_data['PrivateKey'],
    )


def log(message, *args, **kwargs):
    """
    Formats and logs a message to CloudWatch Logs.

    """

    if args or kwargs:
        message = message.format(*args, **kwargs)

    print(message)


def provision_cert():
    """
    Uses certbot to get a certificate from Let's Encrypt.

    """

    with tempfile.TemporaryDirectory() as temp_dir:


        log('Running certbot')

        lets_encrypt_dir = os.path.join(temp_dir, 'lets-encrypt')
        config_dir = os.path.join(lets_encrypt_dir, 'config')
        work_dir = os.path.join(lets_encrypt_dir, 'work')
        logs_dir = os.path.join(lets_encrypt_dir, 'logs')

        certbot_args = [
                'certonly',                             # Obtain a cert but don't install it
                '--noninteractive',                     # Run in non-interactive mode
                '--agree-tos',                          # Agree to the terms of service,
                '--email', EMAIL_ADDRESS,               # Email
                '--dns-route53',                        # Use dns challenge with route53
                '--domains', ','.join(DOMAINS),         # Domains to provision certs for
                '--config-dir', config_dir,             # Override directory paths so script doesn't have to be run as root
                '--work-dir', work_dir,
                '--logs-dir', logs_dir,
        ]
        if STAGING:
            certbot_args.append('--staging')
        
        certbot.main.main(certbot_args)

        cert_data = {}

        files = {
            'Certificate': 'cert.pem',
            'CertificateChain': 'fullchain.pem',
            'PrivateKey': 'privkey.pem',
        }
        for key, name in files.items():
            path = os.path.join(config_dir, 'live', SUBJECT, name)
            with open(path) as open_file:
                cert_data[key] = open_file.read()

        return cert_data


def lambda_handler(event, context):
    """
    Manages Let's Encrypt certificates in ACM.

    """

    cert = find_latest_cert()

    if not cert or get_days_remaining(cert) <= 30:
        cert_data = provision_cert()
        cert = import_cert(cert_data)

    return {
        'Certificate': cert.Certificate,
        'CertificateArn': cert.CertificateArn,
        'CertificateChain': cert.CertificateChain,
        'PrivateKey': cert.PrivateKey,
    }
