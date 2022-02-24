from collections import deque
from email.mime import image
import glob
import os
import shutil
import sys

import cv2

from utils import read_json, read_image, resize, write_json

ANNOTATION_FILE_EXTENSION = 'json'
ANNOTATIONS_DIRNAME = 'annotations'
CACHE_FILENAME = '.cache'
IMAGE_FILE_EXTENSION = 'jpg'
IMAGES_DIRNAME = 'images'
TEMPLATE_FILENAME = 'template.json'

BASE_WINDOW_NAME = 'Labelynx (0.0.1)'
BBOX_RATIO_PRECISION = 4
COLOR_CONVERSION = False
CONTENT_TEXT_SHIFT = 1
FIELD_TEXT_Y_SHIFT = 10
FONT = cv2.FONT_HERSHEY_PLAIN
FONT_SCALE = 1.5
FONT_COLOR = (220, 20, 20)
JSON_INDENTATION = 4
N_MAX_STATES = 20
RECTANGLE_COMPLETE_COLOR = (5, 220, 5)
RECTANGLE_WAIT_COLOR = (5, 5, 220)
RECTANGLE_WIDTH = 2
TEXT_SPACE_WIDTH_RATIO = 0.030
WIDTH_DISPLAY = 200

DIGITS = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
ORD_DIGITS = list(map(ord, DIGITS))

## Globals
drawing = False
writing = False
rect_start = False
x0, y0 = -1, -1
x1, y1 = -1, -1
text = ''
field = ''
full = False
image_view = None

class ImageView:
    def __init__(self, dataset_dir):
        self.dataset_dir = dataset_dir
        self.image_files = None
        self.n_image_files = None
        self.image_filenames = None
        self.image_filenames_wo_extension = None
        self._set_image_files()
        self.image_file = None
        self.image_filename = None

        self.annotations_dir = None
        self.annotation_files = None
        self._set_annotation_files()
        self.annotation_file = None
        self.annotation_json = None

        self.n_completed = 0
        self._init_n_completed()

        self.template_json_file = None
        self.template_json = None
        self._set_template_json()

        self.fields = []
        self.n_fields = 0
        self.field_index = None
        self.field = None
        self.full = False

        self.cache_file = None
        self._set_cache_file()

        self.image_states = deque([])
        self.image_index = self._read_cache()
        self.image_w, self.image_h = None, None
        self.image = self.get_image()
        self.write_cache(self.image_filename)

        self.text_space = int(self.image.shape[1] * TEXT_SPACE_WIDTH_RATIO)
        self.window_name = ''

    def _apply_annotation(self):
        for field in self.fields:
            _bbox = self.annotation_json[field]['bbox']
            if len(_bbox) > 0:
                _x0, _y0, _x1, _y1 = _bbox
                bbox = (_x0 * self.image_w, _y0 * self.image_h, _x1 * self.image_w, _y1 * self.image_h)
                bbox = tuple(map(int, bbox))
                content = self.annotation_json[field]['content']
                text = str(content)
                # if content:
                x0, y0, x1, y1 = bbox
                cv2.rectangle(self.image, (x0, y0), (x1, y1), RECTANGLE_COMPLETE_COLOR, RECTANGLE_WIDTH)
                self.write_text(field, (x0, y1 + FIELD_TEXT_Y_SHIFT))
                self.write_text(text, (x0 - CONTENT_TEXT_SHIFT, y0 - CONTENT_TEXT_SHIFT))
                self.increment_field_index()
                self.set_field()
                self.set_image_states(self.image)

    def _empty_annotation(self):
        self.annotation_json = self.template_json

    def _empty_image_states(self):
        self.image_states = deque([])

    def _get_template_json(self, template_json_file):
        return read_json(template_json_file)

    def _init_n_completed(self):
        self.annotation_files = glob.glob(os.path.join(self.annotations_dir, '*' + ANNOTATION_FILE_EXTENSION))
        for annotation_file in self.annotation_files:
            try:
                annotation = read_json(annotation_file)
            except PermissionError as e:
                print(e)
                continue
            for key in list(annotation.keys()):
                is_bbox_completed = annotation[key]['bbox'] != []
                is_content_completed = annotation[key]['content'] != ''
                key_completed = is_bbox_completed and is_content_completed
                if not key_completed:
                    break
            else:
                self.n_completed += 1

    def _read_cache(self):
        with open(self.cache_file, 'r') as f:
            lines = f.readlines()
        last_image_index = 0
        if len(lines) > 0:
            last_filename = lines[0].strip()
            try:
                last_image_index = self.image_filenames.index(last_filename)
            except ValueError:
                pass
        return last_image_index

    def _set_annotation(self):
        image_filename_wo_extension = self.image_filenames_wo_extension[self.image_index]
        self.annotation_file = os.path.join(self.annotations_dir,
                image_filename_wo_extension + '.' + ANNOTATION_FILE_EXTENSION)
        if not os.path.isfile(self.annotation_file):
            shutil.copyfile(self.template_json_file, self.annotation_file)
        try:
            self.annotation_json = read_json(self.annotation_file)
        except Exception as e:
            print(e)
            self.annotation_json = read_json(self.template_annotation_file)
        self.fields = list(self.annotation_json.keys())
        self.n_fields = len(self.fields)
        self.field_index = 0
        self.full = self.field_index == self.n_fields
        self.set_field()

    def _set_annotation_files(self):
        self.annotations_dir = os.path.join(self.dataset_dir, ANNOTATIONS_DIRNAME)
        os.makedirs(self.annotations_dir, exist_ok=True)
        self.annotation_files = glob.glob(os.path.join(self.annotations_dir, '*' + ANNOTATION_FILE_EXTENSION))

    def _set_cache_file(self):
        self.cache_file = os.path.abspath(os.path.join(self.dataset_dir, CACHE_FILENAME))
        if not os.path.isfile(self.cache_file):
            with open(self.cache_file, 'w'):
                pass

    def _set_image_index(self, image_index):
        self.image_index = image_index % self.n_image_files

    def _set_image_files(self):
        images_dir = os.path.join(self.dataset_dir, IMAGES_DIRNAME)
        if not os.path.isdir(images_dir):
            print(f'{images_dir} was not found. Exiting.')
            sys.exit()
        self.image_files = sorted(glob.glob(os.path.join(images_dir, '*' + IMAGE_FILE_EXTENSION)))
        self.image_filenames = list(map(os.path.basename, self.image_files))
        self.image_filenames_wo_extension = list(map(lambda s: s.split('.')[0], self.image_filenames))
        self.n_image_files = len(self.image_files)
        if self.n_image_files == 0:
            print(f'{self.n_image_files} images found in {images_dir} . Exiting.')
            sys.exit()
        print(f'{self.n_image_files} images found in {images_dir}')

    def _set_template_json(self):
        self.template_json_file = os.path.abspath(os.path.join(self.dataset_dir, TEMPLATE_FILENAME))
        if not os.path.isfile(self.template_json_file):
            print(f'{self.template_json_file} was not found. Exiting.')
            sys.exit()
        self.template_json = self._get_template_json(self.template_json_file)

    def clean(self):
        self.set_image(self.image_states[0])
        self._empty_image_states()
        self.set_image_states(self.image)
        self.template_json = self._get_template_json(self.template_json_file)
        self._empty_annotation()
        self.write_annotation()
        self.field_index = 0
        self.set_field()
        self.decrement_n_completed()

    def decrement_image_index(self):
        self._set_image_index(self.image_index - 1)

    def decrement_field_index(self):
        self.field_index -= 1
        self.field_index = max(0, self.field_index)
        self.full = self.field_index == self.n_fields

    def decrement_n_completed(self):
        self.n_completed -= 1

    def increment_image_index(self):
        self._set_image_index(self.image_index + 1)

    def increment_field_index(self):
        self.field_index += 1
        self.field_index = min(self.field_index, self.n_fields)
        self.full = self.field_index == self.n_fields

    def increment_n_completed(self):
        self.n_completed += 1

    def is_full(self):
        return self.full

    def get_image(self):
        self.image_file = self.image_files[self.image_index]
        self.image_filename = self.image_filenames[self.image_index]
        self._empty_image_states()
        self._set_annotation()
        self.image = read_image(self.image_file, convert_color=COLOR_CONVERSION)
        self.image = resize(self.image, width=WIDTH_DISPLAY, height=None)
        self.image_h, self.image_w = self.image.shape[:2]
        self.set_image_states(self.image)
        if self.n_fields > 0:
            self._apply_annotation()
        else:
            self.set_image_states(self.image)
        self.set_window_name(self.image_filename)
        return self.image

    def set_image(self, image):
        self.image = image.copy()

    def set_image_states(self, image):
        self.image_states.append(image.copy())
        if len(self.image_states) > N_MAX_STATES:
            self.image_states.popleft()

    def set_field(self):
        if self.field_index == self.n_fields:
            self.full = True
            self.field = None
        else:
            self.full = False
            self.field = self.fields[self.field_index]

    def set_last_image(self):
        if len(self.image_states) > 1:
            self.set_image(self.image_states[-2])
            self.image_states.pop()
        elif len(self.image_states) == 1:
            self.set_image(self.image_states[-1])
        else:
            raise IndexError

    def set_window_name(self, image_filename):
        completion = self.n_completed / self.n_image_files
        completion_str = str(round(100 * completion, 1)) + '%'
        self.window_name = BASE_WINDOW_NAME + '  ' + \
                image_filename + '  ' + \
                '(' + str(self.image_index + 1) + '/' + \
                str(self.n_image_files) + ')' + '  ' + \
                'Completion:' + completion_str

    def undo(self):
        if len(self.image_states) > 1:
            self.set_image(self.image_states[-2])
            self.image_states.pop()
        self.decrement_field_index()
        self.decrement_n_completed()
        self.set_field()
        self.annotation_json[self.field]['bbox'] = []
        self.annotation_json[self.field]['content'] = ''
        self.write_annotation()

    def write_annotation(self):
        write_json(self.annotation_json, self.annotation_file, indent=JSON_INDENTATION)

    def write_cache(self, text):
        try:
            with open(self.cache_file, 'w') as f:
                f.write(text + '\n')
        except PermissionError as e:
            print(e)

    def write_text(self, text, loc):
        cv2.putText(self.image, text, loc,
                FONT,
                FONT_SCALE,
                FONT_COLOR,
                RECTANGLE_WIDTH,
                cv2.LINE_AA)

def draw_rectangle(event, x, y, flags, param):
    global image_view, x0, y0, x1, y1, \
            full, drawing, writing, rect_start, text, field

    if not full:
        if event == cv2.EVENT_LBUTTONDOWN:
            drawing = True
            rect_start = True
            text = ''
            x0, y0 = x, y
        elif event == cv2.EVENT_MOUSEMOVE:
            if drawing == True:
                if not rect_start:
                    image_view.set_last_image()
                else:
                    rect_start = False
                cv2.rectangle(image_view.image, (x0, y0), (x, y), \
                        RECTANGLE_WAIT_COLOR, RECTANGLE_WIDTH)
                image_view.set_image_states(image_view.image)
        elif event == cv2.EVENT_LBUTTONUP:
            drawing = False
            writing = True

            ## Swap x, y orders if rectangle is drawn reverse and fix out-of-bounds
            if x < x0:
                x0, x = x, x0
            if y < y0:
                y0, y = y, y0
            x0, x, y0, y = max(0, x0), max(0, x), max(0, y0), max(0, y)
            x0, x = min(image_view.image_w, x0), min(image_view.image_w, x)
            y0, y = min(image_view.image_h, y0), min(image_view.image_h, y)

            normalized_bbox_coords = (x0 / image_view.image_w, \
                                      y0 / image_view.image_h, \
                                      x / image_view.image_w, \
                                      y / image_view.image_h)
            normalized_bbox_coords = list(map(lambda x: round(x, BBOX_RATIO_PRECISION), \
                    normalized_bbox_coords))
            image_view.annotation_json[field]['bbox'] = normalized_bbox_coords
            image_view.set_last_image()
            cv2.rectangle(image_view.image, (x0, y0), (x, y), \
                    RECTANGLE_WAIT_COLOR, RECTANGLE_WIDTH)
            x1, y1 = x, y
            image_view.write_text(field, (x0, y + FIELD_TEXT_Y_SHIFT))  ## Write field below

    return image_view.image

def write(char):
    global image_view, x0, y0, writing, text

    length_text = len(text)
    char_loc = (x0 + image_view.text_space * (length_text - 1) - CONTENT_TEXT_SHIFT, y0 - CONTENT_TEXT_SHIFT)
    cv2.putText(image_view.image, char, char_loc,
            FONT,
            FONT_SCALE,
            FONT_COLOR,
            RECTANGLE_WIDTH,
            cv2.LINE_AA)

if __name__ == '__main__':
    ## Get dataset directory (if not given get first one under 'dataset')
    if len(sys.argv) == 2:
        dataset_dir = sys.argv[1]
    else:
        dataset_dir = sorted(glob.glob(os.path.join('.', 'dataset', '*')))[0]

    ## Set image file and callbacks
    image_view = ImageView(dataset_dir)
    field = image_view.field
    full = image_view.is_full()
    cv2.namedWindow(BASE_WINDOW_NAME, cv2.WINDOW_KEEPRATIO)
    cv2.setMouseCallback(BASE_WINDOW_NAME, draw_rectangle)
    cv2.setWindowTitle(BASE_WINDOW_NAME, image_view.window_name)

    ## View main loop
    while True:
        cv2.imshow(BASE_WINDOW_NAME, image_view.image)
        key = cv2.waitKey(1) & 0xFF

        ## Escape with 'Esc' or 'q'
        if key in [27, ord('q')]:
            image_view.write_cache(image_view.image_filename)
            break

        ## Close from 'X' button
        try:
            if cv2.getWindowProperty(BASE_WINDOW_NAME, cv2.WND_PROP_AUTOSIZE) == -1:
                image_view.write_cache(image_view.image_filename)
                break
        except Exception as e:
            print(e)
            image_view.write_cache(image_view.image_filename)
            break

        ## Go previous or next image
        if key in [ord('a'), ord('d'), ord('A'), ord('D')]:
            if key in [ord('a'), ord('A')]:
                image_view.decrement_image_index()
            elif key in [ord('d'), ord('D')]:
                image_view.increment_image_index()
            image = image_view.get_image()
            image_view.set_image(image)
            drawing = False
            writing = False
            x0, y0 = -1, -1
            text = ''
            field = image_view.field
            full = image_view.is_full()
            cv2.setWindowTitle(BASE_WINDOW_NAME, image_view.window_name)
            image_view.write_cache(image_view.image_filename)

        ## Write label
        if writing and key in ORD_DIGITS:
            digit_str = chr(key)
            text += digit_str
            write(digit_str)

        # ## Delete label with 'backspace' in writing mode
        # if writing and key == 8:
        #     text = text[:-1]
        #     image_view.set_last_image()

        ## Undo
        if key in [ord('z'), ord('Z')]:
            image_view.undo()
            field = image_view.field
            full = image_view.is_full()
            image_view.set_window_name(image_view.image_filename)
            cv2.setWindowTitle(BASE_WINDOW_NAME, image_view.window_name)

        ## Clean
        if (not writing) and (key in [ord('c'), ord('C')]):
            image_view.clean()
            field = image_view.field
            full = image_view.is_full()
            image_view.set_window_name(image_view.image_filename)
            cv2.setWindowTitle(BASE_WINDOW_NAME, image_view.window_name)

        ## Go out from writing mode with 'enter'
        if writing and key == 13:
            writing = False
            image_view.annotation_json[field]['content'] = text
            image_view.write_annotation()
            text = ''
            image_view.increment_field_index()
            image_view.set_field()
            field = image_view.field
            full = image_view.is_full()
            if full:
                image_view.increment_n_completed()
            cv2.rectangle(image_view.image, (x0, y0), (x1, y1), \
                    RECTANGLE_COMPLETE_COLOR, RECTANGLE_WIDTH)
            image_view.set_window_name(image_view.image_filename)
            cv2.setWindowTitle(BASE_WINDOW_NAME, image_view.window_name)
            image_view.set_image_states(image_view.image)

    cv2.destroyAllWindows()