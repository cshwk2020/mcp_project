import os
import io
import cv2
import numpy as np
import base64
import logging
import easyocr
from PIL import Image, ImageOps
from werkzeug.datastructures import FileStorage

from mcp_project.mcp_shared.app_util import debugText
from mcp_project.mcp_shared.logging_util import logger
from mcp_project.config import MODE_REAL, MODE_OCR_EXCEPTION, MOCK_FILE_PATH, MOCK_FILE_OCR_TEXTS

logger = logging.getLogger(__name__)


class MCPOcrService:

    def __init__(self, langs=['ch_tra', 'en']):
        self.service_name = "EasyOCR MCP Component"
        self.reader = easyocr.Reader(langs)

    def get_tools_schema(self):
        return [{
            "name": "ocr_run_file_b64",
            "description": "Run OCR on an image file path.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string"}
                },
                "required": ["filepath"]
            }
        }, {
            "name": "ocr_run_bytes_b64",
            "description": "Run OCR on raw image bytes.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "image_bytes": {"type": "string", "description": "Base64 encoded image bytes"}
                },
                "required": ["image_bytes"]
            }
        }]

    def run_file_b64(self, filepath):
        """Called by the generic ServiceRegistry for 'ocr_run_file'."""
        # Call your original method that your unit tests rely on
        gray_image, texts = self.run_file(filepath)
        
        # Format cleanly into JSON-safe structures for the remote client
        return {
            "texts": texts,
            "image_base64": self.np_array_to_base64_image(gray_image)
        }

    def run_bytes_b64(self, image_bytes):
 
        if MODE_OCR_EXCEPTION == True:
            raise ValueError("MODE_OCR_EXCEPTION")
        

        if isinstance(image_bytes, str):
            import base64
            decoded = base64.b64decode(image_bytes)
            image_bytes = io.BytesIO(decoded)

        # Call your original method that your unit tests rely on
        gray_image, texts = self.run_bytes(image_bytes)
        
        return {
            "texts": texts,
            "image_base64": self.np_array_to_base64_image(gray_image)
        }


    # --- Target Methods ---
    def run_bytes(self, image_bytes):
        if MODE_REAL:
            return self._real_easyocr_bytes(image_bytes)
        else:
            return self._mock_easyocr_bytes(image_bytes)

    def run_file(self, filepath):
        with open(filepath, "rb") as f:
            data = f.read()
        return self.run_bytes(io.BytesIO(data))




    # --- Internal helpers ---
    def _real_easyocr_bytes(self, image_bytes):

        print("DEBUG...0...._real_easyocr_bytes.....")
        
        gray_image = self.convert_to_gray_image(image_bytes)
        results = self.reader.readtext(gray_image)

        if not results:  
            raise ValueError("OCR returned no text")

        texts = [text for (_, text, _) in results]
        for (_, text, prob) in results:
            print(f"OCR detected: {text} (confidence {prob:.2f})")

        return gray_image, texts


    def _mock_easyocr_bytes(self, image_bytes):
        mock_file_obj = self.filepath_to_fileobj(MOCK_FILE_PATH)
        gray_image = self.convert_to_gray_image(mock_file_obj)
        return gray_image, MOCK_FILE_OCR_TEXTS


    def convert_to_gray_image(self, file_obj):

        if hasattr(file_obj, "stream"):
            data = file_obj.read()
            file_obj.stream.seek(0)
        else:
            data = file_obj.read()
            file_obj.seek(0)

        image = Image.open(io.BytesIO(data))
        image = ImageOps.exif_transpose(image)
        image_np = np.array(image)

        if len(image_np.shape) == 3 and image_np.shape[2] == 3:
            gray_image_np = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
        elif len(image_np.shape) == 3 and image_np.shape[2] == 4:
            gray_image_np = cv2.cvtColor(image_np, cv2.COLOR_RGBA2GRAY)
        else:
            gray_image_np = image_np

        if gray_image_np.size == 0:
            raise ValueError("Empty grayscale image")

        _, gray_image_np = cv2.threshold(gray_image_np, 150, 255, cv2.THRESH_BINARY)
        gray_image_np = cv2.medianBlur(gray_image_np, 1)

        h, w = gray_image_np.shape
        if w > 0 and h > 0 and w < 800:
            scale = 800 / w
            gray_image_np = cv2.resize(gray_image_np, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_CUBIC)

        logger.info(f"Image preprocessed: {gray_image_np.shape}, dtype={gray_image_np.dtype}")
        return gray_image_np



    def filepath_to_fileobj(self, file_path):
        with open(file_path, "rb") as f:
            data = f.read()
            stream = io.BytesIO(data)
            return FileStorage(
                stream=stream,
                filename=os.path.basename(file_path),
                content_type="image/jpeg"
            )

    def np_array_to_base64_image(self, np_array):
        success, buffer = cv2.imencode(".jpg", np_array)
        if not success:
            return None
        return base64.b64encode(buffer).decode("utf-8")

    def deskew(self, gray_image):
        gray_inv = cv2.bitwise_not(gray_image)
        coords = np.column_stack(np.where(gray_inv > 0))
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        (h, w) = gray_image.shape
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(gray_image, M, (w, h),
                                 flags=cv2.INTER_CUBIC,
                                 borderMode=cv2.BORDER_REPLICATE)
        return rotated

    def dewarp_wave(self, gray_image):
        if len(gray_image.shape) != 2:
            raise ValueError("Expected grayscale image")
        h, w = gray_image.shape
        src_pts = np.float32([[0,0], [w-1,0], [0,h-1], [w-1,h-1]])
        dst_pts = np.float32([[0,0], [w-1,0], [int(0.05*w),h-1], [w-1-int(0.05*w),h-1]])
        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        warped = cv2.warpPerspective(gray_image, M, (w,h),
                                     flags=cv2.INTER_CUBIC,
                                     borderMode=cv2.BORDER_REPLICATE)
        return warped
