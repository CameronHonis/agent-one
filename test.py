from collections.abc import Callable
import os
import sys
import inspect
import importlib
import traceback


def _file_to_module_path(proj_root: str, file_path: str) -> str:
    file_name = os.path.basename(file_path)
    mod_dir = os.path.dirname(os.path.abspath(file_path))
    rel_mod_path = os.path.relpath(mod_dir, proj_root)
    if rel_mod_path == ".":
        return file_name[:-3]  # Remove .py
    else:
        return rel_mod_path.replace(os.sep, ".") + "." + file_name[:-3]


def _adjacent_lines_of_code(file_name, line, context_lines) -> str:
    builder = []
    with open(file_name, "r") as f:
        lines = f.readlines()

    start = max(0, line - context_lines - 1)
    end = min(len(lines), line + context_lines)
    pad_width = len(str(end))

    builder.append("    Code context:")
    for i, line_txt in enumerate(lines[start:end], start + 1):
        prefix = "\033[33m>> " if i == line else "   "
        padded_line_num = f"{i:>{pad_width}}"
        suffix = "\033[0m" if i == line else ""
        builder.append(f"   {prefix}{padded_line_num}: {line_txt.rstrip()}{suffix}")
    return "\n".join(builder)


def _should_ignore(dir_path: str, exclude: list[str]) -> bool:
    for excl_dir in exclude:
        if excl_dir in dir_path:
            return True
    return False


def get_test_funcs_deeply(
    root_path: str, exclude: list[str]
) -> dict[str, list[Callable]]:
    """
    Find all functions that match the expected testing format (starts with `_test_`
    or ends with `_test`) across all python modules recursively from a given directory

    Args:
        project_root: The root directory of your project
        exclude: A list of directory names to ignore

    Returns:
        dictionary mapping module names to lists of underscore function names
    """
    sys.path.insert(0, root_path)

    # module_name -> [underscore_functions]
    rtn = dict()

    for dir_path, _, file_names in os.walk(root_path):
        if _should_ignore(dir_path, exclude):
            continue

        for file_name in file_names:
            if file_name.endswith(".py") and not file_name.startswith("__"):
                file_path = os.path.join(dir_path, file_name)
                mod_path = _file_to_module_path(root_path, file_path)

                # Skip if this module has special characters/invalid identifiers
                should_skip = not all(
                    part.isidentifier() for part in mod_path.split(".")
                )
                if should_skip:
                    continue

                try:
                    mod = importlib.import_module(mod_path)
                except (ImportError, ModuleNotFoundError) as e:
                    print(f"Could not import {mod_path}: {e}")

                underscore_funcs = [
                    obj
                    for name, obj in inspect.getmembers(mod)
                    if inspect.isfunction(obj)
                    and (name.startswith("_test_") or name.endswith("_test"))
                ]
                if underscore_funcs:
                    rtn[mod_path] = underscore_funcs

    return rtn


def format_failed(func, e):
    exc_type, exc_value, exc_traceback = sys.exc_info()
    tb = traceback.extract_tb(exc_traceback)
    filename, line, _, text = tb[-1]

    # Print error information
    print(f"❌ {func.__name__} failed:")
    print(f"   Error: {type(e).__name__}: {str(e)}")
    print(f"   File: {filename}, line {line}")
    print(_adjacent_lines_of_code(filename, line, 4))


def run_tests(exclude: list[str]):
    _project_root = os.path.dirname(os.path.abspath(__file__))
    print(f"Scanning project at: {_project_root}")

    _test_funcs = get_test_funcs_deeply(_project_root, exclude)

    if _test_funcs:
        print("\nTest results:")
        for module, functions in sorted(_test_funcs.items()):
            print(f"\n{module}:")
            sorted_funcs = sorted(functions, key=lambda func: func.__name__)
            for func in sorted_funcs:
                try:
                    func()
                    print(f"✅ {func.__name__}")
                except Exception as e:  # pylint: disable=broad-except
                    format_failed(func, e)
    else:
        print("\nNo tests found :(")


if __name__ == "__main__":
    exclude_dirs = [".venv", "node_modules"]

    run_tests(exclude_dirs)
