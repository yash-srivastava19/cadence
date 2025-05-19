# Fill these.
import re

def apply_diff(parent_program, diffs):
    
    def _apply_diff_in_strs(file_str, diffs, start_marker="### START_BLOCK", end_marker="### END_BLOCK"):
        """
        Replace code blocks in file_str marked by custom start and end markers.
        Diffs should be a list of replacement code blocks, applied in order of appearance.
        """
        # Build regex pattern for custom markers
        pattern = re.compile(
            rf"{re.escape(start_marker)}[\s\S]*?{re.escape(end_marker)}", re.MULTILINE
        )
        diff_iter = iter(diffs)

        def replacer(match):
            try:
                replacement = next(diff_iter)
                return f"{start_marker}\n{replacement}\n{end_marker}"
            except StopIteration:
                return match.group(0)  # No more diffs, leave as is

        return pattern.sub(replacer, file_str)
    pass


# def apply_diff(file_str, diffs, start_marker="### START_BLOCK", end_marker="### END_BLOCK"):
#     pass

diffs = [
    "def foo():\n    print('first replacement')",
    "def bar():\n    print('second replacement')"
]

file_str = """
### START_BLOCK
def foo():
    print('old foo')
### END_BLOCK

print('something else')

### START_BLOCK
def bar():
    print('old bar')
### END_BLOCK
"""

print("PARENT FILE: ")
print(id(file_str))
print(file_str)

new_code = apply_diff(file_str, diffs)

print("CHILD FILE: ")
print(id(new_code))
print(new_code)