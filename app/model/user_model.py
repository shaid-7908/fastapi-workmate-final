from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from app.config.db_config import db_manager

# User Pydantic model - similar to your existing models
class User(BaseModel):
    firstName: str = Field(..., min_length=1, max_length=50)
    lastName: str = Field(..., min_length=1, max_length=50)
    email: EmailStr = Field(..., description="User email address")
    phone: str = Field(..., min_length=10, max_length=15)
    profileImage: Optional[str] = Field(None, description="URL to profile image")
    dateOfBirth: Optional[datetime] = Field(None, description="User's date of birth")
    password: str = Field(..., description="User password")
    refreshToken: Optional[str] = Field(None, description="JWT refresh token")
    createdAt: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updatedAt: Optional[datetime] = Field(default_factory=datetime.utcnow)

# Global variables for lazy initialization
_db = None
_user_model = None

def get_user_model():
    """Get UserModel collection with lazy initialization"""
    global _db, _user_model
    if _user_model is None:
        _db = db_manager.get_database()
        _user_model = _db["users"]
    return _user_model

# For backward compatibility - this will be initialized when first accessed
class UserModelProxy:
    def __getattr__(self, name):
        return getattr(get_user_model(), name)
    
    def __getitem__(self, key):
        return get_user_model()[key]

UserModel = UserModelProxy()

# Index creation function
async def create_user_indexes():
    """Create all necessary indexes for users collection"""
    from pymongo import IndexModel, ASCENDING, DESCENDING
    
    indexes = [
        IndexModel([("email", ASCENDING)], unique=True, name="email_unique"),
    ]
    
    try:
        user_collection = get_user_model()
        result = await user_collection.create_indexes(indexes)
        # Convert result to list if it's not already
        if hasattr(result, '__iter__') and not isinstance(result, str):
            result_list = list(result)
        else:
            result_list = [result] if result is not None else []
        print(f"User indexes created: {result_list}")
        return result_list
    except Exception as e:
        print(f"Error creating user indexes: {e}")
        return []

