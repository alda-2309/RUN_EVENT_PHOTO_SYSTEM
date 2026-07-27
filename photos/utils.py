from PIL import Image
from PIL import ImageDraw


def add_watermark(photo_path):

    image = Image.open(photo_path)

    draw = ImageDraw.Draw(image)

    draw.text(
        (20, 20),
        "Run Event 2026",
        fill="white"
    )

    image.save(photo_path)