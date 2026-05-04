from enum import Enum
from pathlib import Path
import hashlib
import matplot2tikz
import re
from uuid import uuid4

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

def as_tikz(fig, ax, ax2=None, axis_height_ratio: float = 0.8, **kwargs) -> str:
    # Ensures ticks/formatters/etc. are resolved
    fig.canvas.draw()

    # https://github.com/ErwindeGelder/matplot2tikz/blob/main/src/matplot2tikz/_save.py#L68
    code = matplot2tikz.get_tikz_code(fig,
            axis_width=r'\linewidth',
            axis_height=f'{axis_height_ratio:g}\\linewidth',
            include_disclaimer=False,
            **kwargs)

    # Namespace labels per exported figure to avoid multiply-defined labels across files.
    code = tikz_sanitize_labels(code)
    if ax2 is not None:
        code = tikz_fix_overlapping_x_ticks(code)
        code = fix_twin_axis_layout(code)
    return code

def save_tikz(code: str, filepath: str):
    filepath = Path(filepath)
    with filepath.open('w') as f:
        f.write(code)

def tikz_sanitize_labels(code: str) -> str:
    '''
    Sanitize references in `label` and `addlegendimage` by replacing invalid characters.
    '''
    prefix = f'pc{uuid4().hex[:8]}'

    def hashed_label(raw: str) -> str:
        digest = hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]
        return f'{prefix}:{digest}'

    # Match label content: allow balanced `{}` pairs (e.g. `\si{\giga\byte}`), stop at unbalanced `}`
    label_re = re.compile(r'\\label\{((?:[^{}]|\{[^}]*\})*)\}')
    legend_re = re.compile(r'(\\addlegendimage\{.*?/pgfplots/refstyle=)((?:[^,{}]|\{[^}]*\})+)', re.DOTALL)
    code = label_re.sub(lambda m: f"\\label{{{hashed_label(m.group(1))}}}", code)
    code = legend_re.sub(lambda m: f"{m.group(1)}{hashed_label(m.group(2))}", code)
    return code

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

def detect_plot_type(code: str) -> str:
    '''
    Detect whether the axis contains bar plots or line plots.
    Returns 'common/bar' if any bar plots are found, otherwise 'common/line'.
    '''
    if re.search(r'\\addplot\s*\[[^\]]*(?:ybar|xbar)', code):
        return 'common/bar'
    return 'common/line'

def fix_twin_axis_layout(code: str) -> str:
    axis_index = 0
    # Find all axes for plot type detection
    axis_contents = re.findall(r'\\begin\{axis\}.*?\\end\{axis\}', code, re.DOTALL)

    def repl(m):
        nonlocal axis_index
        begin, opts = m.groups()
        entries = parse_axis_options(opts)
        axis_index += 1

        # Normalize width on both axes and remove any existing scale-only marker.
        entries = remove_option(entries, 'scale only axis')

        # Detect plot type for this axis and append style
        axis_content = axis_contents[axis_index - 1] if axis_index <= len(axis_contents) else ''
        plot_style = detect_plot_type(axis_content)
        entries = set_option(entries, plot_style, None)

        if axis_index > 1:
            # Tie right axis to left axis rectangle and hide duplicate x-axis visuals.
            for key in ('at', 'anchor', 'axis x line', 'xtick', 'xticklabels', 'overlay', 'width'):
                entries = remove_option(entries, key)

            entries = set_option(entries, 'common/twin', None)
            opts = render_axis_options(entries)
            return begin + opts

        # Left axis becomes anchor axis regardless of export order.
        entries = remove_option(entries, 'name')
        entries = remove_option(entries, 'width')
        entries = set_option(entries, 'common/twin-main', None)
        opts = render_axis_options(entries)
        return begin + opts

    axis_begin_re = re.compile(r'(\\begin\{axis\})(\s*\[.*?\])', re.DOTALL)
    return axis_begin_re.sub(repl, code)
