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

def as_tikz(fig, axis_width: str, axis_height: str, **kwargs) -> str:
    # https://github.com/ErwindeGelder/matplot2tikz/blob/main/src/matplot2tikz/_save.py#L68
    s = matplot2tikz.get_tikz_code(fig,
            axis_width=axis_width,
            axis_height=axis_height,
            include_disclaimer=False,
            **kwargs)
    s = tikz_sanitize_labels(s)
    s = tikz_fix_overlapping_x_ticks(s)
    return s

def tikz_fix_overlapping_x_ticks(s: str) -> str:
    '''
    With twin axis plots, `xtick` and `xticklabels` is being set for both axes, causing overlapping ticks.
    Replace ticks and labels of all but the first axis with empty ones to fix this issue.
    '''
    count = 0

    def repl(m):
        nonlocal count
        begin, opts = m.groups()
        count += 1

        if count == 1:
            # Leave first axis untouched
            return m.group(0)

        xtick_re = re.compile(r'xtick\s*=\s*\{.*?\}', re.DOTALL)
        xlabels_re = re.compile(r'xticklabels\s*=\s*\{.*?\}', re.DOTALL)
        opts = xtick_re.sub('xtick={}', opts)
        opts = xlabels_re.sub('xticklabels={}', opts)
        return begin + opts

    axis_begin_re = re.compile(r'(\\begin\{axis\})(\s*\[.*?\])', re.DOTALL)
    return axis_begin_re.sub(repl, s)

def tikz_sanitize_labels(s: str) -> str:
    '''
    Sanitize references in `\label` and `\addlegendimage` by replacing invalid characters.
    '''
    label_re = re.compile(r'\\label\{([^}]*)\}')
    legend_re = re.compile(r'(\\addlegendimage\{[^=]+=)([^}]*)\}')
    s = label_re.sub(lambda m: f"\\label{{{sanitize(m.group(1))}}}", s)
    s = legend_re.sub(lambda m: f"{m.group(1)}{sanitize(m.group(2))}}}", s)
    return s

def sanitize(s: str) -> str:
    '''
    Replace invalid characters with underscores.
    '''
    s = re.sub(r'[^A-Za-z0-9_\-:]+', '_', s)
    # Collapse multiple underscores
    s = re.sub(r'_+', '_', s)
    # Avoid leading/trailing underscores
    return s.strip('_')
