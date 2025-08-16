import io
import logging
from typing import Tuple, Optional
from PIL import Image
import numpy as np
from rembg import remove, new_session
import cv2

logger = logging.getLogger(__name__)

class BackgroundRemover:
    """
    Background removal service using rembg library with multiple models
    """
    
    def __init__(self):
        self.session = None
        self._initialize_session()
    
    def _initialize_session(self):
        """Initialize rembg session with default model"""
        try:
            # Use u2net model as default (good for general purpose)
            self.session = new_session('u2net')
            logger.info("Background remover initialized with u2net model")
        except Exception as e:
            logger.error(f"Failed to initialize background remover: {e}")
            self.session = None
    
    def remove_background(self, image_data: bytes, model_name: str = 'u2net') -> Tuple[bytes, dict]:
        """
        Remove background from image
        
        Args:
            image_data: Raw image bytes
            model_name: Model to use for background removal
                       Options: 'u2net', 'u2netp', 'silueta', 'isnet-general-use'
        
        Returns:
            Tuple of (processed_image_bytes, metadata)
        """
        try:
            # Initialize session with specified model if different from current
            if model_name != 'u2net' or self.session is None:
                self.session = new_session(model_name)
            
            # Load original image
            original_image = Image.open(io.BytesIO(image_data))
            original_width, original_height = original_image.size
            original_format = original_image.format
            
            logger.info(f"Processing image: {original_width}x{original_height}, format: {original_format}")
            
            # Remove background
            result_image = remove(image_data, session=self.session)
            
            # Convert to PIL Image for further processing
            processed_image = Image.open(io.BytesIO(result_image))
            
            # Ensure RGBA mode for transparency
            if processed_image.mode != 'RGBA':
                processed_image = processed_image.convert('RGBA')
            
            # Save processed image to bytes
            output_buffer = io.BytesIO()
            processed_image.save(output_buffer, format='PNG', optimize=True)
            processed_bytes = output_buffer.getvalue()
            
            # Calculate compression ratio
            original_size = len(image_data)
            processed_size = len(processed_bytes)
            compression_ratio = processed_size / original_size if original_size > 0 else 1.0
            
            metadata = {
                'original_size': original_size,
                'processed_size': processed_size,
                'compression_ratio': compression_ratio,
                'original_dimensions': (original_width, original_height),
                'processed_dimensions': processed_image.size,
                'original_format': original_format,
                'processed_format': 'PNG',
                'model_used': model_name,
                'has_transparency': True,
                'processing_status': 'success'
            }
            
            logger.info(f"Background removal completed. Original: {original_size} bytes, Processed: {processed_size} bytes")
            
            return processed_bytes, metadata
            
        except Exception as e:
            logger.error(f"Background removal failed: {str(e)}")
            raise Exception(f"Background removal failed: {str(e)}")
    
    def remove_background_with_edge_smoothing(self, image_data: bytes, model_name: str = 'u2net') -> Tuple[bytes, dict]:
        """
        Remove background with additional edge smoothing for better quality
        
        Args:
            image_data: Raw image bytes
            model_name: Model to use for background removal
        
        Returns:
            Tuple of (processed_image_bytes, metadata)
        """
        try:
            # First, perform standard background removal
            processed_bytes, metadata = self.remove_background(image_data, model_name)
            
            # Load the processed image for edge smoothing
            processed_image = Image.open(io.BytesIO(processed_bytes))
            
            # Convert to numpy array for OpenCV processing
            img_array = np.array(processed_image)
            
            # Extract alpha channel
            if img_array.shape[2] == 4:  # RGBA
                alpha = img_array[:, :, 3]
                
                # Apply Gaussian blur to alpha channel for smoother edges
                alpha_blurred = cv2.GaussianBlur(alpha, (3, 3), 1)
                
                # Apply morphological operations to clean up the mask
                kernel = np.ones((2, 2), np.uint8)
                alpha_cleaned = cv2.morphologyEx(alpha_blurred, cv2.MORPH_CLOSE, kernel)
                alpha_cleaned = cv2.morphologyEx(alpha_cleaned, cv2.MORPH_OPEN, kernel)
                
                # Replace alpha channel
                img_array[:, :, 3] = alpha_cleaned
                
                # Convert back to PIL Image
                smoothed_image = Image.fromarray(img_array, 'RGBA')
                
                # Save smoothed image
                output_buffer = io.BytesIO()
                smoothed_image.save(output_buffer, format='PNG', optimize=True)
                smoothed_bytes = output_buffer.getvalue()
                
                # Update metadata
                metadata['processed_size'] = len(smoothed_bytes)
                metadata['edge_smoothing_applied'] = True
                metadata['compression_ratio'] = len(smoothed_bytes) / metadata['original_size']
                
                logger.info("Edge smoothing applied to background removal result")
                
                return smoothed_bytes, metadata
            else:
                # If no alpha channel, return original processed result
                return processed_bytes, metadata
                
        except Exception as e:
            logger.error(f"Edge smoothing failed, returning standard result: {str(e)}")
            # Fallback to standard background removal
            return self.remove_background(image_data, model_name)
    
    def get_available_models(self) -> list:
        """Get list of available background removal models"""
        return [
            'u2net',           # General purpose, good quality
            'u2netp',          # Lighter version of u2net
            'silueta',         # Good for people/portraits
            'isnet-general-use' # High accuracy general use
        ]
    
    def validate_model(self, model_name: str) -> bool:
        """Validate if model name is supported"""
        return model_name in self.get_available_models()

# Global instance
background_remover = BackgroundRemover()
