import os
import asyncio
import boto3
from typing import Optional


class StorageService:
    def __init__(
        self,
        bucket: str = "klegally-documents",
        endpoint_url: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        region: str = "us-east-1",
    ):
        self.bucket = bucket
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region

        # Local fallback directory at the monorepo level
        self.local_dir = os.path.abspath(
            os.path.join(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    )
                ),
                "storage",
            )
        )
        os.makedirs(self.local_dir, exist_ok=True)

        self.s3_client = None
        if self.access_key and self.secret_key:
            try:
                self.s3_client = boto3.client(
                    "s3",
                    endpoint_url=self.endpoint_url,
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                    region_name=self.region,
                )
                print(f"[Storage] S3 Client initialized on bucket '{self.bucket}'.")
            except Exception as e:
                print(f"[Storage] Failed to initialize S3 client: {e}. Using local fallback.")
        else:
            print("[Storage] AWS credentials not fully configured. Using local fallback.")

    async def exists(self, storage_path: str) -> bool:
        """
        Checks if a file exists in S3/storage.
        Used to prevent extraction before PDF upload/ingestion is fully complete.
        """
        if storage_path.startswith("s3://"):
            s3_path = storage_path[5:]
            bucket_name, key = s3_path.split("/", 1)
            if self.s3_client:
                try:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None,
                        lambda: self.s3_client.head_object(
                            Bucket=bucket_name, Key=key
                        ),
                    )
                    return True
                except Exception:
                    return False
            return False

        # Local fallback existence check
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: os.path.exists(storage_path),
        )

    async def upload(self, file_content: bytes, filename: str, s3_key: str) -> str:
        if self.s3_client:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: self.s3_client.put_object(
                        Bucket=self.bucket,
                        Key=s3_key,
                        Body=file_content,
                    ),
                )
                print(f"[Storage] Uploaded {filename} to S3 at s3://{self.bucket}/{s3_key}")
                return f"s3://{self.bucket}/{s3_key}"
            except Exception as e:
                print(f"[Storage] S3 upload failed: {e}. Using local fallback.")

        # Local fallback
        local_path = os.path.join(self.local_dir, s3_key)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: open(local_path, "wb").write(file_content),
        )
        print(f"[Storage] Saved {filename} to local monorepo fallback path: {local_path}")
        return local_path

    async def download(self, storage_path: str) -> str:
        import tempfile
        import shutil

        temp_dir = tempfile.gettempdir()
        temp_file_name = os.path.basename(storage_path)
        temp_file_path = os.path.join(temp_dir, temp_file_name)

        if storage_path.startswith("s3://"):
            s3_path = storage_path[5:]
            bucket_name, key = s3_path.split("/", 1)
            if self.s3_client:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: self.s3_client.download_file(bucket_name, key, temp_file_path),
                )
                print(f"[Storage] Downloaded {storage_path} from S3 to {temp_file_path}")
                return temp_file_path
            else:
                raise ValueError("S3 client is not initialized.")

        # Local fallback
        if os.path.exists(storage_path):
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: shutil.copy2(storage_path, temp_file_path),
            )
            print(f"[Storage] Copied local storage file from {storage_path} to temporary path {temp_file_path}")
            return temp_file_path
        else:
            raise FileNotFoundError(f"Storage path {storage_path} not found.")
