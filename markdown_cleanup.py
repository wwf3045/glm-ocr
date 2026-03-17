from __future__ import annotations

from collections import Counter
import re
from pathlib import Path


_INLINE_SHELL_PREFIX = r"(^|[\s\(\[（{+\-*/=,:，；;])"
_INLINE_SHELL_SUFFIX = r"(?=$|[\s\)\]）}.,:，；;!?。])"
_INLINE_SHELL_BOTH_RE = re.compile(
    _INLINE_SHELL_PREFIX + r"\$\$([^\$\n]+?)\$\$" + _INLINE_SHELL_SUFFIX
)
_INLINE_SHELL_LEADING_RE = re.compile(
    _INLINE_SHELL_PREFIX + r"\$\$([^\$\n]+?)\$" + _INLINE_SHELL_SUFFIX
)
_INLINE_SHELL_TRAILING_RE = re.compile(
    _INLINE_SHELL_PREFIX + r"\$([^\$\n]+?)\$\$" + _INLINE_SHELL_SUFFIX
)
_SPACED_CONTROL_WORD_PATTERNS = [
    ("mid", re.compile(r"\\mid([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("to", re.compile(r"\\to([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("in", re.compile(r"\\in([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("ni", re.compile(r"\\ni([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("notin", re.compile(r"\\notin([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("subseteq", re.compile(r"\\subseteq([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("supseteq", re.compile(r"\\supseteq([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("subset", re.compile(r"\\subset([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("supset", re.compile(r"\\supset([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("cup", re.compile(r"\\cup([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("cap", re.compile(r"\\cap([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("setminus", re.compile(r"\\setminus([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("times", re.compile(r"\\times([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("leq", re.compile(r"\\leq([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("geq", re.compile(r"\\geq([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("neq", re.compile(r"\\neq([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("approx", re.compile(r"\\approx([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("sim", re.compile(r"\\sim([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("simeq", re.compile(r"\\simeq([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("equiv", re.compile(r"\\equiv([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("cong", re.compile(r"\\cong([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("propto", re.compile(r"\\propto([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("parallel", re.compile(r"\\parallel([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("perp", re.compile(r"\\perp([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("forall", re.compile(r"\\forall([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("exists", re.compile(r"\\exists([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("implies", re.compile(r"\\implies([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("iff", re.compile(r"\\iff([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("leftarrow", re.compile(r"\\leftarrow([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("rightarrow", re.compile(r"\\rightarrow([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("leftrightarrow", re.compile(r"\\leftrightarrow([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("Leftarrow", re.compile(r"\\Leftarrow([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("Rightarrow", re.compile(r"\\Rightarrow([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("Leftrightarrow", re.compile(r"\\Leftrightarrow([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("longrightarrow", re.compile(r"\\longrightarrow([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("longleftrightarrow", re.compile(r"\\longleftrightarrow([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("xrightarrow", re.compile(r"\\xrightarrow([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("xleftarrow", re.compile(r"\\xleftarrow([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("xleftrightarrow", re.compile(r"\\xleftrightarrow([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("xRightarrow", re.compile(r"\\xRightarrow([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("sin", re.compile(r"\\sin([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("cos", re.compile(r"\\cos([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("tan", re.compile(r"\\tan([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("cot", re.compile(r"\\cot([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("sec", re.compile(r"\\sec([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("csc", re.compile(r"\\csc([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("sinh", re.compile(r"\\sinh([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("cosh", re.compile(r"\\cosh([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("tanh", re.compile(r"\\tanh([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("coth", re.compile(r"\\coth([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("log", re.compile(r"\\log([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("ln", re.compile(r"\\ln([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("exp", re.compile(r"\\exp([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("lim", re.compile(r"\\lim([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("max", re.compile(r"\\max([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("min", re.compile(r"\\min([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("sup", re.compile(r"\\sup([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("det", re.compile(r"\\det([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("dim", re.compile(r"\\dim([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("ker", re.compile(r"\\ker([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("deg", re.compile(r"\\deg([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("gcd", re.compile(r"\\gcd([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("Pr", re.compile(r"\\Pr([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("Re", re.compile(r"\\Re([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("Im", re.compile(r"\\Im([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("alpha", re.compile(r"\\alpha([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("beta", re.compile(r"\\beta([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("gamma", re.compile(r"\\gamma([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("delta", re.compile(r"\\delta([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("epsilon", re.compile(r"\\epsilon([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("varepsilon", re.compile(r"\\varepsilon([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("zeta", re.compile(r"\\zeta([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("eta", re.compile(r"\\eta([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("theta", re.compile(r"\\theta([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("vartheta", re.compile(r"\\vartheta([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("iota", re.compile(r"\\iota([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("kappa", re.compile(r"\\kappa([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("lambda", re.compile(r"\\lambda([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("mu", re.compile(r"\\mu([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("nu", re.compile(r"\\nu([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("xi", re.compile(r"\\xi([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("pi", re.compile(r"\\pi([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("varpi", re.compile(r"\\varpi([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("rho", re.compile(r"\\rho([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("varrho", re.compile(r"\\varrho([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("sigma", re.compile(r"\\sigma([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("varsigma", re.compile(r"\\varsigma([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("tau", re.compile(r"\\tau([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("upsilon", re.compile(r"\\upsilon([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("phi", re.compile(r"\\phi([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("varphi", re.compile(r"\\varphi([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("chi", re.compile(r"\\chi([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("psi", re.compile(r"\\psi([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("omega", re.compile(r"\\omega([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("Gamma", re.compile(r"\\Gamma([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("Delta", re.compile(r"\\Delta([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("Theta", re.compile(r"\\Theta([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("Lambda", re.compile(r"\\Lambda([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("Xi", re.compile(r"\\Xi([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("Pi", re.compile(r"\\Pi([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("Sigma", re.compile(r"\\Sigma([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("Upsilon", re.compile(r"\\Upsilon([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("Phi", re.compile(r"\\Phi([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("Psi", re.compile(r"\\Psi([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("Omega", re.compile(r"\\Omega([A-Za-z]+)(?=$|[^A-Za-z])")),
]
_SPACED_CONTROL_WORD_EXACT = {
    "inf",
    "int",
    "top",
    "infty",
    "subseteq",
    "subsetneq",
    "subsetneqq",
    "subseteqq",
    "supseteq",
    "supsetneq",
    "supsetneqq",
    "supseteqq",
    "cupdot",
    "capdot",
    "barwedge",
    "limsup",
    "liminf",
    "sinh",
    "cosh",
    "tanh",
    "coth",
    "leqslant",
    "geqslant",
}
_BRACED_CONTROL_WORD_PATTERNS = [
    ("operatorname", re.compile(r"\\operatorname([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("mathrm", re.compile(r"\\mathrm([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("mathbf", re.compile(r"\\mathbf([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("mathit", re.compile(r"\\mathit([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("mathsf", re.compile(r"\\mathsf([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("mathtt", re.compile(r"\\mathtt([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("mathbb", re.compile(r"\\mathbb([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("mathcal", re.compile(r"\\mathcal([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("mathfrak", re.compile(r"\\mathfrak([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("boldsymbol", re.compile(r"\\boldsymbol([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("vec", re.compile(r"\\vec([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("hat", re.compile(r"\\hat([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("bar", re.compile(r"\\bar([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("tilde", re.compile(r"\\tilde([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("dot", re.compile(r"\\dot([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("ddot", re.compile(r"\\ddot([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("widehat", re.compile(r"\\widehat([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("widetilde", re.compile(r"\\widetilde([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("overline", re.compile(r"\\overline([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("underline", re.compile(r"\\underline([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("overrightarrow", re.compile(r"\\overrightarrow([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("overleftarrow", re.compile(r"\\overleftarrow([A-Za-z]+)(?=$|[^A-Za-z])")),
    ("text", re.compile(r"\\text([A-Za-z]+)(?=$|[^A-Za-z])")),
]
_REJOIN_SPLIT_CONTROL_WORD_PATTERNS = [
    (re.compile(r"\\subset\s+eq\b"), r"\\subseteq"),
    (re.compile(r"\\subset\s+neq\b"), r"\\subsetneq"),
    (re.compile(r"\\subset\s+neqq\b"), r"\\subsetneqq"),
    (re.compile(r"\\subset\s+eqq\b"), r"\\subseteqq"),
    (re.compile(r"\\supset\s+eq\b"), r"\\supseteq"),
    (re.compile(r"\\supset\s+neq\b"), r"\\supsetneq"),
    (re.compile(r"\\supset\s+neqq\b"), r"\\supsetneqq"),
    (re.compile(r"\\supset\s+eqq\b"), r"\\supseteqq"),
    (re.compile(r"\\lim\s+sup\b"), r"\\limsup"),
    (re.compile(r"\\lim\s+inf\b"), r"\\liminf"),
]
_KNOWN_CONTROL_WORDS = {
    *[prefix for prefix, _ in _SPACED_CONTROL_WORD_PATTERNS],
    *[prefix for prefix, _ in _BRACED_CONTROL_WORD_PATTERNS],
    *_SPACED_CONTROL_WORD_EXACT,
    "leftarrow",
    "rightarrow",
    "leftrightarrow",
    "Leftarrow",
    "Rightarrow",
    "Leftrightarrow",
    "longrightarrow",
    "longleftrightarrow",
    "xrightarrow",
    "xleftarrow",
    "xleftrightarrow",
    "xRightarrow",
}
_COMMON_LATEX_AUDIT_COMMANDS = {
    "frac",
    "dfrac",
    "tfrac",
    "cfrac",
    "binom",
    "dbinom",
    "tbinom",
    "sqrt",
    "left",
    "right",
    "big",
    "Big",
    "bigg",
    "Bigg",
    "bigl",
    "bigr",
    "biggl",
    "biggr",
    "Bigl",
    "Bigr",
    "Biggl",
    "Biggr",
    "sum",
    "prod",
    "coprod",
    "iint",
    "iiint",
    "iiiint",
    "oint",
    "partial",
    "nabla",
    "cdot",
    "cdots",
    "ldots",
    "vdots",
    "ddots",
    "dots",
    "dotsc",
    "dotsb",
    "dotso",
    "dotsi",
    "pm",
    "mp",
    "div",
    "ast",
    "star",
    "circ",
    "bullet",
    "triangle",
    "triangleleft",
    "triangleright",
    "trianglelefteq",
    "trianglerighteq",
    "square",
    "diamond",
    "emptyset",
    "varnothing",
    "cupdot",
    "capdot",
    "uplus",
    "sqcup",
    "sqcap",
    "bigcup",
    "bigcap",
    "bigvee",
    "bigwedge",
    "bigodot",
    "bigotimes",
    "bigoplus",
    "biguplus",
    "bigsqcup",
    "oplus",
    "ominus",
    "otimes",
    "oslash",
    "odot",
    "land",
    "lor",
    "lnot",
    "neg",
    "mapsto",
    "longmapsto",
    "hookrightarrow",
    "hookleftarrow",
    "uparrow",
    "downarrow",
    "updownarrow",
    "Uparrow",
    "Downarrow",
    "Updownarrow",
    "Longrightarrow",
    "Longleftarrow",
    "Longleftrightarrow",
    "rightsquigarrow",
    "leadsto",
    "le",
    "ge",
    "ne",
    "ll",
    "gg",
    "prec",
    "succ",
    "preceq",
    "succeq",
    "langle",
    "rangle",
    "lceil",
    "rceil",
    "lfloor",
    "rfloor",
    "lbrace",
    "rbrace",
    "quad",
    "qquad",
    "enspace",
    "thinspace",
    "medspace",
    "thickspace",
    "hspace",
    "vspace",
    "limits",
    "nolimits",
    "displaystyle",
    "textstyle",
    "scriptstyle",
    "scriptscriptstyle",
    "textrm",
    "textbf",
    "textit",
    "overbrace",
    "underbrace",
    "overset",
    "underset",
    "pmod",
    "bmod",
    "mod",
    "begin",
    "end",
    "array",
    "matrix",
    "pmatrix",
    "bmatrix",
    "vmatrix",
    "Vmatrix",
    "cases",
    "aligned",
    "align",
    "gathered",
    "gather",
    "split",
    "eqalign",
    "label",
    "tag",
    "ref",
    "eqref",
    "not",
    "prime",
    "ell",
    "dagger",
    "ddagger",
    "stackrel",
    "backslash",
    "triangleq",
    "varOmega",
    "hline",
    "vline",
    "cline",
    "arg",
    "angle",
    "substack",
    "boxed",
    "coloneqq",
    "eqqcolon",
    "bot",
    "top",
    "arccos",
    "arcsin",
    "arctan",
    "arccot",
    "colon",
    "gtrless",
    "lessgtr",
    "nexists",
    "bf",
    "rm",
    "it",
    "cal",
    "sf",
    "tt",
    "bfseries",
    "rmfamily",
    "mathop",
    "choose",
    "atop",
    "cr",
    "qquad",
    "quad",
    "quad",
    "S",
}
_AUDIT_ALLOWED_CONTROL_WORDS = _KNOWN_CONTROL_WORDS | _COMMON_LATEX_AUDIT_COMMANDS
_AUDIT_REPORT_NAME_PREFIX = "_math_command_audit"
_CONTROL_WORD_RE = re.compile(r"\\([A-Za-z]+)")


def is_escaped_dollar(text: str, index: int) -> bool:
    backslashes = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return backslashes % 2 == 1


def is_standalone_block_delimiter(text: str, index: int) -> bool:
    if not text.startswith("$$", index):
        return False

    left = index - 1
    while left >= 0 and text[left] in " \t":
        left -= 1

    right = index + 2
    while right < len(text) and text[right] in " \t":
        right += 1

    left_ok = left < 0 or text[left] == "\n"
    right_ok = right >= len(text) or text[right] == "\n"
    return left_ok and right_ok


def find_closing_math_delimiter(text: str, start: int, delimiter: str) -> int:
    cursor = start
    while cursor < len(text):
        if text[cursor] == "\\":
            cursor += 2
            continue
        if delimiter == "$$":
            if (
                text.startswith("$$", cursor)
                and not is_escaped_dollar(text, cursor)
                and is_standalone_block_delimiter(text, cursor)
            ):
                return cursor
            cursor += 1
            continue
        if (
            text[cursor] == "$"
            and not is_escaped_dollar(text, cursor)
            and not is_standalone_block_delimiter(text, cursor)
        ):
            return cursor
        cursor += 1
    return -1


def find_next_inline_double_dollar(text: str, start: int) -> int:
    cursor = start
    while cursor < len(text) - 1:
        if (
            text.startswith("$$", cursor)
            and not is_escaped_dollar(text, cursor)
            and not is_standalone_block_delimiter(text, cursor)
        ):
            return cursor
        cursor += 1
    return -1


def contains_unescaped_dollar(text: str) -> bool:
    cursor = 0
    while cursor < len(text):
        if text[cursor] == "\\":
            cursor += 2
            continue
        if text[cursor] == "$" and not is_escaped_dollar(text, cursor):
            return True
        cursor += 1
    return False


def sanitize_math_delimiters(text: str) -> str:
    parts: list[str] = []
    cursor = 0
    while cursor < len(text):
        if text[cursor] != "$" or is_escaped_dollar(text, cursor):
            parts.append(text[cursor])
            cursor += 1
            continue

        delimiter = (
            "$$"
            if text.startswith("$$", cursor) and is_standalone_block_delimiter(text, cursor)
            else "$"
        )
        close_index = find_closing_math_delimiter(text, cursor + len(delimiter), delimiter)
        if close_index == -1:
            parts.append(delimiter)
            cursor += len(delimiter)
            continue

        inner = text[cursor + len(delimiter):close_index]
        inner = inner.lstrip(" \t").rstrip(" \t")
        parts.append(delimiter)
        parts.append(inner)
        parts.append(delimiter)
        cursor = close_index + len(delimiter)

    return "".join(parts)


def collapse_compact_double_math(text: str) -> str:
    parts: list[str] = []
    cursor = 0
    while cursor < len(text):
        if (
            text.startswith("$$", cursor)
            and not is_escaped_dollar(text, cursor)
            and not is_standalone_block_delimiter(text, cursor)
        ):
            close_index = find_next_inline_double_dollar(text, cursor + 2)
            if close_index != -1:
                inner = text[cursor + 2:close_index]
                if inner.strip(" \t\n") and not contains_unescaped_dollar(inner):
                    line_start = text.rfind("\n", 0, cursor) + 1
                    line_end = text.find("\n", close_index + 2)
                    if line_end == -1:
                        line_end = len(text)
                    before = text[line_start:cursor].strip(" \t")
                    after = text[close_index + 2:line_end].strip(" \t")
                    normalized_inner = inner.strip(" \t\n")
                    if "\n" in inner or (not before and not after):
                        parts.append("$$\n")
                        parts.append(normalized_inner)
                        parts.append("\n$$")
                    else:
                        parts.append("$")
                        parts.append(inner.strip(" \t"))
                        parts.append("$")
                    cursor = close_index + 2
                    continue

        parts.append(text[cursor])
        cursor += 1

    return "".join(parts)


def collapse_shell_wrapped_math(text: str) -> str:
    text = collapse_compact_double_math(text)
    normalized_lines: list[str] = []
    for line in text.split("\n"):
        previous = None
        while line != previous:
            previous = line
            line = _INLINE_SHELL_BOTH_RE.sub(
                lambda match: f"{match.group(1)}${match.group(2).strip(' \t')}$",
                line,
            )
            line = _INLINE_SHELL_LEADING_RE.sub(
                lambda match: f"{match.group(1)}${match.group(2).strip(' \t')}$",
                line,
            )
            line = _INLINE_SHELL_TRAILING_RE.sub(
                lambda match: f"{match.group(1)}${match.group(2).strip(' \t')}$",
                line,
            )

        normalized_lines.append(line)

    return "\n".join(normalized_lines)


def separate_inline_double_dollars(text: str) -> str:
    parts: list[str] = []
    cursor = 0
    while cursor < len(text):
        if (
            text.startswith("$$", cursor)
            and not is_escaped_dollar(text, cursor)
            and not is_standalone_block_delimiter(text, cursor)
        ):
            # OCR often squeezes two adjacent inline delimiters into `$$`.
            # Split them so Obsidian/MathJax won't treat them as display math.
            parts.append("$ $")
            cursor += 2
            continue

        parts.append(text[cursor])
        cursor += 1

    return "".join(parts)


def repair_squeezed_control_words(segment: str) -> str:
    if "\\" not in segment:
        return segment

    previous = None
    current = segment
    while current != previous:
        previous = current
        for prefix, pattern in _SPACED_CONTROL_WORD_PATTERNS:
            def _replace(match: re.Match[str]) -> str:
                suffix = match.group(1)
                if f"{prefix}{suffix}" in _SPACED_CONTROL_WORD_EXACT:
                    return match.group(0)
                if suffix in _KNOWN_CONTROL_WORDS:
                    return f"\\{prefix}\\{suffix}"
                return f"\\{prefix} {suffix}"

            current = pattern.sub(_replace, current)
        for prefix, pattern in _BRACED_CONTROL_WORD_PATTERNS:
            current = pattern.sub(
                lambda match, prefix=prefix: f"\\{prefix}{{{match.group(1)}}}",
                current,
            )
    return current


def rejoin_split_control_words(text: str) -> str:
    current = text
    previous = None
    while current != previous:
        previous = current
        for pattern, replacement in _REJOIN_SPLIT_CONTROL_WORD_PATTERNS:
            current = pattern.sub(replacement, current)
    return current


def normalize_math_control_words(text: str) -> str:
    parts: list[str] = []
    cursor = 0
    while cursor < len(text):
        if text[cursor] != "$" or is_escaped_dollar(text, cursor):
            parts.append(text[cursor])
            cursor += 1
            continue

        delimiter = (
            "$$"
            if text.startswith("$$", cursor) and is_standalone_block_delimiter(text, cursor)
            else "$"
        )
        close_index = find_closing_math_delimiter(text, cursor + len(delimiter), delimiter)
        if close_index == -1:
            parts.append(delimiter)
            cursor += len(delimiter)
            continue

        inner = text[cursor + len(delimiter):close_index]
        parts.append(delimiter)
        parts.append(repair_squeezed_control_words(inner))
        parts.append(delimiter)
        cursor = close_index + len(delimiter)

    return "".join(parts)


def iter_math_segments(text: str):
    cursor = 0
    while cursor < len(text):
        if text[cursor] != "$" or is_escaped_dollar(text, cursor):
            cursor += 1
            continue

        delimiter = (
            "$$"
            if text.startswith("$$", cursor) and is_standalone_block_delimiter(text, cursor)
            else "$"
        )
        close_index = find_closing_math_delimiter(text, cursor + len(delimiter), delimiter)
        if close_index == -1:
            cursor += len(delimiter)
            continue

        inner_start = cursor + len(delimiter)
        inner_end = close_index
        yield cursor, close_index + len(delimiter), delimiter, text[inner_start:inner_end]
        cursor = close_index + len(delimiter)


def _line_number_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _excerpt_for_span(text: str, start: int, end: int) -> str:
    line_start = text.rfind("\n", 0, start)
    line_start = 0 if line_start == -1 else line_start + 1
    line_end = text.find("\n", end)
    line_end = len(text) if line_end == -1 else line_end
    excerpt = text[line_start:line_end].strip()
    return re.sub(r"\s+", " ", excerpt)[:220]


def _make_audit_finding(
    text: str,
    abs_start: int,
    abs_end: int,
    kind: str,
    token: str,
    suggestion: str = "",
    confidence: str = "high",
) -> dict:
    return {
        "kind": kind,
        "token": token,
        "suggestion": suggestion,
        "confidence": confidence,
        "line": _line_number_for_offset(text, abs_start),
        "context": _excerpt_for_span(text, abs_start, abs_end),
        "start": abs_start,
        "end": abs_end,
    }


def _is_math_audit_report(path: Path) -> bool:
    return path.name.startswith(_AUDIT_REPORT_NAME_PREFIX)


def audit_markdown_math_text(text: str) -> dict:
    findings: list[dict] = []
    kind_counter: Counter[str] = Counter()
    token_counter: Counter[str] = Counter()

    for segment_start, _, delimiter, inner in iter_math_segments(text):
        inner_offset = segment_start + len(delimiter)
        flagged_starts: set[int] = set()

        for pattern, replacement in _REJOIN_SPLIT_CONTROL_WORD_PATTERNS:
            for match in pattern.finditer(inner):
                abs_start = inner_offset + match.start()
                abs_end = inner_offset + match.end()
                finding = _make_audit_finding(
                    text,
                    abs_start,
                    abs_end,
                    kind="split_control_word",
                    token=match.group(0),
                    suggestion=match.expand(replacement),
                )
                findings.append(finding)
                kind_counter[finding["kind"]] += 1
                token_counter[finding["token"]] += 1
                flagged_starts.add(abs_start)

        for prefix, pattern in _SPACED_CONTROL_WORD_PATTERNS:
            for match in pattern.finditer(inner):
                suffix = match.group(1)
                if f"{prefix}{suffix}" in _SPACED_CONTROL_WORD_EXACT:
                    continue
                abs_start = inner_offset + match.start()
                abs_end = inner_offset + match.end()
                suggestion = (
                    f"\\{prefix}\\{suffix}"
                    if suffix in _KNOWN_CONTROL_WORDS
                    else f"\\{prefix} {suffix}"
                )
                finding = _make_audit_finding(
                    text,
                    abs_start,
                    abs_end,
                    kind="glued_control_word",
                    token=match.group(0),
                    suggestion=suggestion,
                )
                findings.append(finding)
                kind_counter[finding["kind"]] += 1
                token_counter[finding["token"]] += 1
                flagged_starts.add(abs_start)

        for prefix, pattern in _BRACED_CONTROL_WORD_PATTERNS:
            for match in pattern.finditer(inner):
                abs_start = inner_offset + match.start()
                abs_end = inner_offset + match.end()
                finding = _make_audit_finding(
                    text,
                    abs_start,
                    abs_end,
                    kind="glued_braced_control_word",
                    token=match.group(0),
                    suggestion=f"\\{prefix}{{{match.group(1)}}}",
                )
                findings.append(finding)
                kind_counter[finding["kind"]] += 1
                token_counter[finding["token"]] += 1
                flagged_starts.add(abs_start)

        for match in _CONTROL_WORD_RE.finditer(inner):
            command = match.group(1)
            if command in _AUDIT_ALLOWED_CONTROL_WORDS:
                continue
            abs_start = inner_offset + match.start()
            if abs_start in flagged_starts:
                continue
            abs_end = inner_offset + match.end()
            finding = _make_audit_finding(
                text,
                abs_start,
                abs_end,
                kind="unknown_control_word",
                token=match.group(0),
                confidence="low",
            )
            findings.append(finding)
            kind_counter[finding["kind"]] += 1
            token_counter[finding["token"]] += 1

    findings.sort(key=lambda item: (item["line"], item["start"], item["kind"]))
    return {
        "total_findings": len(findings),
        "by_kind": dict(kind_counter),
        "top_tokens": token_counter.most_common(20),
        "findings": findings,
    }


def audit_markdown_math_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    audit = audit_markdown_math_text(text)
    audit["path"] = str(path)
    return audit


def audit_markdown_tree(root: Path) -> dict:
    root = root.resolve()
    files: list[dict] = []
    totals = Counter()
    top_tokens = Counter()
    scanned = 0

    for path in sorted(root.rglob("*.md")):
        if _is_math_audit_report(path):
            continue
        scanned += 1
        audit = audit_markdown_math_file(path)
        audit["relative_path"] = str(path.relative_to(root))
        files.append(audit)
        totals.update(audit["by_kind"])
        for token, count in audit["top_tokens"]:
            top_tokens[token] += count

    files_with_findings = [file_audit for file_audit in files if file_audit["total_findings"]]
    return {
        "root": str(root),
        "scanned_files": scanned,
        "files_with_findings": len(files_with_findings),
        "total_findings": sum(file_audit["total_findings"] for file_audit in files),
        "by_kind": dict(totals),
        "top_tokens": top_tokens.most_common(20),
        "files": files_with_findings,
    }


def render_math_audit_report(root: Path, audit: dict) -> str:
    lines = [
        "# OCR Markdown 数学命令审计报告",
        "",
        f"- 扫描目录：`{root}`",
        f"- 扫描 Markdown：`{audit['scanned_files']}`",
        f"- 命中可疑项文件：`{audit['files_with_findings']}`",
        f"- 可疑项总数：`{audit['total_findings']}`",
        "",
    ]

    if audit["by_kind"]:
        lines.extend(
            [
                "## 分类统计",
                "",
                *[f"- `{kind}`：`{count}`" for kind, count in sorted(audit["by_kind"].items())],
                "",
            ]
        )

    if audit["top_tokens"]:
        lines.extend(
            [
                "## 高频可疑命令",
                "",
                *[f"- `{token}`：`{count}`" for token, count in audit["top_tokens"]],
                "",
            ]
        )

    if not audit["files"]:
        lines.extend(["## 结果", "", "未发现剩余可疑数学命令。", ""])
        return "\n".join(lines)

    lines.extend(["## 文件明细", ""])
    for file_audit in audit["files"]:
        lines.append(f"### `{file_audit['relative_path']}`")
        lines.append("")
        lines.append(f"- 可疑项：`{file_audit['total_findings']}`")
        for finding in file_audit["findings"][:80]:
            confidence = "高置信" if finding["confidence"] == "high" else "低置信"
            line = (
                f"- 第 {finding['line']} 行 [{confidence}/{finding['kind']}] "
                f"`{finding['token']}`"
            )
            if finding["suggestion"]:
                line += f" -> 建议 `{finding['suggestion']}`"
            lines.append(line)
            if finding["context"]:
                lines.append(f"  上下文：`{finding['context']}`")
        if len(file_audit["findings"]) > 80:
            remaining = len(file_audit["findings"]) - 80
            lines.append(f"- 其余 {remaining} 项已省略，请直接打开源文件复核。")
        lines.append("")

    return "\n".join(lines)


def write_math_audit_report(root: Path, report_path: Path | None = None) -> dict:
    root = root.resolve()
    audit = audit_markdown_tree(root)
    target = report_path.resolve() if report_path else root / f"{_AUDIT_REPORT_NAME_PREFIX}.md"
    target.write_text(render_math_audit_report(root, audit), encoding="utf-8")
    audit["report_path"] = str(target)
    return audit


def normalize_ocr_markdown(text: str) -> str:
    if not text:
        return text
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = rejoin_split_control_words(text)
    text = sanitize_math_delimiters(text)
    text = collapse_shell_wrapped_math(text)
    text = separate_inline_double_dollars(text)
    return normalize_math_control_words(text)


def write_markdown_text(path: Path, content: str) -> None:
    path.write_text(normalize_ocr_markdown(content), encoding="utf-8")


def repair_markdown_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    normalized = normalize_ocr_markdown(original)
    if normalized == original:
        return False
    path.write_text(normalized, encoding="utf-8")
    return True
