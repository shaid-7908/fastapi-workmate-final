from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo import IndexModel, ASCENDING

from config.db_config import get_collection


class UserModelClass:
    """
    User model class with Mongoose-like interface
    Provides .find(), .findOne(), .aggregate() and other MongoDB operations
    """
    
    def __init__(self):
        self.collection_name = "users"
        self._collection: Optional[AsyncIOMotorCollection] = None
    
    @property
    def collection(self) -> AsyncIOMotorCollection:
        """Get the users collection"""
        if self._collection is None:
            self._collection = get_collection(self.collection_name)
        return self._collection
    
    async def createIndexes(self) -> None:
        """Create database indexes for the users collection"""
        indexes = [
            IndexModel([("email", ASCENDING)], unique=True),
            IndexModel([("googleId", ASCENDING)], sparse=True),
            IndexModel([("refreshToken", ASCENDING)], sparse=True),
            IndexModel([("createdAt", ASCENDING)]),
            IndexModel([("role", ASCENDING)]),
            IndexModel([("isVerified", ASCENDING)])
        ]
        await self.collection.create_indexes(indexes)
    
    # Mongoose-like methods
    async def find(self, filter_dict: Dict[str, Any] = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Find multiple documents - Mongoose-like interface
        
        Args:
            filter_dict: MongoDB filter query
            **kwargs: Additional options like limit, skip, sort
            
        Returns:
            List of documents
        """
        if filter_dict is None:
            filter_dict = {}
        
        cursor = self.collection.find(filter_dict)
        
        # Apply additional options
        if 'limit' in kwargs:
            cursor = cursor.limit(kwargs['limit'])
        if 'skip' in kwargs:
            cursor = cursor.skip(kwargs['skip'])
        if 'sort' in kwargs:
            cursor = cursor.sort(kwargs['sort'])
        
        return await cursor.to_list(length=kwargs.get('limit', 1000))
    
    async def findOne(self, filter_dict: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Find one document - Mongoose-like interface
        
        Args:
            filter_dict: MongoDB filter query
            
        Returns:
            Document if found, None otherwise
        """
        if filter_dict is None:
            filter_dict = {}
        
        return await self.collection.find_one(filter_dict)
    
    async def findById(self, user_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """
        Find document by ID - Mongoose-like interface
        
        Args:
            user_id: Document ID
            
        Returns:
            Document if found, None otherwise
        """
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        return await self.collection.find_one({"_id": user_id})
    
    async def aggregate(self, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Run aggregation pipeline - Mongoose-like interface
        
        Args:
            pipeline: MongoDB aggregation pipeline
            
        Returns:
            List of aggregated results
        """
        cursor = self.collection.aggregate(pipeline)
        return await cursor.to_list(length=None)
    
    async def insertOne(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Insert one document - Mongoose-like interface
        
        Args:
            document: Document to insert
            
        Returns:
            Inserted document with _id
        """
        # Add timestamps if not present
        if 'createdAt' not in document:
            document['createdAt'] = datetime.utcnow()
        if 'updatedAt' not in document:
            document['updatedAt'] = datetime.utcnow()
        
        result = await self.collection.insert_one(document)
        document['_id'] = result.inserted_id
        return document
    
    async def insertMany(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Insert multiple documents - Mongoose-like interface
        
        Args:
            documents: List of documents to insert
            
        Returns:
            List of inserted documents with _ids
        """
        # Add timestamps to all documents
        for doc in documents:
            if 'createdAt' not in doc:
                doc['createdAt'] = datetime.utcnow()
            if 'updatedAt' not in doc:
                doc['updatedAt'] = datetime.utcnow()
        
        result = await self.collection.insert_many(documents)
        
        # Add the inserted IDs back to documents
        for i, doc in enumerate(documents):
            doc['_id'] = result.inserted_ids[i]
        
        return documents
    
    async def updateOne(self, filter_dict: Dict[str, Any], update_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update one document - Mongoose-like interface
        
        Args:
            filter_dict: Filter to find document
            update_dict: Update operations
            
        Returns:
            Update result information
        """
        # Add updatedAt timestamp
        if '$set' not in update_dict:
            update_dict['$set'] = {}
        update_dict['$set']['updatedAt'] = datetime.utcnow()
        
        result = await self.collection.update_one(filter_dict, update_dict)
        return {
            'acknowledged': result.acknowledged,
            'matched_count': result.matched_count,
            'modified_count': result.modified_count,
            'upserted_id': result.upserted_id
        }
    
    async def updateMany(self, filter_dict: Dict[str, Any], update_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update multiple documents - Mongoose-like interface
        
        Args:
            filter_dict: Filter to find documents
            update_dict: Update operations
            
        Returns:
            Update result information
        """
        # Add updatedAt timestamp
        if '$set' not in update_dict:
            update_dict['$set'] = {}
        update_dict['$set']['updatedAt'] = datetime.utcnow()
        
        result = await self.collection.update_many(filter_dict, update_dict)
        return {
            'acknowledged': result.acknowledged,
            'matched_count': result.matched_count,
            'modified_count': result.modified_count,
            'upserted_id': result.upserted_id
        }
    
    async def findOneAndUpdate(self, filter_dict: Dict[str, Any], update_dict: Dict[str, Any], **kwargs) -> Optional[Dict[str, Any]]:
        """
        Find and update one document - Mongoose-like interface
        
        Args:
            filter_dict: Filter to find document
            update_dict: Update operations
            **kwargs: Additional options like return_document
            
        Returns:
            Updated document or None
        """
        # Add updatedAt timestamp
        if '$set' not in update_dict:
            update_dict['$set'] = {}
        update_dict['$set']['updatedAt'] = datetime.utcnow()
        
        return await self.collection.find_one_and_update(
            filter_dict, 
            update_dict, 
            return_document=kwargs.get('return_document', True)
        )
    
    async def deleteOne(self, filter_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete one document - Mongoose-like interface
        
        Args:
            filter_dict: Filter to find document to delete
            
        Returns:
            Delete result information
        """
        result = await self.collection.delete_one(filter_dict)
        return {
            'acknowledged': result.acknowledged,
            'deleted_count': result.deleted_count
        }
    
    async def deleteMany(self, filter_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete multiple documents - Mongoose-like interface
        
        Args:
            filter_dict: Filter to find documents to delete
            
        Returns:
            Delete result information
        """
        result = await self.collection.delete_many(filter_dict)
        return {
            'acknowledged': result.acknowledged,
            'deleted_count': result.deleted_count
        }
    
    async def countDocuments(self, filter_dict: Dict[str, Any] = None) -> int:
        """
        Count documents - Mongoose-like interface
        
        Args:
            filter_dict: Filter to count documents
            
        Returns:
            Number of documents matching filter
        """
        if filter_dict is None:
            filter_dict = {}
        
        return await self.collection.count_documents(filter_dict)
    
    async def distinct(self, field: str, filter_dict: Dict[str, Any] = None) -> List[Any]:
        """
        Get distinct values for a field - Mongoose-like interface
        
        Args:
            field: Field name to get distinct values for
            filter_dict: Optional filter
            
        Returns:
            List of distinct values
        """
        if filter_dict is None:
            filter_dict = {}
        
        return await self.collection.distinct(field, filter_dict)
    
    # Convenience methods for common operations
    async def findByEmail(self, email: str) -> Optional[Dict[str, Any]]:
        """Find user by email"""
        return await self.findOne({"email": email})
    
    async def findByGoogleId(self, google_id: str) -> Optional[Dict[str, Any]]:
        """Find user by Google ID"""
        return await self.findOne({"googleId": google_id})
    
    async def findByRefreshToken(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """Find user by refresh token"""
        return await self.findOne({"refreshToken": refresh_token})
    
    async def findVerifiedUsers(self) -> List[Dict[str, Any]]:
        """Find all verified users"""
        return await self.find({"isVerified": True})
    
    async def findUsersByRole(self, role: str) -> List[Dict[str, Any]]:
        """Find users by role"""
        return await self.find({"role": role})


# Export the UserModel instance - equivalent to Mongoose model export
UserModel = UserModelClass()