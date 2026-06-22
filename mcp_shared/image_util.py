import os
import io
import cv2
import base64
import logging
import hashlib
import numpy as np


def convert_b64_to_bytes_and_gray(receipt_image_b64):
        """Converts base64 input strings to raw bytes and processed gray image arrays"""
        # 1. Reconstruct raw image bytes
        image_bytes = base64.b64decode(receipt_image_b64)
        image_hash = hashlib.sha256(image_bytes).hexdigest()

        # 2. Convert raw bytes to a processing array for CV2
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # 3. Convert to gray image array natively
        gray_image_bytes = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 4. Re-encode the gray image back to a b64 string for the monitor payload
        _, encoded_img = cv2.imencode(".jpg", gray_image_bytes)
        gray_image_b64 = base64.b64encode(encoded_img).decode("utf-8")

        return image_bytes, image_hash, gray_image_bytes, gray_image_b64

    
