from enum import Enum, auto
import logging
import uuid
from typing import Optional
import json

import boto3
import botocore
from botocore.client import Config
from django.conf import settings
from social_core.utils import slugify


LOGGER = logging.getLogger(__name__)


class S3Folders(Enum):
    TEMP = auto()


S3FoldersNames = {
    S3Folders.TEMP: 'temp'
}


def upload_to_s3(data, file_name, folder: S3Folders = S3Folders.TEMP) -> bool:
    """
    Uploads a file to S3 at a given folder path
    """
    key = S3FoldersNames[folder] + '/' + file_name

    s3 = boto3.resource('s3', aws_access_key_id=settings.AWS_ACCESS_KEY,
                        aws_secret_access_key=settings.AWS_SECRET_KEY,
                        region_name='us-east-2',
                        config=Config(signature_version='s3v4'))

    try:
        s3.Bucket(settings.AWS_S3_BUCKET).put_object(Key=key, Body=data)
    except botocore.exceptions.ClientError:
        LOGGER.exception("Error uploading files to s3")
        return False

    return True


def generate_presigned_url(file_name, folder: S3Folders = S3Folders.TEMP) -> str:
    """
    Generates a download link for a file stored in S3
    """
    key = S3FoldersNames[folder] + '/' + file_name

    s3 = boto3.client('s3', aws_access_key_id=settings.AWS_ACCESS_KEY,
                      aws_secret_access_key=settings.AWS_SECRET_KEY,
                      region_name='us-east-2',
                      config=Config(signature_version='s3v4'))

    url = s3.generate_presigned_url(
        ClientMethod='get_object',
        Params={
            'Bucket': settings.AWS_S3_BUCKET,
            'Key': key
        }
    )

    return url


def upload_temp_image(image: bytes, extension: str) -> Optional[str]:
    key = slugify(f'{uuid.uuid4()}') + extension
    success = upload_to_s3(image, key, S3Folders.TEMP)

    if not success:
        LOGGER.error(f'Error uploading the image to S3 with key: {key}')
        return None
    return key
