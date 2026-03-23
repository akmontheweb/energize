import ast
from pathlib import Path

ROOT = Path(r"c:/akhil/projects/energize")

TARGETS = [
    ROOT / "backend" / "app",
    ROOT / "backend" / "alembic",
]


def get_py_files():
    files = []
    for base in TARGETS:
        for p in base.rglob("*.py"):
            files.append(p)
    return sorted(files)


def get_insert_lineno(node):
    if getattr(node, "decorator_list", None):
        return min(d.lineno for d in node.decorator_list)
    return node.lineno


def line_indent(line):
    stripped = line.lstrip(" \t")
    return line[: len(line) - len(stripped)]


def has_existing_description(lines, lineno, indent):
    i = lineno - 2
    while i >= 0 and lines[i].strip() == "":
        i -= 1
    if i >= 0:
        prev = lines[i]
        if prev.startswith(indent + "# Description:"):
            return True
    return False


def build_func_comment(node, indent):
    args = []
    fn_args = node.args
    for a in fn_args.posonlyargs:
        args.append(a.arg)
    for a in fn_args.args:
        args.append(a.arg)
    if fn_args.vararg:
        args.append("*" + fn_args.vararg.arg)
    for a in fn_args.kwonlyargs:
        args.append(a.arg)
    if fn_args.kwarg:
        args.append("**" + fn_args.kwarg.arg)

    if args:
        inputs = ", ".join(args)
    else:
        inputs = "None"

    if node.returns is not None:
        output = ast.unparse(node.returns)
    else:
        output = "Varies by implementation"

    desc = f"Function `{node.name}` implementation."

    return [
        f"{indent}# Description: {desc}\n",
        f"{indent}# Inputs: {inputs}\n",
        f"{indent}# Output: {output}\n",
        f"{indent}# Exceptions: Propagates exceptions raised by internal operations.\n",
    ]


def build_class_comment(node, indent):
    desc = f"Class `{node.name}` encapsulates related data and behavior for this module."
    return [f"{indent}# Description: {desc}\n"]


def apply_to_file(path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return 0

    inserts = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            lineno = get_insert_lineno(node)
            if lineno < 1 or lineno > len(lines):
                continue
            indent = line_indent(lines[lineno - 1])
            if has_existing_description(lines, lineno, indent):
                continue
            if isinstance(node, ast.ClassDef):
                block = build_class_comment(node, indent)
            else:
                block = build_func_comment(node, indent)
            inserts.append((lineno, block))

    if not inserts:
        return 0

    inserts.sort(key=lambda x: x[0], reverse=True)
    for lineno, block in inserts:
        lines[lineno - 1:lineno - 1] = block

    path.write_text("".join(lines), encoding="utf-8")
    return len(inserts)


def main():
    total = 0
    changed = 0
    for py in get_py_files():
        count = apply_to_file(py)
        if count:
            changed += 1
            total += count
            print(f"updated {py}: {count}")
    print(f"changed_files={changed} inserted_blocks={total}")


if __name__ == "__main__":
    main()
