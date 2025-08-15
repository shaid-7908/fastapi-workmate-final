from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

from app.controller.user_controller import user_controller

# Create router
router = APIRouter()

# Request models
class UserRegisterRequest(BaseModel):
    firstName: str = Field(..., min_length=1, max_length=50, description="User's first name")
    lastName: str = Field(..., min_length=1, max_length=50, description="User's last name")
    email: EmailStr = Field(..., description="User's email address")
    phone: str = Field(..., min_length=10, max_length=15, description="User's phone number")
    password: str = Field(..., min_length=8, description="User's password (minimum 8 characters)")
    profileImage: Optional[str] = Field(None, description="URL to user's profile image")
    dateOfBirth: Optional[datetime] = Field(None, description="User's date of birth")
    role: Optional[str] = Field("user", description="User role (user or admin)")

    class Config:
        schema_extra = {
            "example": {
                "firstName": "John",
                "lastName": "Doe",
                "email": "john.doe@example.com",
                "phone": "+1234567890",
                "password": "securepassword123",
                "profileImage": "https://example.com/profile.jpg",
                "dateOfBirth": "1990-01-01T00:00:00Z",
                "role": "user"
            }
        }

# Response models
class UserResponse(BaseModel):
    id: str
    firstName: str
    lastName: str
    email: str
    phone: str
    profileImage: Optional[str] = None
    dateOfBirth: Optional[datetime] = None
    role: str
    isVerified: bool
    createdAt: datetime
    updatedAt: datetime

class RegisterResponse(BaseModel):
    success: bool
    message: str
    user: UserResponse

# Routes
@router.post(
    "/register", 
    
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account with email and password"
)
async def register_user(user_data: UserRegisterRequest):
    """
    Register a new user
    
    - **firstName**: User's first name (required)
    - **lastName**: User's last name (required)  
    - **email**: Valid email address (required, must be unique)
    - **phone**: Phone number (required)
    - **password**: Password with minimum 8 characters (required)
    - **profileImage**: URL to profile image (optional)
    - **dateOfBirth**: User's date of birth (optional)
    - **role**: User role - 'user' or 'admin' (optional, defaults to 'user')
    
    Returns the created user data (without password) and success message.
    """
    try:
        # Convert Pydantic model to dict
        user_dict = user_data.dict()
        
        # Call controller to handle registration
        result = await user_controller.register_user(user_dict)
        
        return result
        
    except HTTPException:
        # Re-raise HTTP exceptions from controller
        raise
    except Exception as e:
        print(str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

# Health check for user routes
@router.get(
    "/health",
    summary="User routes health check",
    description="Check if user routes are working"
)
async def user_routes_health():
    """Health check endpoint for user routes"""
    return {
        "status": "healthy",
        "service": "user_routes",
        "message": "User routes are working properly"
    }
