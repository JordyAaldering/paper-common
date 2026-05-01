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
            y_labels_to_top: bool = True,
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
    if y_labels_to_top:
        code = tikz_move_ylabels_to_top(code)
    if ax2 is not None:
        code = tikz_fix_overlapping_x_ticks(code)
        right_y_labels = get_y_labels(ax2)
        code = fix_twin_axis_layout(code, axis_width, right_y_labels)
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
    legend_re = re.compile(r'(\\addlegendimage\{.*?/pgfplots/refstyle=)([^,}]+)', re.DOTALL)
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

def tikz_move_ylabels_to_top(code: str) -> str:
    count = 0

    def repl(m):
        nonlocal count
        begin, opts = m.groups()
        count += 1

        # Keep default behavior for axes without explicit ylabel.
        if not re.search(r'ylabel\s*=', opts):
            return m.group(0)

        # Place left-axis label near top-left and right-axis label near top-right.
        if count == 1:
            style = 'at={(rel axis cs:0,1)},anchor=south west,rotate=-90,yshift=2pt'
        else:
            style = 'at={(rel axis cs:1,1)},anchor=south east,rotate=-90,yshift=2pt'

        style_re = re.compile(r'ylabel\s+style\s*=\s*\{.*?\}', re.DOTALL)
        if style_re.search(opts):
            opts = style_re.sub(f'ylabel style={{{style}}}', opts, count=1)
        else:
            opts = re.sub(r'\]\s*$', f',ylabel style={{{style}}}]', opts, count=1)

        return begin + opts

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
    right_y_labels: list[str],
    tick_length_pt: float = 2.5,
    inner_sep_pt: float = 0.5,
) -> str:
    main_name = "mainaxis"
    right_padding_em = compute_padding_em(right_y_labels, tick_length_pt, inner_sep_pt)
    effective_width = f"{{{axis_width} - {right_padding_em:.2f}em}}"

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

    def parse_options(opts: str) -> list[tuple[str, str | None]]:
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

    def render_options(entries: list[tuple[str, str | None]]) -> str:
        pieces = []
        for key, value in entries:
            if value is None:
                pieces.append(key)
            else:
                pieces.append(f'{key}={value}')
        return '[' + ','.join(pieces) + ']'

    def remove_key(entries: list[tuple[str, str | None]], key: str) -> list[tuple[str, str | None]]:
        return [(k, v) for k, v in entries if k != key]

    def set_key(entries: list[tuple[str, str | None]], key: str, value: str | None) -> list[tuple[str, str | None]]:
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

    def repl(m):
        begin, opts = m.groups()
        entries = parse_options(opts)

        # Normalize width on both axes and remove any existing scale-only marker for re-adding on primary.
        entries = remove_key(entries, 'scale only axis')
        entries = set_key(entries, 'width', effective_width)

        if has_right_y_axis(opts):
            # Tie right axis to left axis rectangle and hide duplicate x-axis visuals.
            for key in ('at', 'anchor', 'axis x line', 'xtick', 'xticklabels', 'overlay'):
                entries = remove_key(entries, key)

            injection = [
                ('at', f'{{({main_name}.south west)}}'),
                ('anchor', 'south west'),
                ('overlay', None),
                ('axis x line', 'none'),
                ('xtick', r'\empty'),
                ('xticklabels', r'\empty'),
            ]

            opts = render_options(injection + entries)
            return begin + opts

        # Left axis becomes anchor axis regardless of export order.
        entries = set_key(entries, 'name', main_name)
        opts = render_options(entries)
        return begin + opts

    axis_begin_re = re.compile(r'(\\begin\{axis\})(\s*\[.*?\])', re.DOTALL)
    return axis_begin_re.sub(repl, code)

def compute_padding_em(
    labels: list[str],
    tick_length_pt: float = 2.5,
    inner_sep_pt: float = 0.5,
    safety_em: float = 0.5,
) -> float:
    '''
    Compute total right-axis padding in em.
    '''
    if not labels:
        return tick_length_pt * 0.1 + inner_sep_pt * 0.1 + safety_em

    max_label = max(labels, key=len)
    max_label_width = estimate_label_width_em(max_label)

    PT_TO_EM = 0.1  # Approximately 1em = 10pt
    tick_length_em = tick_length_pt * PT_TO_EM
    inner_sep_em = inner_sep_pt * PT_TO_EM

    return max_label_width + tick_length_em + inner_sep_em + safety_em

def estimate_label_width_em(label: str, font_scale: float = 0.7) -> float:
    '''
    Characters are approximately 0.55em at normalsize.
    Assuming a scaling factor of 0.7 for scriptsize.
    '''
    return len(label) * 0.55 * font_scale
