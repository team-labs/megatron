#!/bin/bash
#This is simple bash script that is used pull down and decrypt environment variables for Django

EC2_AVAIL_ZONE=`curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone`
EC2_REGION="`echo \"$EC2_AVAIL_ZONE\" | sed -e 's:\([0-9][0-9]*\)[a-z]*\$:\\1:'`"

export PYTHONUNBUFFERED=1

export HOSTNAME=`aws ssm get-parameters --names django.hostname --no-with-decryption --region $EC2_REGION | python3 -c "import sys, json; print(json.load(sys.stdin)['Parameters'][0]['Value'])"`
export REDIS_URL=`aws ssm get-parameters --names django.redis-url --with-decryption --region $EC2_REGION | python3 -c "import sys, json; print(json.load(sys.stdin)['Parameters'][0]['Value'])"`
export DATABASE_URL=`aws ssm get-parameters --names megatron.database-url --with-decryption --region $EC2_REGION | python3 -c "import sys, json; print(json.load(sys.stdin)['Parameters'][0]['Value'])"`
export DJANGO_PORT=`aws ssm get-parameters --names megatron.django-port --with-decryption --region $EC2_REGION | python3 -c "import sys, json; print(json.load(sys.stdin)['Parameters'][0]['Value'])"`
export FRONT_TOKEN=`aws ssm get-parameters --names megatron.front-token --with-decryption --region $EC2_REGION | python3 -c "import sys, json; print(json.load(sys.stdin)['Parameters'][0]['Value'])"`
export CHANNEL_PREFIX=`aws ssm get-parameters --names megatron.channel-prefix --no-with-decryption --region $EC2_REGION | python3 -c "import sys, json; print(json.load(sys.stdin)['Parameters'][0]['Value'])"`
export MEGATRON_VERIFICATION_TOKEN=`aws ssm get-parameters --names megatron.verification-token --with-decryption --region $EC2_REGION | python3 -c "import sys, json; print(json.load(sys.stdin)['Parameters'][0]['Value'])"`
export MEGATRON_APP_MODE=`aws ssm get-parameters --names megatron.megatron-app-mode --no-with-decryption --region $EC2_REGION | python3 -c "import sys, json; print(json.load(sys.stdin)['Parameters'][0]['Value'])"`

export S3_AWS_ACCESS_KEY_ID=`aws ssm get-parameters --names django.aws-access-key-id --with-decryption --region $EC2_REGION | python3 -c "import sys, json; print(json.load(sys.stdin)['Parameters'][0]['Value'])"`
export S3_AWS_SECRET_ACCESS_KEY=`aws ssm get-parameters --names django.aws-secret-access-key --with-decryption --region $EC2_REGION | python3 -c "import sys, json; print(json.load(sys.stdin)['Parameters'][0]['Value'])"`
export AWS_S3_BUCKET=`aws ssm get-parameters --names django.aws-s3-bucket --no-with-decryption --region $EC2_REGION | python3 -c "import sys, json; print(json.load(sys.stdin)['Parameters'][0]['Value'])"`
