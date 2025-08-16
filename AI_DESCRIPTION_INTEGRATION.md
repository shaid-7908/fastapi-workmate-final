# AI Description Integration

## Overview

The `upload_image_with_background_removal` endpoint now automatically generates AI-powered descriptions using a CLIP model when no description is provided by the user.

## What's Changed

### 1. New Dependencies
- **httpx**: Added for making HTTP requests to the interrogation API
- **base64**: For encoding image data

### 2. New Configuration
- **INTERROGATE_API_URL**: Configurable URL for the image interrogation service
  - Default: `http://127.0.0.1:7860/sdapi/v1/interrogate`
  - Can be overridden via environment variable

### 3. Enhanced Upload Function

**File:** `app/controller/upload_controller.py`

#### New Method: `_interrogate_image()`
```python
async def _interrogate_image(self, image_data: bytes, interrogate_api_url: Optional[str] = None) -> Optional[str]
```

**Features:**
- Converts image to base64 format
- Calls CLIP model API for image description
- Handles connection errors gracefully
- Returns `None` if API is unavailable
- 30-second timeout for API calls

#### Enhanced Method: `upload_image_with_background_removal()`
**New Parameter:**
- `generate_ai_description: bool = True` - Enable/disable AI description generation

**Logic:**
1. Upload image to S3 with background removal
2. If no description provided AND `generate_ai_description=True`:
   - Call CLIP model API with processed image
   - Use generated caption as description
   - Add AI metadata to upload record

### 4. Updated API Endpoint

**Endpoint:** `POST /upload-remove-bg`

**New Parameter:**
- `generate_ai_description`: Boolean (optional, default: true)

## Usage Examples

### Default Behavior (AI Description Enabled)
```bash
curl -X POST "http://localhost:8000/upload-remove-bg" \
  -F "file=@image.jpg" \
  -F "image_type=gallery" \
  -F "model=u2net"
```

### Disable AI Description Generation
```bash
curl -X POST "http://localhost:8000/upload-remove-bg" \
  -F "file=@image.jpg" \
  -F "image_type=gallery" \
  -F "model=u2net" \
  -F "generate_ai_description=false"
```

### With Custom Description (AI Won't Override)
```bash
curl -X POST "http://localhost:8000/upload-remove-bg" \
  -F "file=@image.jpg" \
  -F "description=My custom description" \
  -F "image_type=gallery" \
  -F "model=u2net"
```

## API Integration Details

### Request Format
The system calls the interrogation API with:
```json
{
  "image": "data:image/png;base64,iVBORw0KGgw3...",
  "model": "clip"
}
```

### Expected Response
```json
{
  "caption": "A beautiful sunset over mountains"
}
```

## Metadata Enhancement

Upload records now include AI generation metadata:
```json
{
  "metadata": {
    "ai_description_generated": true,
    "ai_description": "Generated description text",
    "background_removal": {...},
    "processing_applied": "background_removal"
  }
}
```

## Error Handling

The integration is designed to be fault-tolerant:

### Connection Issues
- **Problem**: Interrogation API service unavailable
- **Behavior**: Upload continues without description
- **Log**: "Could not connect to image interrogation API"

### Timeout Issues  
- **Problem**: API response takes too long (>30s)
- **Behavior**: Upload continues without description
- **Log**: "Image interrogation API request timed out"

### API Errors
- **Problem**: API returns error status
- **Behavior**: Upload continues without description  
- **Log**: "Image interrogation API failed with status XXX"

## Configuration

### Environment Variables
Add to your `.env` file:
```env
INTERROGATE_API_URL=http://127.0.0.1:7860/sdapi/v1/interrogate
```

### Dependencies
Make sure to install the new dependency:
```bash
pip install httpx==0.27.0
```

## Benefits

### ✅ Automatic Content Recognition
- No manual description needed
- Consistent, AI-generated descriptions
- Better searchability and organization

### ✅ Flexible Usage
- Optional feature (can be disabled)
- User descriptions take priority
- Configurable API endpoint

### ✅ Robust Implementation
- Graceful degradation if API unavailable
- No impact on core upload functionality
- Comprehensive error handling

### ✅ Metadata Tracking
- Records whether AI was used
- Stores original AI description
- Maintains processing history

## Testing

### Prerequisites
1. Interrogation API service running on configured URL
2. CLIP model available in the service
3. Test images available for upload

### Test Cases

#### 1. Successful AI Description Generation
```bash
# Upload without description - should generate AI description
curl -X POST "http://localhost:8000/upload-remove-bg" \
  -F "file=@test_image.jpg" \
  -F "image_type=gallery"

# Expected: Upload succeeds with AI-generated description
```

#### 2. API Service Unavailable
```bash
# Stop interrogation service and upload
curl -X POST "http://localhost:8000/upload-remove-bg" \
  -F "file=@test_image.jpg" \
  -F "image_type=gallery"

# Expected: Upload succeeds without description, logs connection error
```

#### 3. User Description Priority
```bash
# Upload with custom description
curl -X POST "http://localhost:8000/upload-remove-bg" \
  -F "file=@test_image.jpg" \
  -F "description=My custom description" \
  -F "image_type=gallery"

# Expected: Uses custom description, AI not called
```

#### 4. AI Generation Disabled
```bash
# Upload with AI generation disabled
curl -X POST "http://localhost:8000/upload-remove-bg" \
  -F "file=@test_image.jpg" \
  -F "image_type=gallery" \
  -F "generate_ai_description=false"

# Expected: No description generated, AI not called
```

## Notes

- AI description is only generated for the background-removed endpoint
- The processed (background-removed) image is sent to the API, not the original
- Base64 encoding is handled automatically
- API calls are made asynchronously and don't block the upload process
- Generated descriptions are stored in both the `description` field and metadata
