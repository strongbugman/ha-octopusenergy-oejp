"""Generate non-official Option A brand assets for the OEJP integration.

The artwork is intentionally original: a cute pink cartoon octopus combined
with a yellow lightning bolt, drawn entirely with Pillow on a transparent
background.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "assets"
ICON_PATH = ASSETS_DIR / "icon.png"
LOGO_PATH = ASSETS_DIR / "logo.png"

SCALE = 4
TRANSPARENT = (0, 0, 0, 0)

PINK_TOP = (255, 154, 190, 255)
PINK = (255, 88, 139, 255)
PINK_DEEP = (204, 42, 105, 255)
PINK_SHADOW = (122, 28, 82, 95)
PURPLE = (58, 32, 76, 255)
PURPLE_SOFT = (94, 58, 122, 255)
INK = (39, 29, 48, 255)
WHITE = (255, 255, 255, 255)
YELLOW_TOP = (255, 245, 107, 255)
YELLOW = (255, 207, 47, 255)
AMBER = (236, 139, 25, 255)
CHEEK = (255, 112, 159, 135)


Point = tuple[float, float]


def sc(value: float, scale: int = SCALE) -> int:
    return int(round(value * scale))


def sbox(box: Sequence[float], scale: int = SCALE) -> tuple[int, int, int, int]:
    return tuple(sc(v, scale) for v in box)  # type: ignore[return-value]


def spoints(points: Iterable[Point], scale: int = SCALE) -> list[tuple[int, int]]:
    return [(sc(x, scale), sc(y, scale)) for x, y in points]


def lerp(a: int, b: int, t: float) -> int:
    return int(round(a + (b - a) * t))


def lerp_color(left: Sequence[int], right: Sequence[int], t: float) -> tuple[int, int, int, int]:
    return tuple(lerp(left[i], right[i], t) for i in range(4))  # type: ignore[return-value]


def vertical_gradient(
    size: tuple[int, int],
    top: Sequence[int],
    bottom: Sequence[int],
) -> Image.Image:
    width, height = size
    image = Image.new("RGBA", size, TRANSPARENT)
    draw = ImageDraw.Draw(image)
    denominator = max(height - 1, 1)
    for y in range(height):
        draw.line((0, y, width, y), fill=lerp_color(top, bottom, y / denominator))
    return image


def horizontal_gradient(
    size: tuple[int, int],
    left: Sequence[int],
    right: Sequence[int],
) -> Image.Image:
    width, height = size
    image = Image.new("RGBA", size, TRANSPARENT)
    draw = ImageDraw.Draw(image)
    denominator = max(width - 1, 1)
    for x in range(width):
        draw.line((x, 0, x, height), fill=lerp_color(left, right, x / denominator))
    return image


def alpha_composite_masked(base: Image.Image, color_image: Image.Image, mask: Image.Image) -> None:
    layer = color_image.copy()
    layer.putalpha(mask)
    base.alpha_composite(layer)


def ellipse_gradient(
    base: Image.Image,
    box: Sequence[float],
    top_color: Sequence[int],
    bottom_color: Sequence[int],
    *,
    scale: int = SCALE,
) -> None:
    mask = Image.new("L", base.size, 0)
    ImageDraw.Draw(mask).ellipse(sbox(box, scale), fill=255)
    alpha_composite_masked(base, vertical_gradient(base.size, top_color, bottom_color), mask)


def polygon_gradient(
    base: Image.Image,
    points: Sequence[Point],
    top_color: Sequence[int],
    bottom_color: Sequence[int],
    *,
    scale: int = SCALE,
) -> None:
    mask = Image.new("L", base.size, 0)
    ImageDraw.Draw(mask).polygon(spoints(points, scale), fill=255)
    alpha_composite_masked(base, vertical_gradient(base.size, top_color, bottom_color), mask)


def blurred_shape_layer(
    size: tuple[int, int],
    *,
    blur: float,
    scale: int = SCALE,
) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    layer = Image.new("RGBA", size, TRANSPARENT)
    return layer, ImageDraw.Draw(layer)


def paste_blurred(base: Image.Image, layer: Image.Image, blur: float, *, scale: int = SCALE) -> None:
    base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(sc(blur, scale))))


def cubic_point(p0: Point, p1: Point, p2: Point, p3: Point, t: float) -> Point:
    one = 1.0 - t
    x = one**3 * p0[0] + 3 * one**2 * t * p1[0] + 3 * one * t**2 * p2[0] + t**3 * p3[0]
    y = one**3 * p0[1] + 3 * one**2 * t * p1[1] + 3 * one * t**2 * p2[1] + t**3 * p3[1]
    return x, y


def cubic_path(p0: Point, p1: Point, p2: Point, p3: Point, steps: int = 36) -> list[Point]:
    return [cubic_point(p0, p1, p2, p3, i / steps) for i in range(steps + 1)]


def draw_round_polyline(
    draw: ImageDraw.ImageDraw,
    points: Sequence[Point],
    *,
    width: float,
    fill: Sequence[int],
    scale: int = SCALE,
) -> None:
    scaled = spoints(points, scale)
    scaled_width = sc(width, scale)
    try:
        draw.line(scaled, fill=tuple(fill), width=scaled_width, joint="curve")
    except TypeError:
        draw.line(scaled, fill=tuple(fill), width=scaled_width)

    radius = scaled_width // 2
    for x, y in (scaled[0], scaled[-1]):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=tuple(fill))


def offset_points(points: Sequence[Point], dx: float, dy: float) -> list[Point]:
    return [(x + dx, y + dy) for x, y in points]


def draw_tentacle(
    base: Image.Image,
    path: Sequence[Point],
    *,
    width: float,
    scale: int = SCALE,
) -> None:
    shadow_layer, shadow_draw = blurred_shape_layer(base.size, blur=8, scale=scale)
    draw_round_polyline(
        shadow_draw,
        offset_points(path, 3, 8),
        width=width + 5,
        fill=PINK_SHADOW,
        scale=scale,
    )
    paste_blurred(base, shadow_layer, blur=5, scale=scale)

    draw = ImageDraw.Draw(base)
    draw_round_polyline(draw, path, width=width, fill=PINK_DEEP, scale=scale)
    draw_round_polyline(draw, offset_points(path, -1.5, -2.5), width=width - 7, fill=PINK, scale=scale)
    draw_round_polyline(
        draw,
        offset_points(path[: max(3, len(path) // 2)], -4, -5),
        width=max(width * 0.22, 5),
        fill=(255, 182, 207, 105),
        scale=scale,
    )


def draw_suction_cups(
    base: Image.Image,
    cups: Sequence[tuple[float, float, float]],
    *,
    scale: int = SCALE,
) -> None:
    draw = ImageDraw.Draw(base)
    for x, y, radius in cups:
        draw.ellipse(
            sbox((x - radius - 1, y - radius + 2, x + radius + 1, y + radius + 2), scale),
            fill=(170, 32, 94, 90),
        )
        draw.ellipse(
            sbox((x - radius, y - radius, x + radius, y + radius), scale),
            fill=(255, 183, 207, 230),
        )
        inner = radius * 0.43
        draw.ellipse(
            sbox((x - inner, y - inner, x + inner, y + inner), scale),
            fill=(255, 111, 164, 135),
        )


def draw_lightning(
    base: Image.Image,
    points: Sequence[Point],
    *,
    outline_width: float = 4.5,
    glow: float = 15,
    scale: int = SCALE,
) -> None:
    glow_layer, glow_draw = blurred_shape_layer(base.size, blur=glow, scale=scale)
    glow_draw.polygon(spoints(points, scale), fill=(255, 210, 46, 118))
    paste_blurred(base, glow_layer, blur=glow, scale=scale)

    shadow_layer, shadow_draw = blurred_shape_layer(base.size, blur=6, scale=scale)
    shadow_draw.polygon(spoints(offset_points(points, 4, 6), scale), fill=(125, 72, 12, 105))
    paste_blurred(base, shadow_layer, blur=5, scale=scale)

    polygon_gradient(base, points, YELLOW_TOP, YELLOW, scale=scale)

    draw = ImageDraw.Draw(base)
    closed = spoints([*points, points[0]], scale)
    try:
        draw.line(closed, fill=AMBER, width=sc(outline_width, scale), joint="curve")
    except TypeError:
        draw.line(closed, fill=AMBER, width=sc(outline_width, scale))

    highlight = [points[0], points[1], points[2]]
    draw.line(spoints(highlight, scale), fill=(255, 255, 214, 165), width=sc(2.1, scale))


def draw_icon_art(scale: int = SCALE) -> Image.Image:
    size = (512 * scale, 512 * scale)
    base = Image.new("RGBA", size, TRANSPARENT)

    halo_layer, halo_draw = blurred_shape_layer(size, blur=18, scale=scale)
    halo_draw.ellipse(sbox((86, 89, 425, 411), scale), fill=(255, 86, 144, 54))
    halo_draw.polygon(
        spoints([(368, 43), (291, 180), (348, 172), (305, 291), (442, 135), (379, 149)], scale),
        fill=(255, 220, 68, 76),
    )
    paste_blurred(base, halo_layer, blur=16, scale=scale)

    tentacles = [
        cubic_path((181, 322), (86, 335), (77, 420), (148, 433)),
        cubic_path((222, 340), (167, 379), (188, 450), (248, 427)),
        cubic_path((258, 350), (250, 414), (295, 458), (326, 407)),
        cubic_path((310, 338), (381, 365), (389, 435), (334, 442)),
        cubic_path((344, 318), (434, 330), (442, 403), (383, 424)),
    ]
    widths = [39, 38, 42, 38, 38]
    for path, width in zip(tentacles, widths, strict=True):
        draw_tentacle(base, path, width=width, scale=scale)

    body_box = (108, 103, 404, 373)
    body_shadow, body_shadow_draw = blurred_shape_layer(size, blur=9, scale=scale)
    body_shadow_draw.ellipse(sbox((112, 115, 410, 385), scale), fill=(122, 28, 82, 95))
    paste_blurred(base, body_shadow, blur=8, scale=scale)

    ellipse_gradient(base, body_box, PINK_TOP, PINK_DEEP, scale=scale)

    draw = ImageDraw.Draw(base)
    draw.ellipse(sbox(body_box, scale), outline=(190, 40, 99, 190), width=sc(3.2, scale))
    draw.ellipse(sbox((154, 126, 297, 210), scale), fill=(255, 209, 224, 54))
    draw.arc(sbox((124, 118, 392, 365), scale), start=205, end=338, fill=(255, 205, 223, 95), width=sc(4, scale))

    draw_suction_cups(
        base,
        [
            (125, 407, 8),
            (153, 420, 6.5),
            (213, 417, 7),
            (244, 421, 5.5),
            (292, 421, 6),
            (322, 398, 7),
            (365, 421, 6.5),
            (392, 402, 5.5),
        ],
        scale=scale,
    )

    draw_lightning(
        base,
        [(369, 46), (291, 181), (349, 172), (307, 291), (443, 135), (379, 149)],
        outline_width=4.2,
        glow=14,
        scale=scale,
    )

    draw = ImageDraw.Draw(base)
    for cx, cy, rx, ry in [(201, 224, 37, 43), (300, 224, 37, 43)]:
        draw.ellipse(
            sbox((cx - rx - 1, cy - ry + 4, cx + rx + 1, cy + ry + 4), scale),
            fill=(91, 36, 67, 65),
        )
        draw.ellipse(sbox((cx - rx, cy - ry, cx + rx, cy + ry), scale), fill=WHITE)
        draw.ellipse(
            sbox((cx - rx, cy - ry, cx + rx, cy + ry), scale),
            outline=(104, 57, 85, 120),
            width=sc(2.5, scale),
        )
        draw.ellipse(sbox((cx - 16, cy - 18, cx + 17, cy + 18), scale), fill=INK)
        draw.ellipse(sbox((cx - 10, cy - 13, cx + 2, cy - 1), scale), fill=WHITE)
        draw.ellipse(sbox((cx + 8, cy + 7, cx + 14, cy + 13), scale), fill=(255, 255, 255, 210))

    draw.ellipse(sbox((145, 259, 191, 287), scale), fill=CHEEK)
    draw.ellipse(sbox((320, 259, 366, 287), scale), fill=CHEEK)
    for x in (155, 169, 333, 347):
        draw.line(
            spoints([(x - 7, 275), (x + 6, 269)], scale),
            fill=(255, 205, 220, 145),
            width=sc(2.3, scale),
        )

    draw.arc(sbox((228, 253, 286, 306), scale), start=24, end=156, fill=INK, width=sc(6, scale))
    draw.arc(
        sbox((239, 274, 275, 305), scale),
        start=18,
        end=162,
        fill=(255, 166, 194, 175),
        width=sc(3, scale),
    )

    for spark_x, spark_y, radius in [(101, 155, 5), (423, 254, 4), (89, 289, 3.2), (390, 74, 3.8)]:
        draw.ellipse(
            sbox((spark_x - radius, spark_y - radius, spark_x + radius, spark_y + radius), scale),
            fill=(255, 236, 135, 150),
        )

    return base


def font_path(*names: str) -> str | None:
    roots = [
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("/usr/share/fonts/truetype/liberation2"),
        Path("/usr/share/fonts/liberation"),
        Path("/usr/share/fonts/Adwaita"),
        Path("/usr/share/fonts/truetype"),
        Path("/usr/share/fonts"),
    ]
    for root in roots:
        for name in names:
            matches = sorted(root.rglob(name)) if root.exists() else []
            if matches:
                return str(matches[0])
    return None


def load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = (
        ("DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf")
        if bold
        else ("DejaVuSans.ttf", "LiberationSans-Regular.ttf")
    )
    path = font_path(*names)
    if path:
        return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def draw_text_gradient(
    base: Image.Image,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    left: Sequence[int],
    right: Sequence[int],
    *,
    stroke_fill: Sequence[int] | None = None,
    stroke_width: int = 0,
) -> None:
    draw = ImageDraw.Draw(base)
    if stroke_fill and stroke_width:
        draw.text(xy, text, font=font, fill=tuple(stroke_fill), stroke_width=stroke_width, stroke_fill=tuple(stroke_fill))

    mask = Image.new("L", base.size, 0)
    ImageDraw.Draw(mask).text(xy, text, font=font, fill=255)
    alpha_composite_masked(base, horizontal_gradient(base.size, left, right), mask)


def fit_font(
    text: str,
    *,
    start_size: int,
    min_size: int,
    max_width: int,
    bold: bool,
    scale: int = SCALE,
) -> ImageFont.ImageFont:
    probe = Image.new("RGBA", (10, 10), TRANSPARENT)
    draw = ImageDraw.Draw(probe)
    for size in range(start_size, min_size - 1, -2):
        font = load_font(size * scale, bold=bold)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width * scale:
            return font
    return load_font(min_size * scale, bold=bold)


def draw_logo_art(scale: int = SCALE) -> Image.Image:
    size = (1024 * scale, 512 * scale)
    base = Image.new("RGBA", size, TRANSPARENT)

    mark = draw_icon_art(scale)
    mark_size = 358 * scale
    mark = mark.resize((mark_size, mark_size), Image.Resampling.LANCZOS)

    glow_layer, glow_draw = blurred_shape_layer(size, blur=18, scale=scale)
    glow_draw.ellipse(sbox((54, 72, 410, 428), scale), fill=(255, 91, 139, 34))
    glow_draw.polygon(
        spoints([(812, 109), (770, 198), (808, 195), (777, 283), (866, 170), (821, 177)], scale),
        fill=(255, 210, 52, 64),
    )
    paste_blurred(base, glow_layer, blur=18, scale=scale)

    base.alpha_composite(mark, (sc(54, scale), sc(77, scale)))
    draw_lightning(
        base,
        [(808, 117), (770, 198), (810, 193), (779, 283), (870, 169), (823, 177)],
        outline_width=2.8,
        glow=9,
        scale=scale,
    )

    draw = ImageDraw.Draw(base)
    title_font = fit_font(
        "Octopus Energy",
        start_size=64,
        min_size=54,
        max_width=548,
        bold=True,
        scale=scale,
    )
    main_font = fit_font("OEJP", start_size=118, min_size=96, max_width=420, bold=True, scale=scale)
    tag_font = fit_font(
        "Home Assistant integration",
        start_size=29,
        min_size=24,
        max_width=460,
        bold=False,
        scale=scale,
    )

    x = sc(430, scale)
    draw.text((x + sc(4, scale), sc(123, scale) + sc(5, scale)), "Octopus Energy", font=title_font, fill=(65, 34, 82, 55))
    draw.text(
        (x, sc(123, scale)),
        "Octopus Energy",
        font=title_font,
        fill=(72, 40, 96, 255),
        stroke_width=sc(1.5, scale),
        stroke_fill=(255, 238, 250, 190),
    )
    draw.line(
        (x, sc(197, scale), sc(718, scale), sc(197, scale)),
        fill=(255, 205, 50, 215),
        width=sc(5, scale),
    )
    draw.line(
        (sc(726, scale), sc(197, scale), sc(794, scale), sc(197, scale)),
        fill=(255, 94, 143, 175),
        width=sc(5, scale),
    )

    draw.text((x + sc(5, scale), sc(197, scale) + sc(8, scale)), "OEJP", font=main_font, fill=(66, 31, 79, 62))
    draw_text_gradient(
        base,
        (x, sc(197, scale)),
        "OEJP",
        main_font,
        PINK,
        PURPLE_SOFT,
        stroke_fill=(255, 231, 244, 130),
        stroke_width=sc(1.8, scale),
    )

    draw = ImageDraw.Draw(base)
    draw.text(
        (x + sc(3, scale), sc(344, scale) + sc(4, scale)),
        "Home Assistant integration",
        font=tag_font,
        fill=(65, 34, 82, 42),
    )
    draw.text(
        (x, sc(344, scale)),
        "Home Assistant integration",
        font=tag_font,
        fill=(88, 65, 102, 245),
        stroke_width=sc(1.1, scale),
        stroke_fill=(255, 244, 252, 175),
    )

    for cx, cy, r, color in [
        (914, 136, 4.5, (255, 230, 101, 160)),
        (927, 214, 3.5, (255, 110, 159, 125)),
        (400, 350, 3.5, (255, 232, 134, 140)),
    ]:
        draw.ellipse(sbox((cx - r, cy - r, cx + r, cy + r), scale), fill=color)

    return base


def save_resized(image: Image.Image, path: Path, size: tuple[int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.resize(size, Image.Resampling.LANCZOS).save(path, "PNG")


def main() -> None:
    save_resized(draw_icon_art(SCALE), ICON_PATH, (512, 512))
    save_resized(draw_logo_art(SCALE), LOGO_PATH, (1024, 512))
    print(f"Generated {ICON_PATH.relative_to(ROOT)}")
    print(f"Generated {LOGO_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
