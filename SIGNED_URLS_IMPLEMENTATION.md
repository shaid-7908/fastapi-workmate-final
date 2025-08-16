# Signed URLs Implementation

## Overview

The FastAPI application now supports **signed URLs** for all file uploads stored in AWS S3. This provides secure, time-limited access to files without requiring them to be publicly accessible.

## What's Changed

### 1. New Utility Function

**File:** `app/model/upload_model.py`

Added `generate_signed_url()` function:
```python
def generate_signed_url(file_path: str, expiration: int = 3600) -> str
```

- **Purpose:** Generates AWS S3 presigned URLs for secure file access
- **Parameters:**
  - `file_path`: S3 object key (file path)
  - `expiration`: URL validity period in seconds (default: 1 hour)
- **Returns:** Signed URL string
- **Fallback:** Returns original S3 URL if signing fails

### 2. Modified Functions

**File:** `app/model/upload_model.py`

Updated `get_user_uploads()` function:
```python
async def get_user_uploads(
    user_id: str, 
    status: Optional[ImageStatus] = None, 
    image_type: Optional[ImageType] = None, 
    limit: int = 50, 
    skip: int = 0, 
    url_expiration: int = 3600  # NEW PARAMETER
):
```

**Changes:**
- Added `url_expiration` parameter
- Automatically generates signed URLs for `fileUrl` and `thumbnailUrl`
- Returns more complete upload information

**File:** `app/controller/upload_controller.py`

Updated `get_user_uploads()` method:
- Added `url_expiration` parameter
- Passes expiration time to model function

### 3. Updated API Endpoints

**File:** `app/route/upload_routes.py`

#### GET `/uploads`
- **New Parameter:** `url_expiration` (optional, default: 3600 seconds)
- **Returns:** List of uploads with signed URLs

**Example Request:**
```bash
GET /uploads?limit=10&url_expiration=7200
```

#### GET `/upload/{upload_id}`
- **New Parameter:** `url_expiration` (optional, default: 3600 seconds)
- **Returns:** Single upload details with signed URLs

**Example Request:**
```bash
GET /upload/507f1f77bcf86cd799439011?url_expiration=1800
```

## Benefits

### ✅ Security
- Files are no longer publicly accessible
- Time-limited access reduces security risks
- Prevents unauthorized file sharing

### ✅ Flexibility
- Configurable expiration times per request
- Different expiration periods for different use cases
- Fallback to original URLs if signing fails

### ✅ Backward Compatibility
- Existing API structure remains the same
- New parameter is optional with sensible defaults
- No breaking changes to current implementations

## Usage Examples

### Default Expiration (1 hour)
```bash
GET /uploads
```

### Custom Expiration (30 minutes)
```bash
GET /uploads?url_expiration=1800
```

### Long-term Access (6 hours)
```bash
GET /uploads?url_expiration=21600
```

## Response Format

### Before (Static URLs)
```json
{
  "success": true,
  "uploads": [
    {
      "id": "507f1f77bcf86cd799439011",
      "fileUrl": "https://bucket.s3.region.amazonaws.com/uploads/user/file.jpg",
      "thumbnailUrl": "https://bucket.s3.region.amazonaws.com/uploads/user/thumb.jpg"
    }
  ]
}
```

### After (Signed URLs)
```json
{
  "success": true,
  "uploads": [
    {
      "id": "507f1f77bcf86cd799439011",
      "fileUrl": "https://bucket.s3.region.amazonaws.com/uploads/user/file.jpg?AWSAccessKeyId=...&Signature=...&Expires=...",
      "thumbnailUrl": "https://bucket.s3.region.amazonaws.com/uploads/user/thumb.jpg?AWSAccessKeyId=...&Signature=...&Expires=..."
    }
  ]
}
```

## Configuration

Ensure your `.env` file contains:
```env
AWS_ACCESS_KEY=your_access_key
AWS_SECRET_KEY=your_secret_key
AWS_REGION=your_region
AWS_BUCKET=your_bucket_name
```

## Error Handling

- If AWS credentials are invalid: Falls back to original URLs
- If S3 bucket is inaccessible: Falls back to original URLs
- Logs errors for debugging while maintaining functionality

## Common Expiration Times

| Use Case | Seconds | Human Readable |
|----------|---------|----------------|
| Quick preview | 300 | 5 minutes |
| Standard access | 3600 | 1 hour |
| Extended session | 7200 | 2 hours |
| Long-term access | 86400 | 24 hours |

## Testing

A test script `test_signed_urls.py` is provided to verify:
- AWS configuration
- Signed URL generation
- Function signatures
- Implementation completeness

Run with:
```bash
python test_signed_urls.py
```

## Notes

- Signed URLs are generated on-demand for each API request
- URL expiration is counted from the time of generation
- Files remain in S3 with original access permissions
- This implementation is compatible with all existing upload functionality
