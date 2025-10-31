"""
Script to create OSS bucket for feedback image uploads.

Creates the 'financial-agent-feedback' bucket if it doesn't exist.
Reads credentials from environment variables.
"""

import os
import oss2
import sys

# OSS Configuration from environment
ACCESS_KEY_ID = os.getenv("OSS_ACCESS_KEY", "")
ACCESS_KEY_SECRET = os.getenv("OSS_SECRET_KEY", "")
ENDPOINT = os.getenv("OSS_ENDPOINT", "oss-cn-hangzhou.aliyuncs.com")
BUCKET_NAME = "financial-agent-feedback"

def main():
    # Validate credentials
    if not ACCESS_KEY_ID or not ACCESS_KEY_SECRET:
        print("❌ Error: OSS_ACCESS_KEY and OSS_SECRET_KEY environment variables required")
        print("   Set them in your environment or .env file")
        return 1

    # Initialize auth
    auth = oss2.Auth(ACCESS_KEY_ID, ACCESS_KEY_SECRET)

    # Create service to check/create buckets
    service = oss2.Service(auth, ENDPOINT)

    # Check if bucket exists
    print(f"Checking if bucket '{BUCKET_NAME}' exists...")

    try:
        # List all buckets
        buckets = [b.name for b in oss2.BucketIterator(service)]

        if BUCKET_NAME in buckets:
            print(f"✅ Bucket '{BUCKET_NAME}' already exists!")

            # Verify access
            bucket = oss2.Bucket(auth, ENDPOINT, BUCKET_NAME)
            bucket.get_bucket_info()
            print(f"✅ Successfully verified access to bucket")

        else:
            print(f"❌ Bucket '{BUCKET_NAME}' does not exist. Creating...")

            # Create bucket
            bucket = oss2.Bucket(auth, ENDPOINT, BUCKET_NAME)
            bucket.create_bucket(
                oss2.BUCKET_ACL_PRIVATE,  # Private access (default)
                oss2.models.BucketCreateConfig(
                    oss2.BUCKET_STORAGE_CLASS_STANDARD  # Standard storage class
                )
            )

            print(f"✅ Bucket '{BUCKET_NAME}' created successfully!")

            # Set CORS rules to allow browser uploads
            rule = oss2.models.CorsRule(
                allowed_origins=['*'],  # Allow all origins (restrict in production)
                allowed_methods=['GET', 'PUT', 'POST'],
                allowed_headers=['*'],
                max_age_seconds=3600
            )
            bucket.put_bucket_cors(oss2.models.BucketCors([rule]))
            print(f"✅ CORS rules configured for browser uploads")

        # Show bucket details
        bucket = oss2.Bucket(auth, ENDPOINT, BUCKET_NAME)
        info = bucket.get_bucket_info()

        print("\n📋 Bucket Information:")
        print(f"  Name: {info.name}")
        print(f"  Location: {info.location}")
        print(f"  Storage Class: {info.storage_class}")
        print(f"  ACL: {info.acl}")
        print(f"  Creation Date: {info.creation_date}")
        print(f"  Endpoint: https://{BUCKET_NAME}.{ENDPOINT}")

        return 0

    except oss2.exceptions.NoSuchBucket:
        print(f"❌ Bucket does not exist and couldn't be created")
        return 1
    except oss2.exceptions.AccessDenied:
        print(f"❌ Access denied. Check credentials.")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
