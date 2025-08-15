from datetime import datetime
from typing import Dict, Any
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from app.model.user_model import User, UserModel
from app.utils.password_utils import hash_password

class UserController:
    """User controller for handling user-related operations"""
    
    @staticmethod
    async def register_user(user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Register a new user
        
        Args:
            user_data: Dictionary containing user registration data
            
        Returns:
            Dictionary with success status and user data (without password)
            
        Raises:
            HTTPException: If registration fails
        """
        try:
            # Validate required fields
            required_fields = ['firstName', 'lastName', 'email', 'phone', 'password']
            for field in required_fields:
                if field not in user_data or not user_data[field]:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Missing required field: {field}"
                    )
            
            # Check if user already exists
            existing_user = await UserModel.find_one({"email": user_data['email']})
            if existing_user:
                raise HTTPException(
                    status_code=400, 
                    detail="User with this email already exists"
                )
            
            # Hash the password
            hashed_password = hash_password(user_data['password'])
            
            # Prepare user document
            user_doc = {
                'firstName': user_data['firstName'],
                'lastName': user_data['lastName'],
                'email': user_data['email'].lower(),  # Store email in lowercase
                'phone': user_data['phone'],
                'password': hashed_password,
                'role': user_data.get('role', 'user'),
                'isVerified': False,
                'profileImage': user_data.get('profileImage'),
                'dateOfBirth': user_data.get('dateOfBirth'),
                'googleId': None,
                'refreshToken': None,
                'createdAt': datetime.utcnow(),
                'updatedAt': datetime.utcnow()
            }
            
            # Validate with Pydantic model (optional but recommended)
            try:
                User(**user_doc)  # This will validate the data structure
            except Exception as e:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid user data: {str(e)}"
                )
            
            # Insert user into database
            result = await UserModel.insert_one(user_doc)
            
            if not result.inserted_id:
                raise HTTPException(
                    status_code=500, 
                    detail="Failed to create user"
                )
            
            # Get the created user (without password)
            created_user = await UserModel.find_one({"_id": result.inserted_id})
            if created_user:
                # Remove password from response
                created_user.pop('password', None)
                created_user['id'] = str(created_user['_id'])
                created_user.pop('_id', None)
            
            return {
                "success": True,
                "message": "User registered successfully",
                "user": created_user
            }
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except DuplicateKeyError:
            raise HTTPException(
                status_code=400, 
                detail="User with this email already exists"
            )
        except Exception as e:
            print(f"Registration failed: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Registration failed: {str(e)}"
            )

# Create controller instance
user_controller = UserController()
