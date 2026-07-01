import io
import uuid
from datetime import timedelta
from typing import Optional, BinaryIO
from minio import Minio
from minio.error import S3Error

from app.config import settings


class StorageService:
    def __init__(self):
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE
        )
        self.bucket = settings.MINIO_BUCKET
        self.public_endpoint = settings.MINIO_PUBLIC_ENDPOINT or settings.MINIO_ENDPOINT
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except S3Error as e:
            print(f"Error creating bucket: {e}")

    def _generate_filename(self, original_filename: str, prefix: str = "") -> str:
        ext = original_filename.rsplit(".", 1)[-1] if "." in original_filename else "bin"
        unique_id = uuid.uuid4().hex
        return f"{prefix}/{unique_id}.{ext}" if prefix else f"{unique_id}.{ext}"

    async def upload_file(
        self,
        file_data: BinaryIO,
        original_filename: str,
        content_type: str,
        prefix: str = ""
    ) -> str:
        """Upload a file and return the object name"""
        object_name = self._generate_filename(original_filename, prefix)
        file_data.seek(0, 2)
        file_size = file_data.tell()
        file_data.seek(0)

        self.client.put_object(
            self.bucket,
            object_name,
            file_data,
            file_size,
            content_type=content_type
        )
        return object_name

    async def upload_bytes(
        self,
        data: bytes,
        original_filename: str,
        content_type: str,
        prefix: str = ""
    ) -> str:
        """Upload bytes and return the object name"""
        object_name = self._generate_filename(original_filename, prefix)
        self.client.put_object(
            self.bucket,
            object_name,
            io.BytesIO(data),
            len(data),
            content_type=content_type
        )
        return object_name

    async def get_file(self, object_name: str) -> bytes:
        """Download file content"""
        response = None
        try:
            response = self.client.get_object(self.bucket, object_name)
            return response.read()
        finally:
            if response:
                response.close()
                response.release_conn()

    async def get_file_url(self, object_name: str, expires: int = 3600) -> str:
        """Get a presigned URL for the file (accessible from browser)"""
        # Generate URL using internal client (that can connect)
        url = self.client.presigned_get_object(
            self.bucket,
            object_name,
            expires=timedelta(seconds=expires)
        )
        # Replace internal endpoint with public endpoint for browser access
        if self.public_endpoint and self.public_endpoint != settings.MINIO_ENDPOINT:
            url = url.replace(settings.MINIO_ENDPOINT, self.public_endpoint)
        return url

    async def delete_file(self, object_name: str) -> bool:
        """Delete a file"""
        try:
            self.client.remove_object(self.bucket, object_name)
            return True
        except S3Error:
            return False

    async def list_files(self, prefix: str = "") -> list:
        """List files with a given prefix"""
        objects = self.client.list_objects(self.bucket, prefix=prefix)
        return [obj.object_name async for obj in objects]


storage_service = StorageService()
