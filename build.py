import datetime
import pathlib
import itertools
import subprocess
import json
import yaml

import PIL.Image
import jinja2

BUCKET = "files.thea.codes"
THUMBNAIL_SIZE = (1024, 768)
EXIF_TAGS = {
    "Make": "make",
    "Model": "model",
    "ExposureTime": "exposure",
    "FNumber": "f",
    "ISO": "iso",
    "DateTimeOriginal": "datetime",
    "FocalLength": "focal_length",
    "Lens": "lens",
    "LensInfo": "lens",
    "LensModel": "lens",
    "ShutterSpeed": "shutter",
    "HistorySoftwareAgent": "edited_with",
}
GSUTIL_PATH = str(pathlib.Path("~/google-cloud-sdk/bin/gsutil").expanduser())


jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader('templates'),
)
photos_dir = pathlib.Path("photos")
info_dir = pathlib.Path("info")
thumbnail_dir = pathlib.Path("thumbnails")


def extract_exif(photo_path):
    output = {}

    raw_exif_data = json.loads(subprocess.check_output(["exiftool", "-json", str(photo_path)]))[0]

    for key, val in raw_exif_data.items():
        if key in EXIF_TAGS:
            output[EXIF_TAGS[key]] = val

    return output


def thumbnail(photo_path):
    thumbnail_path = thumbnail_dir / photo_path.parent.name / photo_path.name
    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)

    im = PIL.Image.open(photo_path)
    im.thumbnail(THUMBNAIL_SIZE)
    im.save(str(thumbnail_path))

    im.close()

    return thumbnail_path


def process_photos():
    """Process new photos

    - Create info files
    - Create thumbnails
    - Upload to cloud
    """
    new_photos = itertools.chain(
        photos_dir.rglob("*.jpg"), photos_dir.rglob("*.jpeg"), photos_dir.rglob("*.JPG"))

    for photo_path in new_photos:
        date = photo_path.parent.name
        info_dst = info_dir / date / (photo_path.name.lower() + ".yaml")
        info_dst.parent.mkdir(exist_ok=True)

        if info_dst.exists():
            continue

        print(f"Processing {photo_path}.")
        
        # Read the EXIF data
        exif = extract_exif(photo_path)

        # Create the thumbnail image
        thumbnail_path = thumbnail(photo_path)

        # Set the thumbnail and full size locations.
        exif["thumbnail_url"] = str(thumbnail_path)
        exif["full_url"] = str(photo_path)

        # Write out the info.
        with info_dst.open("w") as fh:
            yaml.dump(exif, fh)


def upload_photos():
    subprocess.check_call([
        GSUTIL_PATH, "-m", "rsync", "-r", str(photos_dir), f"gs://{BUCKET}/photos"])
    subprocess.check_call([
        GSUTIL_PATH, "-m", "rsync", "-r", str(thumbnail_dir), f"gs://{BUCKET}/thumbnails"])


def generate_index():
    photos = []
    info_files = pathlib.Path("info").rglob("*.yaml")

    for info_file in info_files:
        with info_file.open("r") as fh:
            info = yaml.safe_load(fh)
            info["datetime"] = datetime.datetime.strptime(info["datetime"], "%Y:%m:%d %H:%M:%S")
            photos.append(info)

    photos.sort(key=lambda x: x["datetime"], reverse=True)

    template = jinja_env.get_template('index.html')
    rendered = template.render(
        storage_root=f"https://storage.googleapis.com/{BUCKET}/",
        photos=photos)
    pathlib.Path("docs/index.html").write_text(rendered)

def main():
    process_photos()
    upload_photos()
    generate_index()


if __name__ == '__main__':
    main()
