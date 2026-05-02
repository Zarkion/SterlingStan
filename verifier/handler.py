import json
import os

import boto3
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from shared.secrets import get_secret

lambda_client = boto3.client("lambda")


def handler(event, context):
    if event.get("source") == "sterlingstan.warmup":
        return {"statusCode": 200, "body": "warm"}

    signature = event["headers"].get("x-signature-ed25519", "")
    timestamp = event["headers"].get("x-signature-timestamp", "")
    body = event["body"] or ""

    try:
        verify_key = VerifyKey(bytes.fromhex(get_secret()["DISCORD_PUBLIC_KEY"]))
        verify_key.verify(f"{timestamp}{body}".encode(), bytes.fromhex(signature))
    except BadSignatureError:
        return {"statusCode": 401, "body": "invalid signature"}

    payload = json.loads(body)

    if payload.get("type") == 1:
        return {"statusCode": 200, "body": json.dumps({"type": 1})}

    lambda_client.invoke(
        FunctionName=os.environ["EXECUTOR_FUNCTION_NAME"],
        InvocationType="Event",
        Payload=json.dumps(payload).encode(),
    )
    return {"statusCode": 200, "body": json.dumps({"type": 5})}
