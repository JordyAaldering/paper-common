from enum import Enum
from pathlib import Path
import matplot2tikz
import re

class Colors(Enum):
    GREEN = '#3AA640'
    LIGHT_GREEN = '#A8D47A'
    WHITE = '#FFFFFF'
    GREY = '#AAABAB'
    BLACK = '#000000'

    # Harmonies of GREEN (https://www.colorharmonygenerator.com)
    COMPLEMENTARY = '#A63AA0'
    TRIADIC_1 = '#403AA6'
    TRIADIC_2 = '#A6403A'
    TETRADIC_1 = '#3A6AA6'
    TETRADIC_2 = '#A63AA0'
    TETRADIC_3 = '#A6763A'

def as_tikz(fig, ax, ax2=None,
            axis_width: str = r'\linewidth',
            axis_height: str = r'.8\linewidth',
            y_axis_text_size: str = 'scriptsize',
            **kwargs
        ) -> str:

    # Ensures ticks/formatters/etc. are resolved
    fig.canvas.draw()

    # https://github.com/ErwindeGelder/matplot2tikz/blob/main/src/matplot2tikz/_save.py#L68
    code = matplot2tikz.get_tikz_code(fig,
            axis_width=axis_width,
            axis_height=axis_height,
            include_disclaimer=False,
            **kwargs)

    code = tikz_sanitize_labels(code)
    if ax2 is not None:
        code = tikz_fix_overlapping_x_ticks(code)
        right_y_tick_labels = get_y_labels(ax2)
        y_axis_font_scale = latex_size_to_font_scale(y_axis_text_size)
        code = fix_twin_axis_layout(
            code,
            axis_width,
            right_y_tick_labels,
            y_axis_font_scale=y_axis_font_scale,
        )

    code = tikz_apply_yaxis_text_size(code, y_axis_text_size)
    return code

def save_tikz(code: str, filepath: str):
    filepath = Path(filepath)
    with filepath.open('w') as f:
        f.write(code)

def get_y_labels(ax):
    return [t.get_text() for t in ax.get_yticklabels()]

def tikz_sanitize_labels(code: str) -> str:
    '''
    Sanitize references in `label` and `addlegendimage` by replacing invalid characters.
    '''
    label_re = re.compile(r'\\label\{([^}]*)\}')
    # Match refstyle value: allow balanced `{}` pairs (e.g. `\si{\giga\byte\per\second}`), stop at unbalanced `}` or `,``
    legend_re = re.compile(r'(\\addlegendimage\{.*?/pgfplots/refstyle=)((?:[^,{}]|\{[^}]*\})+)', re.DOTALL)
    code = label_re.sub(lambda m: f"\\label{{{sanitize(m.group(1))}}}", code)
    code = legend_re.sub(lambda m: f"{m.group(1)}{sanitize(m.group(2))}", code)
    return code

def sanitize(s: str) -> str:
    '''
    Replace invalid characters with underscores.
    '''
    s = re.sub(r'[^A-Za-z0-9_\-:]+', '_', s)
    s = re.sub(r'_+', '_', s)  # Collapse multiple underscores
    return s.strip('_')  # Avoid leading/trailing underscores

def split_top_level_options(s: str) -> list[str]:
    parts = []
    chunk = []
    brace_depth = 0
    bracket_depth = 0
    paren_depth = 0

    for ch in s:
        if ch == '{':
            brace_depth += 1
        elif ch == '}':
            brace_depth = max(0, brace_depth - 1)
        elif ch == '[':
            bracket_depth += 1
        elif ch == ']':
            bracket_depth = max(0, bracket_depth - 1)
        elif ch == '(':
            paren_depth += 1
        elif ch == ')':
            paren_depth = max(0, paren_depth - 1)

        if ch == ',' and brace_depth == 0 and bracket_depth == 0 and paren_depth == 0:
            part = ''.join(chunk).strip()
            if part:
                parts.append(part)
            chunk = []
            continue

        chunk.append(ch)

    part = ''.join(chunk).strip()
    if part:
        parts.append(part)

    return parts

def parse_axis_options(opts: str) -> list[tuple[str, str | None]]:
    text = opts.strip()
    if not (text.startswith('[') and text.endswith(']')):
        return []

    body = text[1:-1].strip()
    if not body:
        return []

    entries = []
    for part in split_top_level_options(body):
        if '=' in part:
            key, value = part.split('=', 1)
            entries.append((key.strip(), value.strip()))
        else:
            entries.append((part.strip(), None))
    return entries

def render_axis_options(entries: list[tuple[str, str | None]]) -> str:
    pieces = []
    for key, value in entries:
        if value is None:
            pieces.append(key)
        else:
            pieces.append(f'{key}={value}')
    return '[' + ','.join(pieces) + ']'

def remove_option(entries: list[tuple[str, str | None]], key: str) -> list[tuple[str, str | None]]:
    return [(k, v) for k, v in entries if k != key]

def set_option(entries: list[tuple[str, str | None]], key: str, value: str | None) -> list[tuple[str, str | None]]:
    updated = []
    replaced = False
    for k, v in entries:
        if k == key:
            if not replaced:
                updated.append((key, value))
                replaced = True
            continue
        updated.append((k, v))

    if not replaced:
        updated.insert(0, (key, value))
    return updated

def has_right_y_axis(opts: str) -> bool:
    return bool(re.search(r'axis\s+y\s+line\*?\s*=\s*right|yticklabel\s+pos\s*=\s*right|ylabel\s+near\s+ticks\s*=\s*right', opts))

def latex_size_to_font_scale(size: str) -> float:
    name = size.strip().lstrip('\\')
    if not name:
        return 0.7

    by_name = {
        'tiny': 0.55,
        'scriptsize': 0.70,
        'footnotesize': 0.80,
        'small': 0.90,
        'normalsize': 1.00,
        'large': 1.10,
        'Large': 1.20,
        'LARGE': 1.30,
        'huge': 1.40,
        'Huge': 1.50,
    }

    if name in by_name:
        return by_name[name]

    lowered = name.lower()
    lower_map = {
        'tiny': 0.55,
        'scriptsize': 0.70,
        'footnotesize': 0.80,
        'small': 0.90,
        'normalsize': 1.00,
        'large': 1.10,
        'huge': 1.40,
    }
    return lower_map.get(lowered, 0.70)

def latex_size_to_font(size: str) -> str:
    name = size.strip().lstrip('\\')
    return f'\\{name or "scriptsize"}'

def set_style_font(entries: list[tuple[str, str | None]], key: str, font: str) -> list[tuple[str, str | None]]:
    style_value = None
    for k, v in entries:
        if k == key:
            style_value = v
            break

    parts = []
    if style_value:
        style_text = style_value.strip()
        if style_text.startswith('{') and style_text.endswith('}'):
            style_text = style_text[1:-1]
        parts = split_top_level_options(style_text) if style_text else []

    parts = [p for p in parts if not p.strip().startswith('font=')]
    parts.append(f'font={font}')
    return set_option(entries, key, '{' + ','.join(parts) + '}')

def tikz_apply_yaxis_text_size(code: str, y_axis_text_size: str) -> str:
    font = latex_size_to_font(y_axis_text_size)

    def repl(m):
        begin, opts = m.groups()
        entries = parse_axis_options(opts)
        entries = set_style_font(entries, 'yticklabel style', font)
        entries = set_style_font(entries, 'ylabel style', font)
        return begin + render_axis_options(entries)

    axis_begin_re = re.compile(r'(\\begin\{axis\})(\s*\[.*?\])', re.DOTALL)
    return axis_begin_re.sub(repl, code)

def tikz_fix_overlapping_x_ticks(code: str) -> str:
    '''
    With twin axis plots, `xtick` and `xticklabels` is being set for both axes, causing overlapping ticks.
    Replace ticks and labels of all but the first axis with empty ones to fix this issue.
    '''
    count = 0

    def repl(m):
        nonlocal count
        begin, opts = m.groups()
        count += 1

        if count == 1:  # Leave first axis untouched
            return m.group(0)

        xtick_re = re.compile(r'xtick\s*=\s*\{.*?\}', re.DOTALL)
        xlabels_re = re.compile(r'xticklabels\s*=\s*\{.*?\}', re.DOTALL)
        opts = xtick_re.sub('xtick={}', opts)
        opts = xlabels_re.sub('xticklabels={}', opts)
        return begin + opts

    axis_begin_re = re.compile(r'(\\begin\{axis\})(\s*\[.*?\])', re.DOTALL)
    return axis_begin_re.sub(repl, code)

def fix_twin_axis_layout(
    code: str,
    axis_width: str,
    right_y_tick_labels: list[str],
    y_axis_font_scale: float = 0.7,
    tick_length_pt: float = 2.5,
    inner_sep_pt: float = 0.5,
) -> str:
    main_name = "mainaxis"
    right_padding_em = compute_padding_em(
        right_y_tick_labels,
        tick_font_scale=y_axis_font_scale,
        y_axis_label_font_scale=y_axis_font_scale,
        tick_length_pt=tick_length_pt,
        inner_sep_pt=inner_sep_pt,
    )
    effective_width = f"{{{axis_width} - {right_padding_em:.2f}em}}"

    def repl(m):
        begin, opts = m.groups()
        entries = parse_axis_options(opts)

        # Normalize width on both axes and remove any existing scale-only marker.
        entries = remove_option(entries, 'scale only axis')
        entries = set_option(entries, 'width', effective_width)

        if has_right_y_axis(opts):
            # Tie right axis to left axis rectangle and hide duplicate x-axis visuals.
            for key in ('at', 'anchor', 'axis x line', 'xtick', 'xticklabels', 'overlay'):
                entries = remove_option(entries, key)

            injection = [
                ('at', f'{{({main_name}.south west)}}'),
                ('anchor', 'south west'),
                ('overlay', None),
                ('axis x line', 'none'),
                ('xtick', r'\empty'),
                ('xticklabels', r'\empty'),
            ]

            opts = render_axis_options(injection + entries)
            return begin + opts

        # Left axis becomes anchor axis regardless of export order.
        entries = set_option(entries, 'name', main_name)
        opts = render_axis_options(entries)
        return begin + opts

    axis_begin_re = re.compile(r'(\\begin\{axis\})(\s*\[.*?\])', re.DOTALL)
    return axis_begin_re.sub(repl, code)

def compute_padding_em(
    tick_labels: list[str],
    tick_font_scale: float = 0.7,
    y_axis_label_font_scale: float = 0.7,
    tick_length_pt: float = 2.5,
    inner_sep_pt: float = 0.5,
) -> float:
    '''
    Compute total right-axis padding in em.
    '''
    max_tick_width = 0.0
    if tick_labels:
        max_tick_width = max([estimate_label_width_em(lbl, font_scale=tick_font_scale) for lbl in tick_labels if lbl])

    # A rotated side ylabel mostly contributes by glyph height, not string length.
    y_axis_label_side_em = 0.0
    y_axis_label_side_em = 0.65 * y_axis_label_font_scale

    PT_TO_EM = 1.0/12.0  # Approximately 1em = 12pt
    tick_length_em = tick_length_pt * PT_TO_EM
    inner_sep_em = inner_sep_pt * PT_TO_EM

    # Keep padding tight: measured tick width + geometric extras + small safety buffer.
    return max_tick_width + y_axis_label_side_em + tick_length_em + inner_sep_em

def estimate_label_width_em(label: str, font_scale: float = 0.7) -> float:
    '''
    Estimate label width from weighted character classes.

    Digits and punctuation are narrower than letters in typical TeX fonts,
    so weighted widths avoid systematic overestimation (and excessive padding).
    '''
    if not label:
        return 0.0

    width_em = 0.0
    for ch in label:
        if ch.isdigit():
            width_em += 0.48
        elif ch in '.:,;':
            width_em += 0.22
        elif ch in '+-=':
            width_em += 0.30
        elif ch in '()[]{}':
            width_em += 0.32
        elif ch.isspace():
            width_em += 0.25
        elif ch.isalpha():
            width_em += 0.50
        else:
            width_em += 0.45

    return width_em * font_scale
