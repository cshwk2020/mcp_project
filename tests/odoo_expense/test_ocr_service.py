import os, io
import cv2
import pytest
import numpy as np
from mcp_project.mcp_servers.mcp_ocr.ocr_service import MCPOcrService
from mcp_project.config import UPLOAD_FOLDER

TEST_FILE_PATH = "/Users/cshwk1995/Desktop/img/receipts/IMG_2150.jpg"
TEST_FAIL_FILE_PATH = "/Users/cshwk1995/Desktop/img/receipts/non_image_txt.jpg"


@pytest.fixture(scope="module")
def ocr_service():
    return MCPOcrService()

@pytest.mark.skip(reason="temporarily disabled")
def test_real_easyocr_bytes_success(ocr_service):
    gray_image, texts = test_real_easyocr_bytes(ocr_service, TEST_FILE_PATH)
    print('test_real_easyocr_bytes: len(gray_image) == ', len(gray_image))
    print('test_real_easyocr_bytes: texts == ', texts)

@pytest.mark.skip(reason="temporarily disabled")
def test_real_easyocr_bytes_fail_file_missing(ocr_service):
     
    with pytest.raises(Exception) as exc_info:
        _ = test_real_easyocr_bytes(ocr_service, "a/b/c")

    assert exc_info.value is not None
    print(f"Exception occurred: {exc_info.value}")


@pytest.mark.skip(reason="temporarily disabled")
def test_real_easyocr_bytes_fail_ocr_bad(ocr_service):
     
    with pytest.raises(Exception) as exc_info:
        _ = test_real_easyocr_bytes(ocr_service, TEST_FAIL_FILE_PATH)

    assert exc_info.value is not None
    print(f"Exception occurred: {exc_info.value}")

 

@pytest.mark.skip(reason="temporarily disabled")
def test_real_easyocr_bytes(ocr_service, file_path):

    with open(file_path, "rb") as f:
        data = f.read()
        image_bytes = io.BytesIO(data)
        return ocr_service._real_easyocr_bytes(image_bytes)
         
    raise Value(f'test_real_easyocr_bytes: {file_path} cannot open')


@pytest.mark.skip(reason="temporarily disabled")
def test_ocr_run_bytes_b64_success(ocr_service):
     
    with open(TEST_FILE_PATH, "rb") as f:
        data = f.read()
        image_bytes = io.BytesIO(data)
        gray_image, texts = ocr_service.run_bytes_b64(image_bytes)
        print('test_real_easyocr_bytes: len(gray_image) == ', len(gray_image))
        print('test_real_easyocr_bytes: texts == ', texts)



@pytest.mark.skip(reason="temporarily disabled")
def test_run_easyocr_file(ocr_service):

    file_path = TEST_FILE_PATH
    filename = os.path.basename(file_path)
    new_file_path = os.path.abspath(os.path.join(UPLOAD_FOLDER, filename))

    gray_image_np, texts = ocr_service.run_file(file_path)
    print('texts: ', texts)
    cv2.imwrite(new_file_path, gray_image_np)

@pytest.mark.skip(reason="temporarily disabled")
def test_convert_to_gray_image(ocr_service):
    file_path = TEST_FILE_PATH
    file_obj = ocr_service.filepath_to_fileobj(file_path)
    filename = file_obj.filename

    gray_image_obj = ocr_service.convert_to_gray_image(file_obj)
    grayimage_fullpath = os.path.abspath(os.path.join(UPLOAD_FOLDER, 'gray_' + filename))
    cv2.imwrite(grayimage_fullpath, gray_image_obj)

@pytest.mark.skip(reason="temporarily disabled")
def test_fileobj_to_filepath(ocr_service):
    file_path = TEST_FILE_PATH
    file_obj = ocr_service.filepath_to_fileobj(file_path)

    new_file_path = os.path.abspath(os.path.join(UPLOAD_FOLDER, "test_copy.jpg"))
    file_obj.save(new_file_path)
    print('test_fileobj_to_filepath: ', file_obj)

@pytest.mark.skip(reason="temporarily disabled")
def test_filepath_to_fileobj(ocr_service):
    file_path = TEST_FILE_PATH
    file_obj = ocr_service.filepath_to_fileobj(file_path)

    print(file_obj.filename)
    print(file_obj.content_type)

@pytest.mark.skip(reason="temporarily disabled")
def test_preocr_process_image(ocr_service):
    filepath = TEST_FILE_PATH
    result = ocr_service.convert_to_gray_image(ocr_service.filepath_to_fileobj(filepath))
    print("result shape: ", result.shape)
