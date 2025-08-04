from PIL import Image, ImageDraw, ImageFont
import io

def generate_profile_picture(name):
    """
    Generates a profile picture with the user's initials.
    """
    img = Image.new("RGB", (256, 256), color=(73, 109, 137))
    d = ImageDraw.Draw(img)
    initials = "".join([name[0] for name in name.split()])

    # Use a truetype font
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 120)
    except IOError:
        font = ImageFont.load_default()

    # Center the text
    text_width, text_height = d.textsize(initials, font=font)
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
