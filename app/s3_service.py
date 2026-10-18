
import os

import boto3
from dotenv import load_dotenv

load_dotenv()


def get_s3_client():
    return boto3.client(
        "s3",
        region_name=os.environ["AWS_REGION"],
    )
