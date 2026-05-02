import json
import os

import boto3

_secret_cache = None


def get_secret():
    global _secret_cache
    if not _secret_cache:
        client = boto3.client("secretsmanager")
        raw = client.get_secret_value(SecretId=os.environ["SECRET_NAME"])
        _secret_cache = json.loads(raw["SecretString"])
    return _secret_cache
