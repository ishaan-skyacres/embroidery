"""Generate the fixture SVGs used by the tests (run: python tests/make_fixtures.py)."""
from pathlib import Path

HERE = Path(__file__).resolve().parent / "fixtures"


def logo5() -> str:
    # 5 colours, overlapping shapes, a thin outline stroke, a wide shape and a narrow bar
    return """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 100">
  <circle cx="45" cy="50" r="35" fill="#2060d0"/>
  <rect x="60" y="30" width="50" height="40" fill="#e02020"/>
  <path d="M 105 50 a 20 20 0 1 0 -40 0 a 20 20 0 1 0 40 0 z M 97 50 a 12 12 0 1 1 -24 0 a 12 12 0 1 1 24 0 z" fill="#ffd700" fill-rule="evenodd"/>
  <polygon points="20,85 45,20 70,85" fill="#2e8b2e"/>
  <circle cx="45" cy="50" r="35" fill="none" stroke="#000000" stroke-width="0.6"/>
  <rect x="8" y="8" width="104" height="3" fill="#000000"/>
</svg>
"""


def thin_outline() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 60">
  <rect x="10" y="10" width="80" height="40" rx="8" fill="#80c0ff"/>
  <rect x="10" y="10" width="80" height="40" rx="8" fill="none" stroke="#202020" stroke-width="0.35"/>
  <path d="M 20 30 C 40 10, 60 50, 80 30" fill="none" stroke="#202020" stroke-width="0.9"/>
</svg>
"""


def small_text() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 40">
  <rect x="5" y="5" width="90" height="30" fill="#f0e0c0"/>
  <text x="10" y="28" font-family="DejaVu Sans" font-size="6" fill="#102040">Small text</text>
</svg>
"""


def wide_shape() -> str:
    # at --size-mm 60 the long bar is 15 x 60 mm (must become fill), the second 5 x 45 mm (satin), the line 0.9 mm (running)
    return """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 60">
  <rect x="2" y="0" width="15" height="60" fill="#c03030"/>
  <rect x="22" y="5" width="5" height="45" fill="#3060c0"/>
  <rect x="32" y="5" width="0.9" height="45" fill="#303030"/>
</svg>
"""


def messy12() -> str:
    # 12 near-duplicate shades of 5 colours plus a background rectangle covering the canvas
    shades = {
        "red": ["#e02020", "#e22424", "#dd1f22", "#e42626"],
        "blue": ["#2060d0", "#2262d2", "#1f5ecf"],
        "green": ["#2e8b2e", "#308d30"],
        "yellow": ["#ffd700", "#fdd503"],
        "black": ["#101010"],
    }
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 80">',
           '  <rect x="0" y="0" width="120" height="80" fill="#f4f1ea"/>']
    x = 5
    for name, cols in shades.items():
        for i, c in enumerate(cols):
            out.append(f'  <rect x="{x}" y="{10 + i * 16}" width="18" height="14" fill="{c}"/>')
        x += 23
    out.append("</svg>")
    return "\n".join(out) + "\n"


def write_all() -> None:
    HERE.mkdir(parents=True, exist_ok=True)
    for name, fn in [("logo5.svg", logo5), ("thin_outline.svg", thin_outline), ("small_text.svg", small_text),
                     ("wide_shape.svg", wide_shape), ("messy12.svg", messy12)]:
        (HERE / name).write_text(fn(), encoding="utf-8")


if __name__ == "__main__":
    write_all()
    print("fixtures written to", HERE)
