import os
import uuid
import boto3
import base64
import httpx
from datetime import datetime
from typing import Optional
from fastapi import HTTPException, UploadFile, status
from botocore.exceptions import ClientError, NoCredentialsError
from PIL import Image
import io

from app.config.env_config import env_config
from app.model.upload_model import (
    Upload, UploadUpdate, UploadModel, ImageStatus, ImageType,
    get_upload_model, create_upload_indexes
)
from app.imageprocessor.background_remover import background_remover

class UploadController:
    """Controller for handling image uploads to AWS S3 and database operations"""
    
    def __init__(self):
        self.s3_client = None
        self._initialize_s3_client()
    
    def _initialize_s3_client(self):
        """Initialize AWS S3 client with credentials from environment"""
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=env_config.AWS_ACCESS_KEY,
                aws_secret_access_key=env_config.AWS_SECRET_KEY,
                region_name=env_config.AWS_REGION
            )
            # Test connection
            self.s3_client.head_bucket(Bucket=env_config.AWS_BUCKET)
            print("AWS S3 client initialized successfully")
        except NoCredentialsError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AWS credentials not found"
            )
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"AWS S3 bucket '{env_config.AWS_BUCKET}' not found"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"AWS S3 connection error: {str(e)}"
                )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize AWS S3 client: {str(e)}"
            )

    async def _interrogate_image(self, image_data: bytes, interrogate_api_url: Optional[str] = None) -> Optional[str]:
        """
        Call the image interrogation API to generate a description using CLIP model
        
        Args:
            image_data: Raw image bytes
            interrogate_api_url: URL of the interrogation API endpoint
            
        Returns:
            Generated caption/description or None if failed
        """
        try:
            # Use configured URL if not provided
            print(f"Interrogate API URL: {interrogate_api_url}")
            if interrogate_api_url is None:
                interrogate_api_url = env_config.INTERROGATE_API_URL
                
            # Convert image data to base64
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            # Prepare the request payload
            payload = {
                "image": f"data:image/png;base64,{base64_image}",
                "model": "clip"
            }
            
            # Make the API call with timeout
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    interrogate_api_url,
                    json=payload,
                    headers={
                        'accept': 'application/json',
                        'Content-Type': 'application/json'
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    caption = result.get('caption', '').strip()
                    if caption:
                        print(f"Generated image caption: {caption}")
                        return caption
                    else:
                        print("Image interrogation returned empty caption")
                        return None
                else:
                    print(f"Image interrogation API failed with status {response.status_code}: {response.text}")
                    return None
                    
        except httpx.ConnectError:
            print("Could not connect to image interrogation API - service may be unavailable")
            return None
        except httpx.TimeoutException:
            print("Image interrogation API request timed out")
            return None
        except Exception as e:
            print(f"Error calling image interrogation API: {e}")
            return None

    def _validate_image_file(self, file: UploadFile) -> tuple:
        """Validate uploaded file and return image dimensions"""
        # Check file type
        allowed_types = [
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
            'image/webp', 'image/bmp', 'image/tiff'
        ]
        
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}"
            )
        
        # Check file size (10MB limit)
        max_size = 10 * 1024 * 1024  # 10MB
        if file.size and file.size > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds 10MB limit"
            )
        
        try:
            # Read image to get dimensions and validate
            image_data = file.file.read()
            file.file.seek(0)  # Reset file pointer
            
            with Image.open(io.BytesIO(image_data)) as img:
                width, height = img.size
                
            return width, height, len(image_data)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image file or corrupted image"
            )

    def _generate_file_path(self, user_id: str, original_filename: str, image_type: ImageType) -> tuple:
        """Generate unique file path and filename for S3 storage"""
        # Extract file extension
        file_extension = os.path.splitext(original_filename)[1].lower()
        if not file_extension:
            file_extension = '.jpg'  # Default extension
        
        # Generate unique filename
        unique_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        new_filename = f"{timestamp}_{unique_id}{file_extension}"
        
        # Create organized folder structure
        folder_path = f"uploads/{user_id}/{image_type.value}/{datetime.utcnow().year}/{datetime.utcnow().month:02d}"
        full_path = f"{folder_path}/{new_filename}"
        
        return full_path, new_filename

    async def upload_image_to_s3(self, file: UploadFile, user_id: str, 
                                image_type: ImageType = ImageType.GALLERY,
                                description: Optional[str] = None,
                                tags: Optional[list] = None,
                                is_public: bool = False) -> dict:
        """Upload image to S3 and save metadata to database"""
        
        try:
            # Validate image file
            width, height, file_size = self._validate_image_file(file)
            
            # Generate file path
            s3_path, new_filename = self._generate_file_path(user_id, file.filename, image_type)
            
            # Reset file pointer
            file.file.seek(0)
            
            # Upload to S3
            extra_args = {
                'ContentType': file.content_type,
                'Metadata': {
                    'original-filename': file.filename or 'unknown',
                    'user-id': user_id,
                    'upload-timestamp': datetime.utcnow().isoformat()
                }
            }
            
            # Set public read if image is public
            if is_public:
                extra_args['ACL'] = 'public-read'
            
            self.s3_client.upload_fileobj(
                file.file,
                env_config.AWS_BUCKET,
                s3_path,
                ExtraArgs=extra_args
            )
            
            # Generate S3 URL
            s3_url = f"https://{env_config.AWS_BUCKET}.s3.{env_config.AWS_REGION}.amazonaws.com/{s3_path}"
            
            # Create upload record in database
            upload_data = Upload(
                userId=user_id,
                originalName=file.filename or 'unknown',
                fileName=new_filename,
                filePath=s3_path,
                fileUrl=s3_url,
                mimeType=file.content_type,
                fileSize=file_size,
                width=width,
                height=height,
                imageType=image_type,
                status=ImageStatus.UPLOADED,
                description=description,
                tags=tags or [],
                isPublic=is_public,
                uploadedAt=datetime.utcnow(),
                updatedAt=datetime.utcnow()
            )
            
            # Save to database
            upload_collection = get_upload_model()
            result = await upload_collection.insert_one(upload_data.dict())
            
            if not result.inserted_id:
                # If DB save fails, try to delete from S3 (cleanup)
                try:
                    self.s3_client.delete_object(Bucket=env_config.AWS_BUCKET, Key=s3_path)
                except:
                    pass  # Ignore cleanup errors
                
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to save upload record to database"
                )
            
            # Return success response
            return {
                "success": True,
                "message": "Image uploaded successfully",
                "upload": {
                    "id": str(result.inserted_id),
                    "userId": user_id,
                    "originalName": file.filename,
                    "fileName": new_filename,
                    "fileUrl": s3_url,
                    "filePath": s3_path,
                    "mimeType": file.content_type,
                    "fileSize": file_size,
                    "width": width,
                    "height": height,
                    "imageType": image_type,
                    "status": ImageStatus.UPLOADED,
                    "description": description,
                    "tags": tags or [],
                    "isPublic": is_public,
                    "uploadedAt": upload_data.uploadedAt,
                    "updatedAt": upload_data.updatedAt
                }
            }
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except ClientError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AWS S3 upload error: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Upload failed: {str(e)}"
            )

    async def get_user_uploads(self, user_id: str, status: Optional[ImageStatus] = None,
                              image_type: Optional[ImageType] = None, 
                              limit: int = 50, skip: int = 0, url_expiration: int = 3600) -> dict:
        """Get uploads for a specific user with signed URLs"""
        try:
            from app.model.upload_model import get_user_uploads
            
            uploads = await get_user_uploads(user_id, status, image_type, limit, skip, url_expiration)
            
            # Convert ObjectId to string for JSON serialization
            for upload in uploads:
                upload['id'] = str(upload['_id'])
                del upload['_id']
            
            return {
                "success": True,
                "uploads": uploads,
                "count": len(uploads),
                "limit": limit,
                "skip": skip
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch uploads: {str(e)}"
            )

    async def delete_upload(self, upload_id: str, user_id: str) -> dict:
        """Delete an upload (both from S3 and database)"""
        try:
            from bson import ObjectId
            
            upload_collection = get_upload_model()
            
            # Find the upload
            upload = await upload_collection.find_one({
                "_id": ObjectId(upload_id),
                "userId": user_id,
                "deletedAt": None
            })
            
            if not upload:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Upload not found"
                )
            
            # Delete from S3
            try:
                self.s3_client.delete_object(
                    Bucket=env_config.AWS_BUCKET,
                    Key=upload['filePath']
                )
            except ClientError as e:
                print(f"Warning: Failed to delete from S3: {e}")
                # Continue with database deletion even if S3 deletion fails
            
            # Soft delete from database
            from app.model.upload_model import soft_delete_upload
            success = await soft_delete_upload(upload_id)
            
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to delete upload record"
                )
            
            return {
                "success": True,
                "message": "Upload deleted successfully",
                "uploadId": upload_id
            }
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete upload: {str(e)}"
            )

    async def upload_image_with_background_removal(self, file: UploadFile, user_id: str,
                                                  image_type: ImageType = ImageType.GALLERY,
                                                  description: Optional[str] = None,
                                                  tags: Optional[list] = None,
                                                  is_public: bool = False,
                                                  model_name: str = 'u2net',
                                                  apply_edge_smoothing: bool = True,
                                                  generate_ai_description: bool = True) -> dict:
        """Upload image with automatic background removal to S3 and save metadata to database"""
        
        try:
            # Validate image file first
            width, height, original_file_size = self._validate_image_file(file)
            
            # Reset file pointer and read image data
            file.file.seek(0)
            original_image_data = file.file.read()
            
            # Validate background removal model
            if not background_remover.validate_model(model_name):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid model. Available models: {background_remover.get_available_models()}"
                )
            
            # Remove background from image
            try:
                if apply_edge_smoothing:
                    processed_image_data, processing_metadata = background_remover.remove_background_with_edge_smoothing(
                        original_image_data, model_name
                    )
                else:
                    processed_image_data, processing_metadata = background_remover.remove_background(
                        original_image_data, model_name
                    )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Background removal failed: {str(e)}"
                )
            
            # Update file info with processed image
            processed_file_size = len(processed_image_data)
            processed_width, processed_height = processing_metadata['processed_dimensions']
            
            # Generate file path with _nobg suffix to indicate background removed
            original_filename = file.filename or 'unknown'
            name_without_ext = os.path.splitext(original_filename)[0]
            new_filename_base = f"{name_without_ext}_nobg"
            
            # Create a temporary file-like object for processed image
            processed_file_obj = io.BytesIO(processed_image_data)
            
            # Generate file path (PNG format for transparency support)
            folder_path = f"uploads/{user_id}/{image_type.value}/{datetime.utcnow().year}/{datetime.utcnow().month:02d}"
            unique_id = str(uuid.uuid4())
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            new_filename = f"{timestamp}_{unique_id}_nobg.png"
            s3_path = f"{folder_path}/{new_filename}"
            
            # Upload processed image to S3
            extra_args = {
                'ContentType': 'image/png',
                'Metadata': {
                    'original-filename': original_filename,
                    'user-id': user_id,
                    'upload-timestamp': datetime.utcnow().isoformat(),
                    'background-removed': 'true',
                    'model-used': model_name,
                    'edge-smoothing': str(apply_edge_smoothing),
                    'original-size': str(original_file_size),
                    'processed-size': str(processed_file_size)
                }
            }
            
            # Set public read if image is public
            if is_public:
                extra_args['ACL'] = 'public-read'
            
            self.s3_client.upload_fileobj(
                processed_file_obj,
                env_config.AWS_BUCKET,
                s3_path,
                ExtraArgs=extra_args
            )
            
            # Generate S3 URL
            s3_url = f"https://{env_config.AWS_BUCKET}.s3.{env_config.AWS_REGION}.amazonaws.com/{s3_path}"
            
            # Generate AI description if no description provided and AI generation is enabled
            ai_generated_description = None
            if generate_ai_description:
                try:
                    ai_generated_description = await self._interrogate_image(processed_image_data,'http://127.0.0.1:7860/sdapi/v1/interrogate')
                    if ai_generated_description:
                        description = ai_generated_description
                        print(f"Using AI-generated description: {description}")
                except Exception as e:
                    print(f"Failed to generate AI description: {e}")
            
            # Prepare metadata for database
            combined_metadata = {
                'background_removal': processing_metadata,
                'original_file_info': {
                    'size': original_file_size,
                    'dimensions': (width, height),
                    'format': file.content_type
                },
                'processing_applied': 'background_removal',
                'model_used': model_name,
                'edge_smoothing_applied': apply_edge_smoothing,
                'ai_description_generated': ai_generated_description is not None,
                'ai_description': ai_generated_description if ai_generated_description else None
            }
            
            # Create upload record in database
            upload_data = Upload(
                userId=user_id,
                originalName=original_filename,
                fileName=new_filename,
                filePath=s3_path,
                fileUrl=s3_url,
                mimeType='image/png',  # Always PNG for transparency
                fileSize=processed_file_size,
                width=processed_width,
                height=processed_height,
                imageType=image_type,
                status=ImageStatus.PROCESSED,  # Mark as processed since background was removed
                description=ai_generated_description,
                tags=tags or [],
                isPublic=is_public,
                metadata=combined_metadata,
                uploadedAt=datetime.utcnow(),
                updatedAt=datetime.utcnow()
            )
            
            # Save to database
            upload_collection = get_upload_model()
            result = await upload_collection.insert_one(upload_data.dict())
            
            if not result.inserted_id:
                # If DB save fails, try to delete from S3 (cleanup)
                try:
                    self.s3_client.delete_object(Bucket=env_config.AWS_BUCKET, Key=s3_path)
                except:
                    pass  # Ignore cleanup errors
                
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to save upload record to database"
                )
            
            # Return success response
            return {
                "success": True,
                "message": "Image uploaded successfully with background removed",
                "upload": {
                    "id": str(result.inserted_id),
                    "userId": user_id,
                    "originalName": original_filename,
                    "fileName": new_filename,
                    "fileUrl": s3_url,
                    "filePath": s3_path,
                    "mimeType": "image/png",
                    "fileSize": processed_file_size,
                    "width": processed_width,
                    "height": processed_height,
                    "imageType": image_type,
                    "status": ImageStatus.PROCESSED,
                    "description": ai_generated_description,
                    "tags": tags or [],
                    "isPublic": is_public,
                    "backgroundRemoved": True,
                    "processingMetadata": processing_metadata,
                    "uploadedAt": upload_data.uploadedAt,
                    "updatedAt": upload_data.updatedAt
                }
            }
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except ClientError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AWS S3 upload error: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Upload with background removal failed: {str(e)}"
            )

# Global controller instance
upload_controller = UploadController()
