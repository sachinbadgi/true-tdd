"""
Copy this file to your project root as mutmut_config.py.
Customise the skip rules and test command routing for your codebase.

Verified context properties (mutmut 3.x):
  context.filename              — path of file being mutated
  context.current_source_line   — source line text
  context.skip                  — set True to skip this mutation
"""

def pre_mutation(context):
    # Skip low-signal lines
    if any(s in context.current_source_line for s in [
        "logger.", "print(", "# pragma", "__repr__", "__str__", "logging."
    ]):
        context.skip = True
        return
