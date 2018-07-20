"""
    pdf2image is a light wrapper for the poppler-utils tools that can convert your
    PDFs into Pillow images.
"""

import os
import re
import tempfile
import uuid

from io import BytesIO
from subprocess import Popen, PIPE
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

def convert_from_path(pdf_path, dpi=200, output_folder=None, first_page=None, last_page=None, thread_count=1, userpw=None):
    """
        Description: Convert PDF to Image will throw whenever one of the condition is reached
        Parameters:
            pdf_path -> Path to the PDF that you want to convert
            dpi -> Image quality in DPI (default 200)
            output_folder -> Write the resulting images to a folder (instead of directly in memory)
            first_page -> First page to process
            last_page -> Last page to process before stopping
            fmt -> Output image format
            thread_count -> How many threads we are allowed to spawn for processing
            userpw -> PDF's password
    """
    
    pdf_name, _ = os.path.splitext(os.path.basename(pdf_path))
    page_count = __page_count(pdf_path, userpw)

    if thread_count < 1:
        thread_count = 1
        
    if page_count < thread_count:
        thread_count = page_count
        
    if first_page is None:
        first_page = 1

    if last_page is None or last_page > page_count:
        last_page = page_count

    # Recalculate page count based on first and last page
    page_count = last_page - first_page + 1

    if thread_count > page_count:
        thread_count = page_count

    reminder = page_count % thread_count
    current_page = first_page
    processes = []
    for _ in range(thread_count):
        # A unique identifier for our files if the directory is not empty
        uid = str(uuid.uuid4())
        # Get the number of pages the thread will be processing
        thread_page_count = page_count // thread_count + int(reminder > 0)
        # Build the command accordingly
        args, parse_buffer_func = __build_command(['pdftopng', '-r', str(dpi), pdf_path], output_folder, current_page, current_page + thread_page_count - 1, uid, userpw)
        # Update page values
        current_page = current_page + thread_page_count
        reminder -= int(reminder > 0)
        # Spawn the process and save its uuid
        processes.append((uid, Popen(args, stdout=PIPE, stderr=PIPE)))

    images = []
    for uid, proc in processes:
        data, _ = proc.communicate()

        if output_folder is not None:
            images += __load_from_output_folder(output_folder, uid)
        else:
            images += parse_buffer_func(data)
            
    for idx, image in enumerate(images):
        image_name = image.filename
        new_name = os.path.join(os.path.dirname(image_name), pdf_name + '-{}.png'.format(first_page + idx))
        image.close()
        if os.path.exists(new_name):
            os.path.remove(new_name)
        os.rename(image_name, new_name)
    return images

def convert_from_bytes(pdf_file, dpi=200, output_folder=None, first_page=None, last_page=None, thread_count=1, userpw=None):
    """
        Description: Convert PDF to Image will throw whenever one of the condition is reached
        Parameters:
            pdf_file -> Bytes representing the PDF file
            dpi -> Image quality in DPI
            output_folder -> Write the resulting images to a folder (instead of directly in memory)
            first_page -> First page to process
            last_page -> Last page to process before stopping
            fmt -> Output image format
            thread_count -> How many threads we are allowed to spawn for processing
            userpw -> PDF's password
    """

    with tempfile.NamedTemporaryFile('wb') as f:
        f.write(pdf_file)
        f.flush()
        return convert_from_path(f.name, dpi=dpi, output_folder=output_folder, first_page=first_page, last_page=last_page, thread_count=thread_count, userpw=userpw)

def __build_command(args, output_folder, first_page, last_page, uid, userpw):
    if first_page is not None:
        args.extend(['-f', str(first_page)])

    if last_page is not None:
        args.extend(['-l', str(last_page)])

    parsed_format, parse_buffer_func = 'png', __parse_buffer_to_png

    if output_folder is not None:
        args.append(os.path.join(output_folder, uid))

    if userpw is not None:
        args.extend(['-upw', userpw])

    return args, parse_buffer_func

def __parse_buffer_to_png(data):
    images = []

    index = 0

    while index < len(data):
        file_size = data[index:].index(b'IEND') + 8 # 4 bytes for IEND + 4 bytes for CRC
        images.append(Image.open(BytesIO(data[index:index+file_size])))
        index += file_size

    return images

def __page_count(pdf_path, userpw=None):
    if userpw is not None:
        proc = Popen(["pdfinfo", pdf_path, '-upw', userpw], stdout=PIPE, stderr=PIPE)
    else:
        proc = Popen(["pdfinfo", pdf_path], stdout=PIPE, stderr=PIPE)

    out, _ = proc.communicate()
    try:
        # This will throw if we are unable to get page count
        return int(re.search(r'Pages:\s+(\d+)', out.decode("utf8", "ignore")).group(1))
    except:
        raise Exception('Unable to get page count.')

def __load_from_output_folder(output_folder, uid):
    return [Image.open(os.path.join(output_folder, f)) for f in sorted(os.listdir(output_folder)) if uid in f]
