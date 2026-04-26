from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

PAGE_W, PAGE_H = A4

CARD_W = 66 * mm
CARD_H = 66 * mm
COLS = 3
ROWS = 4

GRID_W = COLS * CARD_W
GRID_H = ROWS * CARD_H
MARGIN_X = (PAGE_W - GRID_W) / 2
MARGIN_Y = (PAGE_H - GRID_H) / 2


def front_origin(idx: int) -> tuple[float, float]:
    """Bottom-left corner of card idx on a front page (ReportLab y-up coords)."""
    col = idx % COLS
    row = idx // COLS
    return (
        MARGIN_X + col * CARD_W,
        MARGIN_Y + (ROWS - 1 - row) * CARD_H,
    )


def back_origin(idx: int) -> tuple[float, float]:
    """Bottom-left corner of card idx on a back page.

    Columns are mirrored so that long-edge duplex printing aligns each
    back face with its corresponding front face.
    """
    col = idx % COLS
    row = idx // COLS
    mirrored_col = COLS - 1 - col
    return (
        MARGIN_X + mirrored_col * CARD_W,
        MARGIN_Y + (ROWS - 1 - row) * CARD_H,
    )
