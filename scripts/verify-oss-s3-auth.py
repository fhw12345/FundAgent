#!/usr/bin/env python3
"""
Verify Aliyun OSS S3-compatible API authentication.

This script tests:
1. Bucket access with S3-compatible API
2. Upload test file
3. Download test file
4. Delete test file
5. List bucket contents

Usage:
    python3 scripts/verify-oss-s3-auth.py
"""

import os
import sys
from datetime import datetime, timezone

try:
    import boto3
    from botocore.client import Config
    from botocore.exceptions import ClientError, BotoCoreError
except ImportError:
    print("ERROR: boto3 not installed. Install with: pip install boto3")
    sys.exit(1)


def main() -> None:
    """Test OSS S3-compatible API authentication."""
    # Configuration
    endpoint = os.getenv(
        "OSS_ENDPOINT", "https://oss-cn-hangzhou.aliyuncs.com"
    )  # NO s3. prefix!
    bucket_name = os.getenv("OSS_BUCKET", "langfuse-events-prod")
    region = os.getenv("OSS_REGION", "cn-hangzhou")
    access_key_id = os.getenv("OSS_ACCESS_KEY_ID")
    secret_access_key = os.getenv("OSS_SECRET_ACCESS_KEY")

    if not access_key_id or not secret_access_key:
        print("ERROR: OSS_ACCESS_KEY_ID and OSS_SECRET_ACCESS_KEY must be set")
        print("\nUsage:")
        print("  export OSS_ACCESS_KEY_ID='your-access-key-id'")
        print("  export OSS_SECRET_ACCESS_KEY='your-secret-access-key'")
        print("  python3 scripts/verify-oss-s3-auth.py")
        sys.exit(1)

    print("=" * 80)
    print("OSS S3-Compatible API Authentication Verification")
    print("=" * 80)
    print(f"Endpoint:   {endpoint}")
    print(f"Bucket:     {bucket_name}")
    print(f"Region:     {region}")
    print(f"Access Key: {access_key_id[:10]}..." if access_key_id else "Not set")
    print("=" * 80)
    print()

    # Create S3 client
    try:
        print("[1/5] Creating S3 client...")
        s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            use_ssl=True,
            config=Config(
                signature_version="s3v4",
                s3={
                    "addressing_style": "virtual",  # Virtual-hosted style
                    "payload_signing_enabled": True,  # Enable payload signing (required by OSS)
                },
                # Disable retries to avoid chunked encoding
                retries={"max_attempts": 1, "mode": "standard"},
            ),
        )
        print("✅ S3 client created successfully")
        print()
    except (ClientError, BotoCoreError) as e:
        print(f"❌ Failed to create S3 client: {e}")
        sys.exit(1)

    # Test 1: List buckets
    try:
        print("[2/5] Listing buckets...")
        response = s3_client.list_buckets()
        buckets = [b["Name"] for b in response.get("Buckets", [])]
        print(f"✅ Found {len(buckets)} bucket(s): {', '.join(buckets)}")
        print()
    except ClientError as e:
        print(f"❌ Failed to list buckets: {e}")
        print(f"   Error code: {e.response.get('Error', {}).get('Code', 'Unknown')}")
        print(f"   Error message: {e.response.get('Error', {}).get('Message', 'Unknown')}")
        sys.exit(1)

    # Test 2: Upload test file
    now = datetime.now(timezone.utc)
    test_key = f"test-verification/{now.isoformat()}.txt"
    test_content = f"OSS S3 API verification test at {now.isoformat()}"

    try:
        print(f"[3/5] Uploading test file to s3://{bucket_name}/{test_key}...")
        body_bytes = test_content.encode("utf-8")
        s3_client.put_object(
            Bucket=bucket_name,
            Key=test_key,
            Body=body_bytes,
            ContentType="text/plain",
            ContentLength=len(body_bytes),  # Explicitly set content length
        )
        print("✅ Upload successful")
        print()
    except ClientError as e:
        print(f"❌ Failed to upload: {e}")
        print(f"   Error code: {e.response.get('Error', {}).get('Code', 'Unknown')}")
        print(f"   Error message: {e.response.get('Error', {}).get('Message', 'Unknown')}")
        sys.exit(1)

    # Test 3: Download test file
    try:
        print(f"[4/5] Downloading test file from s3://{bucket_name}/{test_key}...")
        response = s3_client.get_object(Bucket=bucket_name, Key=test_key)
        downloaded_content = response["Body"].read().decode("utf-8")

        if downloaded_content == test_content:
            print("✅ Download successful, content matches")
        else:
            print("❌ Download successful but content mismatch!")
            print(f"   Expected: {test_content}")
            print(f"   Got: {downloaded_content}")
            sys.exit(1)
        print()
    except ClientError as e:
        print(f"❌ Failed to download: {e}")
        print(f"   Error code: {e.response.get('Error', {}).get('Code', 'Unknown')}")
        sys.exit(1)

    # Test 4: Delete test file
    try:
        print(f"[5/5] Deleting test file s3://{bucket_name}/{test_key}...")
        s3_client.delete_object(Bucket=bucket_name, Key=test_key)
        print("✅ Delete successful")
        print()
    except ClientError as e:
        print(f"❌ Failed to delete: {e}")
        print(f"   Error code: {e.response.get('Error', {}).get('Code', 'Unknown')}")
        sys.exit(1)

    # Summary
    print("=" * 80)
    print("✅ ALL TESTS PASSED!")
    print("=" * 80)
    print()
    print("OSS S3-compatible API authentication is working correctly.")
    print("You can now use these credentials with Langfuse:")
    print()
    print(f"  LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT={endpoint}")
    print(f"  LANGFUSE_S3_EVENT_UPLOAD_BUCKET={bucket_name}")
    print(f"  LANGFUSE_S3_EVENT_UPLOAD_REGION={region}")
    print(f"  LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE=false")
    print(f"  AWS_ACCESS_KEY_ID={access_key_id}")
    print("  AWS_SECRET_ACCESS_KEY=<your-secret>")
    print()


if __name__ == "__main__":
    main()
