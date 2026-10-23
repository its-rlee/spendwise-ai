"""S3-compatible private object storage (AWS or Supabase Storage).

S3 endpoint and credentials are backend-only environment variables.
"""
import os

import boto3
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()


def get_s3_client():
    endpoint = os.getenv("AWS_S3_ENDPOINT_URL") or None

    # Supabase Storage's S3 API requires path-style addressing and SigV4.
    # This is also compatible with AWS S3.
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=os.environ["AWS_REGION"],
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 2, "mode": "standard"},
        ),
    )
