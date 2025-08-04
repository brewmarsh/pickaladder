from PIL import Image, ImageDraw, ImageFont
import io

import os

def generate_profile_picture(name):
    """
    Generates a profile picture with the user's initials.
    """
    # Get the absolute path to the static directory
    static_dir = os.path.join(os.path.dirname(__file__), '..', 'static')
    img = Image.open(os.path.join(static_dir, 'user_icon.png')).convert("RGB")
    d = ImageDraw.Draw(img)
    initials = "".join([name[0]for name in name.split()])

    # Use a truetype font
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 120)
    except IOError:
        font = ImageFont.load_default()

    # Center the text
    bbox = font.getbbox(initials)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    position = ((256 - text_width) / 2, (256 - text_height) / 2)

    d.text(position, initials, fill=(255, 255, 0), font=font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    profile_picture_data = buf.getvalue()

    img.thumbnail((64, 64))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    thumbnail_data = buf.getvalue()

    return profile_picture_data, thumbnail_data
