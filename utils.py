import json

import cv2

def read_image(image_file, convert_color=False):
    if convert_color:
        return cv2.cvtColor((cv2.imread(image_file), cv2.COLOR_BGR2RGB))
    else:
        return cv2.imread(image_file)

def read_json(json_file):
    with open(json_file) as f:
        j = json.load(f)
    return j

def scale(image, scale):
    return cv2.resize(image, None, fx=scale, fy=scale)

def resize(image, width=None, height=None, interpolation=cv2.INTER_NEAREST):
    if width == None and height == None:
        return image

    width0, height0 = image.shape[:2]

    if width != None and height == None:
        w_scale = width / width0
        height = int(height0 * w_scale)
        return cv2.resize(image, (height, width), interpolation=interpolation)

    if height != None and width == None:
        h_scale = height / height0
        width = int(width0 * h_scale)
        return cv2.resize(image, (height, width), interpolation=interpolation)

    return cv2.resize(image, (height, width), interpolation=interpolation)

def write_json(j, json_file, indent=4):
    with open(json_file, 'w') as f:
        json.dump(j, f, indent=indent)
