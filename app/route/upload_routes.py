from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from app.controller.upload_controller import upload_controller
from app.model.upload_model import ImageType, ImageStatus
from app.imageprocessor.background_remover import background_remover

# Create router
router = APIRouter()

# Static user ID as requested
STATIC_USER_ID = "689ee6ecd47c80ffc5530c26"

# Response models
class UploadResponse(BaseModel):
    id: str
    userId: str
    originalName: str
    fileName: str
    fileUrl: str
    filePath: str
    mimeType: str
    fileSize: int
    width: int
    height: int
    imageType: str
    status: str
    description: Optional[str] = None
    tags: List[str] = []
    isPublic: bool
    uploadedAt: datetime
    updatedAt: datetime

class UploadSuccessResponse(BaseModel):
    success: bool
    message: str
    upload: UploadResponse

class UploadsListResponse(BaseModel):
    success: bool
    uploads: List[dict]
    count: int
    limit: int
    skip: int

class DeleteResponse(BaseModel):
    success: bool
    message: str
    uploadId: str

# Routes
@router.post(
    "/upload",
    response_model=UploadSuccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload image to AWS S3",
    description="Upload an image file to AWS S3 and store metadata in database"
)
async def upload_image(
    file: UploadFile = File(..., description="Image file to upload"),
    image_type: ImageType = Form(default=ImageType.GALLERY, description="Type of image"),
    description: Optional[str] = Form(None, description="Image description"),
    tags: Optional[str] = Form(None, description="Comma-separated tags"),
    is_public: bool = Form(default=False, description="Make image publicly accessible")
):
    """
    Upload an image to AWS S3 and store metadata in database
    
    - **file**: Image file to upload (required)
    - **image_type**: Type of image - gallery, profile, document, thumbnail (optional, defaults to gallery)
    - **description**: Description of the image (optional)
    - **tags**: Comma-separated list of tags (optional)
    - **is_public**: Whether the image should be publicly accessible (optional, defaults to false)
    
    Returns the upload details including S3 URL and database information.
    """
    try:
        # Parse tags if provided
        tags_list = []
        if tags:
            tags_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
        
        # Upload image using controller
        result = await upload_controller.upload_image_to_s3(
            file=file,
            user_id=STATIC_USER_ID,
            image_type=image_type,
            description=description,
            tags=tags_list,
            is_public=is_public
        )
        
        return result
        
    except HTTPException:
        # Re-raise HTTP exceptions from controller
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )

@router.post(
    "/upload-remove-bg",
    response_model=UploadSuccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload image with automatic background removal to AWS S3",
    description="Upload an image file, automatically remove background, and store to AWS S3"
)
async def upload_image_with_background_removal(
    file: UploadFile = File(..., description="Image file to upload"),
    image_type: ImageType = Form(default=ImageType.GALLERY, description="Type of image"),
    description: Optional[str] = Form(None, description="Image description"),
    tags: Optional[str] = Form(None, description="Comma-separated tags"),
    is_public: bool = Form(default=False, description="Make image publicly accessible"),
    model: str = Form(default="u2net", description="Background removal model to use"),
    edge_smoothing: bool = Form(default=True, description="Apply edge smoothing for better quality"),
    generate_ai_description: bool = Form(default=True, description="Generate AI description if no description provided")
):
    """
    Upload an image with automatic background removal to AWS S3
    
    - **file**: Image file to upload (required)
    - **image_type**: Type of image - gallery, profile, document, thumbnail (optional, defaults to gallery)
    - **description**: Description of the image (optional)
    - **tags**: Comma-separated list of tags (optional)
    - **is_public**: Whether the image should be publicly accessible (optional, defaults to false)
    - **model**: Background removal model - u2net, u2netp, silueta, isnet-general-use (optional, defaults to u2net)
    - **edge_smoothing**: Apply edge smoothing for better quality (optional, defaults to true)
    - **generate_ai_description**: Generate AI description using CLIP model if no description provided (optional, defaults to true)
    
    The image will have its background automatically removed before being stored to S3.
    If no description is provided and generate_ai_description is true, an AI-generated description will be created.
    Returns the upload details including S3 URL and processing metadata.
    """
    try:
        # Validate model
        if not background_remover.validate_model(model):
            available_models = background_remover.get_available_models()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid model '{model}'. Available models: {', '.join(available_models)}"
            )
        
        # Parse tags if provided
        tags_list = []
        if tags:
            tags_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
        
        # Upload image with background removal using controller
        result = await upload_controller.upload_image_with_background_removal(
            file=file,
            user_id=STATIC_USER_ID,
            image_type=image_type,
            description=description,
            tags=tags_list,
            is_public=is_public,
            model_name=model,
            apply_edge_smoothing=edge_smoothing,
            generate_ai_description=generate_ai_description
        )
        
        return result
        
    except HTTPException:
        # Re-raise HTTP exceptions from controller
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload with background removal failed: {str(e)}"
        )

@router.get(
    "/uploads",
    response_model=UploadsListResponse,
    summary="Get user uploads",
    description="Get list of uploads for the static user with signed URLs"
)
async def get_uploads(
    status_filter: Optional[ImageStatus] = None,
    image_type: Optional[ImageType] = None,
    limit: int = 50,
    skip: int = 0,
    url_expiration: int = 3600
):
    """
    Get uploads for the static user with signed URLs
    
    - **status_filter**: Filter by upload status (optional)
    - **image_type**: Filter by image type (optional)
    - **limit**: Maximum number of uploads to return (optional, defaults to 50)
    - **skip**: Number of uploads to skip for pagination (optional, defaults to 0)
    - **url_expiration**: URL expiration time in seconds (optional, defaults to 3600 - 1 hour)
    
    Returns list of user uploads with signed URLs for secure access.
    """
    try:
        result = await upload_controller.get_user_uploads(
            user_id=STATIC_USER_ID,
            status=status_filter,
            image_type=image_type,
            limit=limit,
            skip=skip,
            url_expiration=url_expiration
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch uploads: {str(e)}"
        )

@router.delete(
    "/upload/{upload_id}",
    response_model=DeleteResponse,
    summary="Delete an upload",
    description="Delete an uploaded image from S3 and database"
)
async def delete_upload(upload_id: str):
    """
    Delete an uploaded image
    
    - **upload_id**: ID of the upload to delete
    
    Removes the image from both AWS S3 and the database.
    """
    try:
        result = await upload_controller.delete_upload(
            upload_id=upload_id,
            user_id=STATIC_USER_ID
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete upload: {str(e)}"
        )

@router.get(
    "/upload/{upload_id}",
    summary="Get upload details",
    description="Get details of a specific upload with signed URL"
)
async def get_upload_details(upload_id: str, url_expiration: int = 3600):
    """
    Get details of a specific upload with signed URL
    
    - **upload_id**: ID of the upload to retrieve
    - **url_expiration**: URL expiration time in seconds (optional, defaults to 3600 - 1 hour)
    
    Returns detailed information about the upload with signed URLs for secure access.
    """
    try:
        from bson import ObjectId
        from app.model.upload_model import get_upload_model
        
        upload_collection = get_upload_model()
        upload = await upload_collection.find_one({
            "_id": ObjectId(upload_id),
            "userId": STATIC_USER_ID,
            "deletedAt": None
        })
        
        if not upload:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Upload not found"
            )
        
        # Convert ObjectId to string
        upload['id'] = str(upload['_id'])
        del upload['_id']
        
        # Generate signed URLs
        from app.model.upload_model import generate_signed_url
        if upload.get('filePath'):
            upload['fileUrl'] = generate_signed_url(upload['filePath'], url_expiration)
        if upload.get('thumbnailPath'):
            upload['thumbnailUrl'] = generate_signed_url(upload['thumbnailPath'], url_expiration)
        
        return {
            "success": True,
            "upload": upload
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch upload details: {str(e)}"
        )

@router.get(
    "/bg-removal-models",
    summary="Get available background removal models",
    description="Get list of available background removal models"
)
async def get_background_removal_models():
    """
    Get available background removal models
    
    Returns a list of available models for background removal with descriptions.
    """
    try:
        models = background_remover.get_available_models()
        
        model_descriptions = {
            'u2net': 'General purpose model with good quality (recommended)',
            'u2netp': 'Lighter version of u2net, faster processing',
            'silueta': 'Optimized for people and portraits',
            'isnet-general-use': 'High accuracy general use model'
        }
        
        model_info = []
        for model in models:
            model_info.append({
                'name': model,
                'description': model_descriptions.get(model, 'Background removal model')
            })
        
        return {
            "success": True,
            "models": model_info,
            "default_model": "u2net",
            "total_models": len(models)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get background removal models: {str(e)}"
        )

# Health check for upload routes
@router.get(
    "/health",
    summary="Upload routes health check",
    description="Check if upload routes and AWS S3 connection are working"
)
async def upload_routes_health():
    """Health check endpoint for upload routes"""
    try:
        # Test AWS S3 connection
        from app.config.env_config import env_config
        import boto3
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=env_config.AWS_ACCESS_KEY,
            aws_secret_access_key=env_config.AWS_SECRET_KEY,
            region_name=env_config.AWS_REGION
        )
        
        # Test bucket access
        s3_client.head_bucket(Bucket=env_config.AWS_BUCKET)
        
        # Test background remover
        available_models = background_remover.get_available_models()
        
        return {
            "status": "healthy",
            "service": "upload_routes",
            "message": "Upload routes and AWS S3 connection are working properly",
            "aws_region": env_config.AWS_REGION,
            "aws_bucket": env_config.AWS_BUCKET,
            "static_user_id": STATIC_USER_ID,
            "background_removal": {
                "available": True,
                "models_count": len(available_models),
                "default_model": "u2net"
            }
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "upload_routes",
            "message": f"AWS S3 connection error: {str(e)}",
            "static_user_id": STATIC_USER_ID
        }
