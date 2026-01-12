import boto3
import os
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class S3Client:
    """Utility for S3 operations."""
    
    def __init__(self):
        self.bucket = os.getenv("S3_BUCKET", "housing-regression-data-ajayr")
        self.region = os.getenv("AWS_REGION", "us-east-2")
        self.s3 = boto3.client("s3", region_name=self.region)
        logger.info(f"S3Client initialized: bucket={self.bucket}, region={self.region}")
    
    def download(self, key: str, local_path: str) -> None:
        """
        Download file from S3, creating directories if needed.
        
        Args:
            key: S3 object key (path)
            local_path: Local file path to save to
        
        Raises:
            Exception: If download fails
        """
        local_path = Path(local_path)
        if not local_path.exists():
            local_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Downloading s3://{self.bucket}/{key} → {local_path}")
            self.s3.download_file(self.bucket, key, str(local_path))
            logger.info(f"Download complete: {local_path}")
        else:
            logger.info(f"File already exists locally: {local_path}")
    
    def upload(self, local_path: str, key: str) -> None:
        """
        Upload file to S3.
        
        Args:
            local_path: Local file path
            key: S3 object key (destination path)
        
        Raises:
            Exception: If upload fails
        """
        logger.info(f"Uploading {local_path} → s3://{self.bucket}/{key}")
        self.s3.upload_file(local_path, self.bucket, key)
        logger.info(f"Upload complete: s3://{self.bucket}/{key}")
    
    def exists(self, key: str) -> bool:
        """
        Check if S3 object exists.
        
        Args:
            key: S3 object key
        
        Returns:
            True if object exists, False otherwise
        """
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception as e:
            logger.debug(f"Object not found: s3://{self.bucket}/{key}")
            return False
    
    def list_objects(self, prefix: str) -> list:
        """
        List objects in S3 with given prefix.
        
        Args:
            prefix: S3 prefix to filter by
        
        Returns:
            List of object keys
        """
        try:
            response = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
            if "Contents" in response:
                return [obj["Key"] for obj in response["Contents"]]
            return []
        except Exception as e:
            logger.error(f"Error listing objects with prefix {prefix}: {str(e)}")
            return []
