"""Opens uploaded images: OpenSlide for scans (.svs, tiled .tif/.tiff), Pillow for everything else."""

from pathlib import Path

import openslide
from PIL import Image, ImageOps

SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".svs")
UNREADABLE = "Could not read this file. It may be corrupted or not a valid image."


class IngestError(ValueError):
    """A file the app can't use. The API returns its message with a 400."""


class Slide:
    """A whole image in original (level-0) pixels, plus its scale in µm per pixel."""

    def __init__(self, width, height, mpp, mpp_estimated):
        self.width, self.height = width, height
        self.mpp, self.mpp_estimated = mpp, mpp_estimated

    def read_region(self, x, y, size, out_px):
        """The size×size square at (x, y), resized to out_px×out_px RGB."""
        raise NotImplementedError

    def thumbnail(self, size):
        """The whole image resized to exactly `size` (width, height), RGB."""
        raise NotImplementedError


class PillowSlide(Slide):
    def __init__(self, image, mpp, mpp_estimated):
        super().__init__(image.width, image.height, mpp, mpp_estimated)
        self.image = image

    def read_region(self, x, y, size, out_px):
        return self.image.crop((x, y, x + size, y + size)).resize((out_px, out_px), Image.BILINEAR)

    def thumbnail(self, size):
        return self.image.resize(size, Image.BILINEAR)


class OpenSlideSlide(Slide):
    def __init__(self, osr, mpp, mpp_estimated):
        super().__init__(*osr.dimensions, mpp, mpp_estimated)
        self.osr = osr

    def read_region(self, x, y, size, out_px):
        level = self.osr.get_best_level_for_downsample(size / out_px)
        n = max(1, round(size / self.osr.level_downsamples[level]))
        region = self.osr.read_region((x, y), level, (n, n))
        return to_rgb(region).resize((out_px, out_px), Image.BILINEAR)

    def thumbnail(self, size):
        return self.osr.get_thumbnail(size).convert("RGB").resize(size, Image.BILINEAR)


def to_rgb(image):
    """RGB on a white background, so transparent areas read as blank glass."""
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        image = image.convert("RGBA")
        white = Image.new("RGBA", image.size, (255, 255, 255, 255))
        return Image.alpha_composite(white, image).convert("RGB")
    return image.convert("RGB")


def parse_mpp(value):
    try:
        mpp = float(value)
    except (TypeError, ValueError):
        mpp = 0.0
    if not mpp > 0:
        raise IngestError("Image scale must be a positive number of µm per pixel.")
    return mpp


def open_slide(path, user_mpp=None, default_mpp=None):
    """Open an upload. A scan's own mpp wins; otherwise the typed mpp, then the default, marked estimated."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise IngestError(f"Unsupported file type '{ext or path.name}'. Upload a PNG, JPEG, TIFF or SVS image.")
    if user_mpp not in (None, ""):
        user_mpp = parse_mpp(user_mpp)
    else:
        user_mpp = None
    fallback_mpp = user_mpp or default_mpp

    if ext in (".svs", ".tif", ".tiff"):
        try:
            osr = openslide.OpenSlide(str(path))
        except openslide.OpenSlideUnsupportedFormatError as e:
            if ext == ".svs":
                raise IngestError(UNREADABLE) from e
            osr = None  # a plain (untiled) TIFF: Pillow reads it below
        except openslide.OpenSlideError as e:
            raise IngestError(UNREADABLE) from e
        if osr is not None:
            scan_mpp = osr.properties.get(openslide.PROPERTY_NAME_MPP_X)
            if scan_mpp:
                return OpenSlideSlide(osr, float(scan_mpp), False)
            return OpenSlideSlide(osr, fallback_mpp, True)

    try:
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image)
            image.load()
            image = to_rgb(image)
    except Image.DecompressionBombError as e:
        raise IngestError("This image is too large to open as a flat image. Upload it as an SVS or tiled TIFF.") from e
    except (OSError, ValueError, SyntaxError) as e:
        raise IngestError(UNREADABLE) from e
    return PillowSlide(image, fallback_mpp, True)
