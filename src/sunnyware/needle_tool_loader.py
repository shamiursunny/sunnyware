# src/sunnyware/needle_tool_loader.py
def load_needle_tools(schema_list: list[dict]) -> list:
    """
    Converts a list of raw JSON schema dictionaries into a list of callables
    with the schema attached to the `_needle_tool` attribute.
    """
    tools = []
    for schema in schema_list:
        name = schema["name"]

        def _make_placeholder(tool_name):
            def _placeholder(**kwargs):
                return kwargs
            _placeholder.__name__ = tool_name
            return _placeholder

        fn = _make_placeholder(name)
        fn._needle_tool = schema
        tools.append(fn)
    return tools

def build_schema_from_tool(tool):
    """
    Constructs a JSON schema dictionary from a tool object with
    name, description, and parameters attributes.
    """
    return {
        "name": tool.name,
        "description": tool.description,
        "parameters": tool.parameters
    }
