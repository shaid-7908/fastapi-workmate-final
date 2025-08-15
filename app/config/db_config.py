import asyncio
import logging
import signal
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure
from .env_config import env_config

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Database connection manager for MongoDB using Motor (async driver)"""
    
    def __init__(self):
        self.client: AsyncIOMotorClient | None = None
        self.database = None
        
    async def connect_db(self) -> None:
        """
        Connect to MongoDB database
        Equivalent to the TypeScript connectDB function
        """
        try:
            # Create MongoDB client with connection options
            self.client = AsyncIOMotorClient(
                env_config.MONGODB_URL,
                serverSelectionTimeoutMS=5000,  # 5 second timeout
                maxPoolSize=10,  # Maximum number of connections in the pool
                minPoolSize=1,   # Minimum number of connections in the pool
                maxIdleTimeMS=30000,  # Close connections after 30 seconds of inactivity
                connectTimeoutMS=5000,  # 5 second connection timeout
            )
            
            # Select database
            self.database = self.client[env_config.MONGODB_DB_NAME]
            
            # Test the connection
            await self.client.admin.command('ping')
            
            logger.info("MongoDB connected successfully")
            logger.info(f"Database: {env_config.MONGODB_DB_NAME}")
            
        except ServerSelectionTimeoutError as e:
            logger.error(f"MongoDB connection timeout: {e}")
            sys.exit(1)  # Stop app if DB fails
        except ConnectionFailure as e:
            logger.error(f"MongoDB connection failed: {e}")
            sys.exit(1)  # Stop app if DB fails
        except Exception as e:
            logger.error(f"MongoDB connection error: {e}")
            sys.exit(1)  # Stop app if DB fails
    
    async def disconnect_db(self) -> None:
        """
        Disconnect from MongoDB database
        Equivalent to graceful shutdown in TypeScript
        """
        if self.client:
            self.client.close()
            logger.info("MongoDB disconnected")
        else:
            logger.warning("No MongoDB connection to close")
    
    def get_database(self):
        """Get the database instance"""
        if self.database is None:
            raise RuntimeError("Database not connected. Call connect_db() first.")
        return self.database
    
    def get_collection(self, collection_name: str):
        """Get a specific collection from the database"""
        database = self.get_database()
        return database[collection_name]

# Global database manager instance
db_manager = DatabaseManager()

# Convenience functions for easier usage
async def connect_db() -> None:
    """Connect to MongoDB database"""
    await db_manager.connect_db()

async def disconnect_db() -> None:
    """Disconnect from MongoDB database"""
    await db_manager.disconnect_db()

def get_database():
    """Get the database instance"""
    return db_manager.get_database()

def get_collection(collection_name: str):
    """Get a specific collection from the database"""
    return db_manager.get_collection(collection_name)

# Graceful shutdown handlers (equivalent to process.on("SIGINT") in Node.js)
def setup_graceful_shutdown():
    """Setup graceful shutdown handlers for the application"""
    
    def signal_handler(signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}. Shutting down gracefully...")
        
        # Run the async disconnect in the event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, schedule the disconnect
            asyncio.create_task(disconnect_db())
        else:
            # If loop is not running, run it
            loop.run_until_complete(disconnect_db())
        
        logger.info("Application terminated gracefully")
        sys.exit(0)
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination signal

# Auto-setup graceful shutdown when module is imported
setup_graceful_shutdown()
