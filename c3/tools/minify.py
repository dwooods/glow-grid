"""Small, dependency-free JS and CSS minifier for c3/tools/build_site.py.

It only removes comments and unneeded whitespace. It never renames anything, never rewrites code and never touches the inside of strings,
template literals or regex literals, so the packed page behaves exactly like web/. Line breaks are kept (one per source line break, indentation
dropped) so automatic semicolon insertion works the same as in the source. The editor's scripts share one global scope, so renaming
(what a full minifier does) is not safe here anyway.

    python3 c3/tools/minify.py            self-test
"""
import re

_IDENT = re.compile(r'[A-Za-z0-9_$\u0080-￿]')
# a '/' after one of these starts a regular expression, not a division
_REGEX_AFTER_WORDS = {'return', 'typeof', 'case', 'in', 'of', 'delete', 'void', 'throw', 'new', 'else', 'do', 'instanceof', 'yield', 'await'}
_REGEX_AFTER_PUNCT = set('(,=:[!&|?{};+-*%<>~^')


def _skip_string(s, i, q):
    j = i + 1
    while j < len(s):
        c = s[j]
        if c == '\\':
            j += 2
            continue
        if c == q:
            return j + 1
        if c == '\n':
            raise ValueError('unterminated string at offset %d' % i)
        j += 1
    raise ValueError('unterminated string at offset %d' % i)


def _skip_regex(s, i):
    j = i + 1
    in_class = False
    while j < len(s):
        c = s[j]
        if c == '\\':
            j += 2
            continue
        if c == '\n':
            raise ValueError('unterminated regex at offset %d' % i)
        if in_class:
            if c == ']':
                in_class = False
        elif c == '[':
            in_class = True
        elif c == '/':
            j += 1
            while j < len(s) and _IDENT.match(s[j]):   # flags
                j += 1
            return j
        j += 1
    raise ValueError('unterminated regex at offset %d' % i)


def _skip_template(s, i):
    """Returns the index just past the closing backtick; ${ ... } holds code, which may hold more strings and templates."""
    j = i + 1
    while j < len(s):
        c = s[j]
        if c == '\\':
            j += 2
            continue
        if c == '`':
            return j + 1
        if c == '$' and s[j + 1:j + 2] == '{':
            j = _skip_code_until_close_brace(s, j + 2)
            continue
        j += 1
    raise ValueError('unterminated template at offset %d' % i)


def _skip_code_until_close_brace(s, j):
    depth = 1
    while j < len(s):
        c = s[j]
        if c in '"\'':
            j = _skip_string(s, j, c)
            continue
        if c == '`':
            j = _skip_template(s, j)
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    raise ValueError('unterminated ${ in template')


def js_minify(s):
    out = []                  # pieces of output
    last = ''                 # last significant character written
    last_word = ''            # the identifier or keyword just written, if the last token was a word
    i, n = 0, len(s)
    pending_ws = ''           # '' | ' ' | '\n'

    def emit(tok, kind):
        nonlocal pending_ws, last, last_word
        if pending_ws == '\n':
            if out and out[-1] != '\n':
                out.append('\n')
        elif pending_ws == ' ' and out and out[-1] != '\n':
            a, b = last, tok[0]
            if (_IDENT.match(a) and _IDENT.match(b)) or (a in '+-' and b == a) or (a == '/' and b in '/*') or (a in '+-' and b in '+-'):
                out.append(' ')
            elif a in '.' and b.isdigit() or (a.isdigit() and b == '.'):
                out.append(' ')
            elif kind == 'regex' and _IDENT.match(a):
                out.append(' ')
        pending_ws = ''
        out.append(tok)
        last = tok[-1]
        last_word = tok if kind == 'word' else ''

    while i < n:
        c = s[i]
        if c in ' \t\r\f\v ﻿':
            if not pending_ws:
                pending_ws = ' '
            i += 1
        elif c == '\n':
            pending_ws = '\n'
            i += 1
        elif c == '/' and s[i + 1:i + 2] == '/':
            while i < n and s[i] != '\n':
                i += 1
            if not pending_ws:
                pending_ws = ' '
        elif c == '/' and s[i + 1:i + 2] == '*':
            j = s.find('*/', i + 2)
            if j < 0:
                raise ValueError('unterminated comment')
            if '\n' in s[i:j]:
                pending_ws = '\n'
            elif not pending_ws:
                pending_ws = ' '
            i = j + 2
        elif c in '"\'':
            j = _skip_string(s, i, c)
            emit(s[i:j], 'string'); i = j
        elif c == '`':
            j = _skip_template(s, i)
            emit(s[i:j], 'template'); i = j
        elif c == '/':
            regex_ok = (not out) or last in _REGEX_AFTER_PUNCT or last_word in _REGEX_AFTER_WORDS
            if regex_ok:
                j = _skip_regex(s, i)
                emit(s[i:j], 'regex'); i = j
            else:
                emit('/', 'punct'); i += 1
        elif _IDENT.match(c):
            j = i
            while j < n and _IDENT.match(s[j]):
                j += 1
            emit(s[i:j], 'word'); i = j
        else:
            emit(c, 'punct'); i += 1
    text = ''.join(out)
    return text.strip('\n') + '\n'


def css_minify(s):
    strings = []          # strings are lifted out so no whitespace rule can touch them, then put back
    out = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == '/' and s[i + 1:i + 2] == '*':
            j = s.find('*/', i + 2)
            if j < 0:
                raise ValueError('unterminated css comment')
            i = j + 2
            out.append(' ')
        elif c in '"\'':
            j = _skip_string(s, i, c)
            strings.append(s[i:j])
            out.append('\x00%d\x00' % (len(strings) - 1)); i = j
        else:
            out.append(c); i += 1
    t = re.sub(r'\s+', ' ', ''.join(out))
    # spaces are only dropped where CSS never needs them: around { } ; , and before a closing brace's semicolon
    t = re.sub(r' ?([{};,]) ?', r'\1', t)
    t = t.replace(';}', '}').strip()
    t = re.sub(r'\x00(\d+)\x00', lambda m: strings[int(m.group(1))], t)
    return t + '\n'


if __name__ == '__main__':
    cases = [
        ('a = b / c / d;', 'a=b/c/d;'),
        ('x = /ab+c/g.test(y);  // t\nz', 'x=/ab+c/g.test(y);\nz'),
        ('return /[/]x/.test(s)', 'return /[/]x/.test(s)'),
        ('a + +b; c - -d; e = a+ ++b', 'a+ +b;c- -d;e=a+ ++b'),
        ('const t = `a ${ b + `c ${d}` }   e\n  f`;', 'const t=`a ${ b + `c ${d}` }   e\n  f`;'),
        ('let a = "x  y"; /* c */ let b = \'q\\\'  r\';', 'let a="x  y";let b=\'q\\\'  r\';'),
        ('if (a) {\n    b();\n}\n\n\n  else c();', 'if(a){\nb();\n}\nelse c();'),
        ('return\n  x', 'return\nx'),
        ('a = 1 .toString()', 'a=1 .toString()'),
        ('typeof /x/ === "object"', 'typeof /x/==="object"'),
    ]
    bad = 0
    for src, want in cases:
        got = js_minify(src).strip('\n')
        if got != want:
            bad += 1
            print('JS MISMATCH\n  src :', repr(src), '\n  want:', repr(want), '\n  got :', repr(got))
    css = 'a , b  { color : red ; margin:0 auto ; }\n/* x */ @media (min-width: 600px) { .c > d { content: "a  b"; } }\n'
    want = 'a,b{color : red;margin:0 auto}@media (min-width: 600px){.c > d{content: "a  b"}}'
    if css_minify(css).strip() != want:
        bad += 1; print('CSS MISMATCH\n  want:', repr(want), '\n  got :', repr(css_minify(css).strip()))
    print('minify self-test: %s' % ('FAILED (%d)' % bad if bad else 'ok'))
    raise SystemExit(1 if bad else 0)
