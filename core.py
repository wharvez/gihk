import time, os, pyperclip, helpers, random, pytesseract
from ahk import AHK

ahk = AHK()
image_types = {'main': "\"poster\"", 'scene': "\"scene\" -youtube -poster"}
bad_sources = ['shutterstock', 'alamy', 'agefotostock', 'gettyimages', 'granger']
images_dir = os.path.join(helpers.gihk_dir, 'images')


def rightclick_menu(ups):
    ahk.key_press('AppsKey')
    time.sleep(1)
    for _ in range(ups):
        ahk.key_press('Up')
        time.sleep(0.2)
    ahk.key_press('Enter')
    time.sleep(0.5)


def load_chrome_get_win():
    ahk.run_script('Run Chrome')
    time.sleep(0.5)
    win = ahk.find_window(title=b'New Tab')
    win.activate()
    win.maximize()
    time.sleep(0.5)
    ahk.type("https://images.google.com/")
    ahk.key_press('Enter')
    time.sleep(1.5)
    win.activate()
    time.sleep(0.5)
    return win


def submit_query(query):
    ahk.type(query)
    ahk.key_press('Enter')
    time.sleep(3)
    ahk.mouse_move(0, 0, relative=False)
    time.sleep(0.5)


def select_first_img(img_pos):
    for _ in range(img_pos):
        ahk.key_press('Right')
        time.sleep(0.5)
    time.sleep(0.5)
    ahk.key_press('Enter')
    time.sleep(1)


class FilmRecord:
    def __init__(self) -> None:
        self.images = []


    def set_ty_from_query(self, data: str):
        year_re = helpers.get_year_re(data[-4:])
        if year_re:
            self.year = year_re.group()
            self.title = data[:-4].strip()
    

    def set_ty_from_file(self, data: dict):
        self.title = data.get('name')
        self.year = data.get('year')


    def get_query(self, image_type) -> str:
        return f"{self.title} {self.year} film {image_types[image_type]}"


class ImageRecord:
    def __init__(self, width=None, height=None, imgtype=None, url=None, imgpath=None, text=None, conf=None) -> None:
        self.width = width
        self.height = height
        self.imgtype = imgtype
        self.url = url
        self.imgpath = imgpath
        self.text = text
        self.conf = conf
    

    def check_size(self):
        if self.width and self.height:
            a = self.width * self.height
            return a < 100000


    def check_text(self):
        if self.text and self.conf:
            sum_text = sum(1 for t in self.text if t)
            sum_conf = sum(1 for c in self.conf if float(c) > 95)
            return sum_text > 0 and sum_conf > 0


class Collector:
    def __init__(self, **kwargs):
        self.films = []
        self.alt_map = kwargs.get('alt_map')
        self.qr = kwargs.get('queries_range') or 0
        self.rand = kwargs.get('rand')
        queries = kwargs.get('queries')
        if queries:
            self.populate_films(queries, 'set_ty_from_query')
        else:
            file_path = os.path.join(helpers.gihk_dir, 'films_artblog.json')
            file_films = helpers.read_json_file(file_path)
            self.populate_films(file_films, 'set_ty_from_file')


    def populate_films(self, indices_range_src, fr_meth):
        if not self.qr or self.qr > len(indices_range_src):
            self.qr = len(indices_range_src)
        indices = [i for i in range(len(indices_range_src))]
        if self.rand:
            random.shuffle(indices)
        for j in range(self.qr):
            fr = FilmRecord()
            getattr(fr, fr_meth)(indices_range_src[indices[j]])
            self.films.append(fr)


    def get_first_img(self, ft, it):
        if self.alt_map:
            alt_first = self.alt_map.get((ft, it))
        else:
            alt_first = None
        return alt_first or 1


    def save_images(self):
        for film in self.films:
            output_dirname = film.title.replace(' ', '_')
            output_dir = os.path.join(images_dir, output_dirname)
            if not os.path.exists(output_dir):
                os.mkdir(output_dir)
            for it in image_types:
                first_img = self.get_first_img(film.title.lower(), it)
                win = load_chrome_get_win()
                submit_query(film.get_query(it))
                select_first_img(first_img)
                saved_images_counter = small_images = text_scenes = gf_fails = bs_fails = 0
                while True:
                    rightclick_menu(4)  # Copy img url
                    imgurl = pyperclip.paste()
                    if not imgurl.startswith('data'):
                        print(film.title, imgurl)
                        if not any(bad_source in imgurl for bad_source in bad_sources):
                            filename = helpers.get_filename(imgurl, output_dirname)  # Attempt to download image
                            if not filename:
                                gf_fails += 1
                                rightclick_menu(7)  # For some reason, opening the image in a new tab after the image download fails sometimes stops 403 errors occurring
                                time.sleep(1)
                                filename = helpers.get_filename(imgurl, output_dirname)  # Try one more time
                            if filename:
                                saved_images_counter += 1
                                rightclick_menu(5)  # Copy img
                                clipimg = None
                                clipimg_tries = 0
                                while not clipimg and clipimg_tries < 5:
                                    clipimg_tries += 1
                                    print(f'waiting {clipimg_tries} seconds before trying to access copied {it} image for {film.title}')
                                    time.sleep(clipimg_tries)
                                    clipimg = helpers.get_clipimg()
                                imgdata = {}
                                if clipimg:
                                    width, height = clipimg.size
                                    imgdata.update(w=width, h=height)
                                    imgdata.update(pytesseract.image_to_data(clipimg, output_type=pytesseract.Output.DICT))
                                image = ImageRecord(width=imgdata.get('w'), height=imgdata.get('h'), imgtype=it, url=imgurl, text=imgdata.get('text'), conf=imgdata.get('conf'))
                                new_filename = f'{it}_{saved_images_counter}'
                                if image.check_size():
                                    new_filename += '_small'
                                if image.check_text():
                                    new_filename += '_text'
                                new_filename += '.jpg'
                                imgpath = os.path.join(output_dir, new_filename)
                                image.imgpath = imgpath
                                film.images.append(image)
                                os.replace(filename, imgpath)
                                if not (it == 'scene' and image.check_text()) and not image.check_size():
                                    break
                                else:
                                    if image.check_size():
                                        small_images += 1
                                        print(film.title, it, f'small images: {small_images}')
                                    if it == 'scene' and image.check_text():
                                        text_scenes += 1
                                        print(film.title, f'text scenes: {text_scenes}')
                            else:
                                gf_fails += 1
                                print(film.title, it, f'get_filename fails: {gf_fails}')
                        else:
                            bs_fails += 1
                            print(film.title, it, f'bad source fails: {bs_fails}')
                        ahk.key_press('Right')
                    else:
                        print(film.title, 'data:image')
                    time.sleep(0.5)  # For some reason, if you keep copying the image address, eventually it gives you the unmasked version that doesn't start with 'data'.
                win.kill()
                time.sleep(0.5)
                pyperclip.copy('')


    def save_collection(self):
        file_path = os.path.join(helpers.gihk_dir, 'collection.json')
        helpers.write_json_file(file_path, self.films)
