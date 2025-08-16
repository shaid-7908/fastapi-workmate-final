from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum
import boto3
from botocore.exceptions import ClientError
from app.config.db_config import db_manager
from app.config.env_config import env_config

# Enum for image status
class ImageStatus(str, Enum):
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    DELETED = "deleted"

# Enum for image types
class ImageType(str, Enum):
    PROFILE = "profile"
    GALLERY = "gallery"
    DOCUMENT = "document"
    THUMBNAIL = "thumbnail"

# Upload Pydantic model
class Upload(BaseModel):
    userId: str = Field(..., description="ID of the user who uploaded the image")
    originalName: str = Field(..., min_length=1, max_length=255, description="Original filename")
    fileName: str = Field(..., min_length=1, max_length=255, description="Stored filename")
    filePath: str = Field(..., description="File path on server")
    fileUrl: Optional[str] = Field(None, description="Public URL to access the image")
    mimeType: str = Field(..., description="MIME type of the image (e.g., image/jpeg)")
    fileSize: int = Field(..., gt=0, description="File size in bytes")
    width: Optional[int] = Field(None, gt=0, description="Image width in pixels")
    height: Optional[int] = Field(None, gt=0, description="Image height in pixels")
    imageType: ImageType = Field(default=ImageType.GALLERY, description="Type of image")
    status: ImageStatus = Field(default=ImageStatus.UPLOADING, description="Upload status")
    description: Optional[str] = Field(None, max_length=500, description="Image description")
    tags: Optional[List[str]] = Field(default=[], description="Image tags for categorization")
    isPublic: bool = Field(default=False, description="Whether image is publicly accessible")
    thumbnailPath: Optional[str] = Field(None, description="Path to thumbnail image")
    thumbnailUrl: Optional[str] = Field(None, description="URL to thumbnail image")
    metadata: Optional[dict] = Field(default={}, description="Additional metadata")
    uploadedAt: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Upload timestamp")
    updatedAt: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    deletedAt: Optional[datetime] = Field(None, description="Deletion timestamp")

    @validator('mimeType')
    def validate_mime_type(cls, v):
        """Validate that mime type is for images"""
        allowed_types = [
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 
            'image/webp', 'image/bmp', 'image/tiff', 'image/svg+xml'
        ]
        if v not in allowed_types:
            raise ValueError(f'Invalid mime type. Allowed types: {", ".join(allowed_types)}')
        return v

    @validator('tags')
    def validate_tags(cls, v):
        """Validate tags list"""
        if v and len(v) > 20:
            raise ValueError('Maximum 20 tags allowed')
        if v:
            for tag in v:
                if len(tag) > 50:
                    raise ValueError('Each tag must be 50 characters or less')
        return v

# Update model for partial updates
class UploadUpdate(BaseModel):
    description: Optional[str] = Field(None, max_length=500)
    tags: Optional[List[str]] = Field(None)
    isPublic: Optional[bool] = Field(None)
    status: Optional[ImageStatus] = Field(None)
    metadata: Optional[dict] = Field(None)
    updatedAt: Optional[datetime] = Field(default_factory=datetime.utcnow)

    @validator('tags')
    def validate_tags(cls, v):
        """Validate tags list"""
        if v and len(v) > 20:
            raise ValueError('Maximum 20 tags allowed')
        if v:
            for tag in v:
                if len(tag) > 50:
                    raise ValueError('Each tag must be 50 characters or less')
        return v

# Global variables for lazy initialization
_db = None
_upload_model = None

def get_upload_model():
    """Get UploadModel collection with lazy initialization"""
    global _db, _upload_model
    if _upload_model is None:
        _db = db_manager.get_database()
        _upload_model = _db["uploads"]
    return _upload_model

# For backward compatibility - this will be initialized when first accessed
class UploadModelProxy:
    def __getattr__(self, name):
        return getattr(get_upload_model(), name)
    
    def __getitem__(self, key):
        return get_upload_model()[key]

UploadModel = UploadModelProxy()

# Utility function to generate signed URLs
def generate_signed_url(file_path: str, expiration: int = 3600) -> str:
    """
    Generate a signed URL for an S3 object
    
    Args:
        file_path: The S3 object key (file path)
        expiration: Time in seconds for the URL to remain valid (default: 1 hour)
    
    Returns:
        Signed URL as string
    """
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=env_config.AWS_ACCESS_KEY,
            aws_secret_access_key=env_config.AWS_SECRET_KEY,
            region_name=env_config.AWS_REGION
        )
        
        # Generate the presigned URL
        signed_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': env_config.AWS_BUCKET, 'Key': file_path},
            ExpiresIn=expiration
        )
        
        return signed_url
    except ClientError as e:
        print(f"Error generating signed URL for {file_path}: {e}")
        # Return the original URL if signing fails
        return f"https://{env_config.AWS_BUCKET}.s3.{env_config.AWS_REGION}.amazonaws.com/{file_path}"
    except Exception as e:
        print(f"Unexpected error generating signed URL for {file_path}: {e}")
        # Return the original URL if signing fails
        return f"https://{env_config.AWS_BUCKET}.s3.{env_config.AWS_REGION}.amazonaws.com/{file_path}"

# Index creation function
async def create_upload_indexes():
    """Create all necessary indexes for uploads collection"""
    from pymongo import IndexModel, ASCENDING, DESCENDING
    
    indexes = [
        # Index for finding uploads by user
        IndexModel([("userId", ASCENDING)], name="userId_index"),
        
    ]
    
    try:
        upload_collection = get_upload_model()
        result = await upload_collection.create_indexes(indexes)
        # Convert result to list if it's not already
        if hasattr(result, '__iter__') and not isinstance(result, str):
            result_list = list(result)
        else:
            result_list = [result] if result is not None else []
        print(f"Upload indexes created: {result_list}")
        return result_list
    except Exception as e:
        print(f"Error creating upload indexes: {e}")
        return []

# Utility functions for common operations
async def get_user_uploads(user_id: str, status: Optional[ImageStatus] = None, 
                          image_type: Optional[ImageType] = None, limit: int = 50, skip: int = 0, 
                          url_expiration: int = 3600):
    """Get uploads for a specific user with optional filtering"""
    match_stage = {
        "userId": user_id,
        "deletedAt": None
    }

    if status:
        match_stage["status"] = status
    if image_type:
        match_stage["imageType"] = image_type

    # Aggregation pipeline
    pipeline = [
        {"$match": match_stage},                     # filter
        {"$sort": {"uploadedAt": -1}},              # sort by upload time desc
        {"$skip": skip},                            # skip N docs
        {"$limit": limit},
        {"$project": {
            "userId": 1,
            "originalName": 1,
            "fileName": 1,
            "filePath": 1,
            "fileUrl": 1,
            "thumbnailPath": 1,
            "thumbnailUrl": 1,
            "imageType": 1,
            "status": 1,
            "description": 1,
            "tags": 1,
            "isPublic": 1,
            "mimeType": 1,
            "fileSize": 1,
            "width": 1,
            "height": 1,
            "uploadedAt": 1,
            "updatedAt": 1
        }}                           # limit
    ]
    
    upload_collection = get_upload_model()
    cursor = upload_collection.aggregate(pipeline)
    uploads = await cursor.to_list(length=limit)
    
    # Generate signed URLs for each upload
    for upload in uploads:
        if upload.get('filePath'):
            upload['fileUrl'] = generate_signed_url(upload['filePath'], url_expiration)
        
        # Also generate signed URL for thumbnail if it exists
        if upload.get('thumbnailPath'):
            upload['thumbnailUrl'] = generate_signed_url(upload['thumbnailPath'], url_expiration)
    
    return uploads

async def get_public_uploads(limit: int = 50, skip: int = 0):
    """Get public uploads"""
    query = {"isPublic": True, "status": ImageStatus.PROCESSED, "deletedAt": None}
    
    upload_collection = get_upload_model()
    cursor = upload_collection.find(query).sort("uploadedAt", -1).skip(skip).limit(limit)
    return await cursor.to_list(length=limit)

async def soft_delete_upload(upload_id: str):
    """Soft delete an upload by setting deletedAt timestamp"""
    upload_collection = get_upload_model()
    result = await upload_collection.update_one(
        {"_id": upload_id},
        {"$set": {"deletedAt": datetime.utcnow(), "updatedAt": datetime.utcnow()}}
    )
    return result.modified_count > 0

async def search_uploads(user_id: str, search_text: str, limit: int = 50, skip: int = 0):
    """Search uploads by description and tags"""
    query = {
        "userId": user_id,
        "deletedAt": None,
        "$text": {"$search": search_text}
    }
    
    upload_collection = get_upload_model()
    cursor = upload_collection.find(query).sort("uploadedAt", -1).skip(skip).limit(limit)
    return await cursor.to_list(length=limit)
