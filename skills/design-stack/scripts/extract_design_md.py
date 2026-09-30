#!/usr/bin/env python3
"""Extract a DESIGN.md (Google Labs design.md alpha schema) from a prose design-system file.

Used by /design-stack --system-to-design-md. Python 3.9+ standard library only.

  extract_design_md.py <input system.md> <output DESIGN.md> [--dry-run]

Reads the pipe tables in a project's .interface-design/system.md (or any markdown design
system) and writes DESIGN.md: YAML front matter with lint-checkable tokens, then a markdown
body. --dry-run prints to stdout and writes nothing. Token counts go to stderr.

Schema notes (checked against `npx @google/design.md@0.1.1 spec`):
  - top-level keys: version, name, description, colors, typography, rounded, spacing, components
  - colors: flat map of name -> "#RRGGBB" (hex, not HSL)
  - typography: map of name -> {fontFamily, fontSize, fontWeight, lineHeight, letterSpacing?}
  - rounded: map of scale -> dimension (the key is `rounded`, not `radii`)
  - spacing: map of scale -> dimension or number
  - components: map of name -> {backgroundColor, textColor, typography, rounded, padding,
    size, height, width}; values reference tokens as {path.to.token}

Body section order: Overview, Colors, Typography, Layout, Elevation & Depth, Shapes,
Components, Do's and Don'ts.

Exit 0 written, 2 usage error or unreadable input. Always lint the result:
  npx -y @google/design.md@0.1.1 lint DESIGN.md --format json
"""

from __future__ import annotations

import math
import json
import os
import re
import sys

DASH = chr(0x2014)  # em dash, matched in source titles; never written to output

# --------------------------------------------------------------------------- helpers


def normalize_token_name(raw: str) -> str:
    """Strip backticks and a leading --, lowercase, kebab-case."""
    s = raw.strip().strip("`").strip()
    s = re.sub(r"^--", "", s).lower()
    s = re.sub(r"[^a-z0-9-]+", "-", s)
    return s.strip("-")


def clean_cell(raw: str) -> str:
    return raw.strip().strip("`").strip()


def _js_round(v: float) -> int:
    return int(math.floor(v + 0.5))


def hsl_to_hex(h: float, s: float, l: float) -> str:
    if not all(math.isfinite(v) for v in (h, s, l)) or not (0 <= s <= 100 and 0 <= l <= 100):
        raise ValueError("HSL needs finite hue and saturation/lightness in 0..100")
    h %= 360
    s_n, l_n = s / 100, l / 100
    c = (1 - abs(2 * l_n - 1)) * s_n
    hp = h / 60
    x = c * (1 - abs((hp % 2) - 1))
    r = g = b = 0.0
    if 0 <= hp < 1:
        r, g = c, x
    elif hp < 2:
        r, g = x, c
    elif hp < 3:
        g, b = c, x
    elif hp < 4:
        g, b = x, c
    elif hp < 5:
        r, b = x, c
    elif hp < 6:
        r, b = c, x
    m = l_n - c / 2
    return "#" + "".join(f"{_js_round((v + m) * 255):02X}" for v in (r, g, b))


def parse_color(raw: str):
    """Hex (#RGB, #RRGGBB) or hsl()/hsla() -> #RRGGBB. None if not a color."""
    s = re.sub(r"[;,]+$", "", clean_cell(raw)).strip()
    m = re.match(r"^#([0-9A-Fa-f]{6})$", s)
    if m:
        return "#" + m.group(1).upper()
    m = re.match(r"^#([0-9A-Fa-f])([0-9A-Fa-f])([0-9A-Fa-f])$", s)
    if m:
        return "#" + "".join(ch * 2 for ch in m.groups()).upper()
    number = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
    m = re.fullmatch(
        rf"(hsla?)\(\s*({number})[\s,]+({number})%[\s,]+({number})%"
        rf"(?:\s*[,/]\s*({number})(%)?)?\s*\)", s, re.I,
    )
    if m:
        alpha = float(m.group(5)) if m.group(5) is not None else 1
        if m.group(6):
            alpha /= 100
        if alpha != 1 or (m.group(1).lower() == "hsla" and m.group(5) is None):
            raise ValueError("nonopaque or missing alpha cannot be represented as #RRGGBB")
        return hsl_to_hex(float(m.group(2)), float(m.group(3)), float(m.group(4)))
    return None


SEPARATOR = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$")


def split_row(row: str) -> list:
    t = row.strip()
    if t.startswith("|"):
        t = t[1:]
    if t.endswith("|"):
        t = t[:-1]
    return [c.strip() for c in t.split("|")]


def parse_all_pipe_tables(md: str) -> list:
    """Every pipe table with its heading ancestry, closest heading first.

    A heading at level N replaces slot N and clears every deeper slot. Without the clearing,
    an H2 "Typography" stays live through later sections and the typography extractor pulls
    in the spacing and radius rows (an observed bug in the first version)."""
    lines = md.split("\n")
    tables = []
    by_level = [None] * 7
    i = 0
    while i < len(lines):
        line = lines[i]
        hm = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if hm:
            level = len(hm.group(1))
            by_level[level] = hm.group(2)
            for deeper in range(level + 1, 7):
                by_level[deeper] = None
            i += 1
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if "|" in line and nxt is not None and SEPARATOR.match(nxt):
            headers = split_row(line)
            rows = []
            j = i + 2
            while j < len(lines) and "|" in lines[j] and lines[j].strip():
                rows.append(split_row(lines[j]))
                j += 1
            ancestry = [h for h in reversed(by_level[1:]) if h]
            tables.append(
                {"headers": headers, "rows": rows, "headings": ancestry, "start": i + 1}
            )
            i = j
            continue
        i += 1
    return tables


def table_matches(t: dict, needles: list) -> bool:
    return any(n.lower() in h.lower() for h in t["headings"] for n in needles)


def find_col(headers: list, needles: list) -> int:
    for i, h in enumerate(headers):
        if any(n.lower() in h.lower() for n in needles):
            return i
    return -1


def cell(row: list, idx: int) -> str:
    return row[idx] if 0 <= idx < len(row) else ""


# --------------------------------------------------------------------------- extractors


def extract_colors(tables: list) -> list:
    out, seen = [], set()
    for t in tables:
        if not table_matches(t, ["color", "palette", "accent", "semantic"]):
            continue
        ti = find_col(t["headers"], ["token", "name", "var"])
        vi = find_col(t["headers"], ["hex", "value", "hsl", "color"])
        ri = find_col(t["headers"], ["role", "use", "purpose", "description"])
        if ti == -1 or vi == -1:
            continue
        for row in t["rows"]:
            name = normalize_token_name(cell(row, ti))
            hexv = parse_color(cell(row, vi)) if cell(row, vi) else None
            if not name or not hexv or name in seen:
                continue  # rows whose value is not a recognizable color are skipped
            seen.add(name)
            out.append(
                {
                    "name": name,
                    "hex": hexv,
                    "role": clean_cell(cell(row, ri)) if ri != -1 else "",
                }
            )
    return out


def ensure_dimension(raw: str) -> str:
    s = clean_cell(raw)
    if re.fullmatch(r"[0-9.]+", s):
        return f"{s}px"
    if re.fullmatch(r"[0-9.]+(px|em|rem)", s, re.I):
        return s.lower()
    return s


def ensure_line_height(raw: str):
    s = clean_cell(raw)
    if s in ("", "-"):
        return 1.5
    if re.fullmatch(r"[0-9.]+", s):
        return float(s)
    if re.fullmatch(r"[0-9.]+(px|em|rem)", s, re.I):
        return s.lower()
    return 1.5


def extract_typography(tables: list, body_family: str, display_family: str) -> list:
    out, seen = [], set()
    for t in tables:
        if not table_matches(t, ["typography", "type scale", "type-scale"]):
            continue
        h = t["headers"]
        ti = find_col(h, ["token", "name"])
        if ti == -1:
            continue
        si = find_col(h, ["size", "desktop"])
        li = find_col(h, ["line-height", "line height", "leading"])
        wi = find_col(h, ["weight", "fontweight"])
        fi = find_col(h, ["family"])
        ki = find_col(h, ["tracking", "letter-spacing", "letter spacing"])
        for row in t["rows"]:
            name = normalize_token_name(cell(row, ti))
            if not name or name in seen:
                continue
            seen.add(name)
            weight = 400
            if wi != -1:
                m = re.match(r"\s*(\d+)", clean_cell(cell(row, wi)))
                if m:
                    weight = int(m.group(1))
            spacing = None
            if ki != -1:
                ls = clean_cell(cell(row, ki))
                if ls and ls not in ("0", "-"):
                    m = re.search(
                        r"(-?[0-9.]+)\s*(em|px|rem)", ls, re.I
                    )  # "0.08em uppercase" -> 0.08em
                    if m:
                        spacing = f"{m.group(1)}{m.group(2).lower()}"
            out.append(
                {
                    "name": name,
                    "fontFamily": (clean_cell(cell(row, fi)) if cell(row, fi) not in ("", "-")
                                   else display_family if name.startswith("display") else body_family),
                    "fontSize": ensure_dimension(cell(row, si)) if si != -1 else "16px",
                    "fontWeight": weight,
                    "lineHeight": ensure_line_height(cell(row, li))
                    if li != -1
                    else 1.5,
                    "letterSpacing": spacing,
                }
            )
    return out


def _name_value(tables: list, needles: list) -> list:
    out, seen = [], set()
    for t in tables:
        if not table_matches(t, needles):
            continue
        ti = find_col(t["headers"], ["token", "name"])
        vi = find_col(t["headers"], ["value", "size", "px"])
        if ti == -1 or vi == -1:
            continue
        for row in t["rows"]:
            name, raw = normalize_token_name(cell(row, ti)), cell(row, vi)
            if name and raw and name not in seen:
                seen.add(name)
                out.append((name, raw))
    return out


def extract_spacing(tables: list) -> list:
    return [
        {"name": n, "value": ensure_dimension(v)}
        for n, v in _name_value(tables, ["spacing"])
        if ensure_dimension(v)
    ]


def extract_rounded(tables: list) -> list:
    out, seen = [], set()
    for name, raw in _name_value(
        tables, ["radii", "rounded", "border radius", "radius"]
    ):
        name = re.sub(
            r"^radius-", "", name
        )  # schema scale keys drop the radius- prefix
        v = clean_cell(raw)
        value = (
            "999px" if v.startswith("999") else ensure_dimension(v)
        )  # 999 or 9999 means "full"
        if value == "0":
            value = "0px"  # a bare 0 is not a valid dimension
        if name in seen:
            continue
        seen.add(name)
        out.append({"name": name, "value": value})
    return out


def h2_section(md: str, pattern: str) -> str:
    """Body of the first H2 whose title matches, up to the next H2."""
    out, inside = [], False
    for line in md.split("\n"):
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if inside:
                break
            if re.search(pattern, m.group(1), re.I):
                inside = True
                continue
        if inside:
            out.append(line)
    return "\n".join(out).strip()


def summarize_prose(body: str, max_chars: int = 600) -> str:
    """Prose only: drops tables, fenced code and sub-headings. The separator filter must match a
    whole |---|---| row; an earlier pattern also matched "- " bullets and dropped them."""
    text = re.sub(r"```[\s\S]*?```", "", body)
    kept = [
        ln
        for ln in text.split("\n")
        if "|" not in ln
        and not re.fullmatch(r"\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*", ln)
        and not re.match(r"^#{2,6}\s", ln)
        and not ln.startswith("```")
    ]
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    cut = cleaned.rfind(".", 0, max_chars)
    return cleaned[: cut + 1 if cut > 0 else max_chars].strip()


def extract_all(md: str, project: str) -> dict:
    tables = parse_all_pipe_tables(md)
    display = body = "system-ui, -apple-system, sans-serif"
    m = re.search(r"Display:\s*([^\n]+)\n[\s\S]{0,200}?Body:\s*([^\n]+)", md)
    if m:
        display, body = m.group(1).strip(), m.group(2).strip()
    description = ""
    past_h1 = False
    for ln in md.split("\n"):
        if not past_h1:
            past_h1 = bool(re.match(r"^#\s+", ln))
            continue
        if re.match(r"^\*\*|^\s*$|^---|^#{2,}", ln):
            continue
        description = ln.strip()
        if description:
            break
    return {
        "project": project,
        "description": description or f"{project} interface design tokens",
        "colors": extract_colors(tables),
        "typography": extract_typography(tables, body, display),
        "spacing": extract_spacing(tables),
        "rounded": extract_rounded(tables),
        "overview": summarize_prose(
            h2_section(md, r"north.?star|overview|brand|principles|dark[- ]mode"), 800
        ),
        "layout": summarize_prose(h2_section(md, r"responsive|layout"), 800),
        "elevation": summarize_prose(
            h2_section(md, r"elevation|borders|shadow|depth"), 600
        ),
        "shapes": summarize_prose(h2_section(md, r"radii|rounded|shape"), 400),
        "components": summarize_prose(h2_section(md, r"component|states"), 800),
        "dos": summarize_prose(
            h2_section(md, r"accessibilit|do.?s.*don.?ts|imagery"), 800
        ),
    }


# --------------------------------------------------------------------------- components


def build_components(tok: dict) -> dict:
    """Three starter components from the extracted names, only where the tokens exist."""

    def find(kind, *needles):
        for t in tok[kind]:
            if any(n in t["name"] for n in needles):
                return t["name"]
        return None

    comps = {}
    accent, bg, text = (
        find("colors", "accent"),
        find("colors", "bg"),
        find("colors", "text"),
    )
    button_type, pill = find("typography", "button"), find("rounded", "pill", "full")
    pad6 = find("spacing", "6") or find("spacing", "4")
    if accent and bg:
        c = {"backgroundColor": f"{{colors.{accent}}}", "textColor": f"{{colors.{bg}}}"}
        if button_type:
            c["typography"] = f"{{typography.{button_type}}}"
        if pill:
            c["rounded"] = f"{{rounded.{pill}}}"
        if pad6:
            c["padding"] = f"{{spacing.{pad6}}}"
        comps["buttonPrimary"] = c
    body_type, md_round = find("typography", "body"), find("rounded", "md")
    if bg and (text or body_type):
        c = {"backgroundColor": f"{{colors.{bg}}}"}
        if text:
            c["textColor"] = f"{{colors.{text}}}"
        if body_type:
            c["typography"] = f"{{typography.{body_type}}}"
        if md_round:
            c["rounded"] = f"{{rounded.{md_round}}}"
        if find("spacing", "6"):
            c["padding"] = f"{{spacing.{find('spacing', '6')}}}"
        comps["card"] = c
    label_type = find("typography", "body") or find("typography", "label")
    input_pad = find("spacing", "3") or find("spacing", "4")
    if bg and text:
        c = {"backgroundColor": f"{{colors.{bg}}}", "textColor": f"{{colors.{text}}}"}
        if label_type:
            c["typography"] = f"{{typography.{label_type}}}"
        if md_round:
            c["rounded"] = f"{{rounded.{md_round}}}"
        if input_pad:
            c["padding"] = f"{{spacing.{input_pad}}}"
        comps["input"] = c
    return comps


# --------------------------------------------------------------------------- emit


def yaml_string(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def num(v) -> str:
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def emit_front_matter(tok: dict, comps: dict) -> str:
    out = [
        "---",
        "version: alpha",
        f"name: {yaml_string(tok['project'])}",
        f"description: {yaml_string(tok['description'])}",
        "colors:",
    ]
    out += [f"  {yaml_string(c['name'])}: {yaml_string(c['hex'])}" for c in tok["colors"]]
    out.append("typography:")
    for t in tok["typography"]:
        out += [
            f"  {yaml_string(t['name'])}:",
            f"    fontFamily: {yaml_string(t['fontFamily'])}",
            f"    fontSize: {yaml_string(t['fontSize'])}",
            f"    fontWeight: {t['fontWeight']}",
            f"    lineHeight: {num(t['lineHeight']) if isinstance(t['lineHeight'], float) else yaml_string(t['lineHeight'])}",
        ]
        if t["letterSpacing"]:
            out.append(f"    letterSpacing: {yaml_string(t['letterSpacing'])}")
    out.append("rounded:")
    out += [f"  {yaml_string(r['name'])}: {yaml_string(r['value'])}" for r in tok["rounded"]]
    out.append("spacing:")
    out += [f"  {yaml_string(s['name'])}: {yaml_string(s['value'])}" for s in tok["spacing"]]
    if comps:
        out.append("components:")
        for name, fields in comps.items():
            out.append(f"  {name}:")
            out += [f"    {k}: {yaml_string(v)}" for k, v in fields.items()]
    out += ["---", ""]
    return "\n".join(out)


def emit_body(tok: dict, src: str) -> str:
    link = f"[{src}]({src})"
    o = [
        f"# {tok['project']}",
        "",
        "## Overview",
        "",
        tok["overview"] or f"See {link} for the full design system rationale.",
        "",
        "## Colors",
        "",
    ]
    if tok["colors"]:
        o += ["| Token | Hex | Role |", "|---|---|---|"] + [
            f"| `{c['name']}` | `{c['hex']}` | {c['role']} |" for c in tok["colors"]
        ]
    else:
        o.append(f"See {link} for the color palette.")
    o += ["", "## Typography", ""]
    if tok["typography"]:
        o += [
            "| Token | Family | Size | Weight | Line-height | Tracking |",
            "|---|---|---|---|---|---|",
        ]
        for t in tok["typography"]:
            family = t["fontFamily"].split(",")[0].strip().strip("'\"")
            o.append(
                f"| `{t['name']}` | {family} | {t['fontSize']} | {t['fontWeight']} | {num(t['lineHeight'])} | {t['letterSpacing'] or '-'} |"
            )
    else:
        o.append(f"See {link} for the type scale.")
    o += [
        "",
        "## Layout",
        "",
        tok["layout"] or f"See {link} for the responsive strategy.",
        "",
    ]
    if tok["spacing"]:
        o += (
            ["", "**Spacing tokens**:", "", "| Token | Value |", "|---|---|"]
            + [f"| `{s['name']}` | {s['value']} |" for s in tok["spacing"]]
            + [""]
        )
    o += [
        "## Elevation & Depth",
        "",
        tok["elevation"] or f"See {link} for elevation rules.",
        "",
        "## Shapes",
        "",
    ]
    if tok["shapes"]:
        o.append(tok["shapes"])
    if tok["rounded"]:
        o += ["", "| Token | Value |", "|---|---|"] + [
            f"| `{r['name']}` | {r['value']} |" for r in tok["rounded"]
        ]
    o += [
        "",
        "## Components",
        "",
        tok["components"] or f"See {link} for component states.",
        "",
    ]
    o += [
        "## Do's and Don'ts",
        "",
        tok["dos"] or f"See {link} for the accessibility contract.",
        "",
    ]
    o += [
        "---",
        "",
        f"See {link} for platform-specific notes, motion timing, voice and downstream-doc rules. "
        "Those live outside the lint-checkable token surface.",
        "",
    ]
    return "\n".join(o)


def infer_project(path: str, md: str) -> str:
    m = re.search(r"^#\s+(.+?)\s*$", md, re.M)
    if m:
        title = re.sub(rf"\s*{DASH}.*$|\s+-\s.*$", "", m.group(1)).strip()
        return title or m.group(1).strip()
    return os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(path))))


def convert(md: str, input_path: str, output_path: str) -> tuple:
    tok = extract_all(md, infer_project(input_path, md))
    comps = build_components(tok)
    rel = os.path.relpath(
        os.path.abspath(input_path), os.path.dirname(os.path.abspath(output_path))
    )
    return (
        emit_front_matter(tok, comps)
        + emit_body(tok, rel or os.path.basename(input_path)),
        tok,
        comps,
    )


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    dry = "--dry-run" in argv
    pos = [a for a in argv if not a.startswith("--")]
    if len(pos) < 2:
        print(
            "usage: extract_design_md.py <input system.md> <output DESIGN.md> [--dry-run]",
            file=sys.stderr,
        )
        return 2
    try:
        with open(pos[0], encoding="utf-8") as f:
            md = f.read()
    except OSError as exc:
        print(f"extract_design_md: cannot read {pos[0]}: {exc}", file=sys.stderr)
        return 2
    try:
        text, tok, comps = convert(md, pos[0], pos[1])
    except ValueError as exc:
        print(f"extract_design_md: {exc}", file=sys.stderr)
        return 2
    if dry:
        sys.stdout.write(text)
        return 0
    with open(pos[1], "w", encoding="utf-8") as f:
        f.write(text)
    print(
        f"extract_design_md: wrote {pos[1]}\n  colors:     {len(tok['colors'])}\n  typography: {len(tok['typography'])}\n"
        f"  spacing:    {len(tok['spacing'])}\n  rounded:    {len(tok['rounded'])}\n  components: {len(comps)}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
