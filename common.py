from enum import Enum
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

def as_tikz(fig, ax, ax2=None, axis_width: str = r'\\linewidth', axis_height: str = r'.8\\linewidth', **kwargs) -> str:
    # https://github.com/ErwindeGelder/matplot2tikz/blob/main/src/matplot2tikz/_save.py#L68
    s = matplot2tikz.get_tikz_code(fig,
            axis_width=axis_width,
            axis_height=axis_height,
            include_disclaimer=False,
            **kwargs)
    s = tikz_sanitize_labels(s)
    if ax2 is not None:
        s = tikz_fix_overlapping_x_ticks(s)
        right_y_labels = get_y_labels(ax2)
        s = fix_twin_axis_layout(s, axis_width, right_y_labels)
    return s

def get_y_labels(ax):
    ax.figure.canvas.draw()  # Ensures ticks/formatters are resolved
    return [t.get_text() for t in ax.get_yticklabels()]

def tikz_sanitize_labels(s: str) -> str:
    '''
    Sanitize references in `label` and `addlegendimage` by replacing invalid characters.
    '''
    label_re = re.compile(r'\\label\{([^}]*)\}')
    legend_re = re.compile(r'(\\addlegendimage\{.*?/pgfplots/refstyle=)([^,}]+)', re.DOTALL)
    s = label_re.sub(lambda m: f"\\label{{{sanitize(m.group(1))}}}", s)
    s = legend_re.sub(lambda m: f"{m.group(1)}{sanitize(m.group(2))}", s)
    return s

def sanitize(s: str) -> str:
    '''
    Replace invalid characters with underscores.
    '''
    s = re.sub(r'[^A-Za-z0-9_\-:]+', '_', s)
    s = re.sub(r'_+', '_', s)  # Collapse multiple underscores
    return s.strip('_')  # Avoid leading/trailing underscores

def tikz_fix_overlapping_x_ticks(s: str) -> (bool, str):
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
    return axis_begin_re.sub(repl, s)

def fix_twin_axis_layout(
    tikz: str,
    axis_width: str,
    right_y_labels: list[str],
    tick_length_pt: float = 2.5,
    inner_sep_pt: float = 0.5,
) -> str:
    count = 0
    main_name = "mainaxis"

    def repl(m):
        nonlocal count
        begin, opts = m.groups()
        count += 1

        # First axis
        if count == 1:
            right_padding_em = compute_padding_em(right_y_labels, tick_length_pt, inner_sep_pt)

            effective_width = f"{{{axis_width} - {right_padding_em:.2f}em}}"

            width_re = re.compile(r'width\s*=\s*([^,\]]+)')
            if width_re.search(opts):
                opts = width_re.sub(f'width={effective_width}', opts)
            else:
                opts = opts.replace('[', f'[width={effective_width},', 1)

            if "name=" not in opts:
                opts = opts.replace('[', f'[name={main_name},', 1)

            if "scale only axis" not in opts:
                opts = opts.replace('[', '[scale only axis,', 1)

            return begin + opts
        # Secondary axes
        else:
            injection = (
                f'at={{({main_name}.south west)}},'
                'anchor=south west,'
                'overlay,'
                'axis x line=none,'
                'xtick=\\empty,'
                'xticklabels=\\empty,'
            )

            # Remove accidental scaling
            opts = re.sub(r'scale only axis\s*,?', '', opts)

            opts = opts.replace('[', f'[{injection}', 1)

            return begin + opts

    axis_begin_re = re.compile(r'(\\begin\{axis\})(\s*\[.*?\])', re.DOTALL)
    return axis_begin_re.sub(repl, tikz)

def compute_padding_em(
    labels: [str],
    tick_length_pt: float = 2.5,
    inner_sep_pt: float = 0.5,
    safety_em: float = 0.5,
) -> float:
    '''
    Compute total right-axis padding in em.
    '''
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
