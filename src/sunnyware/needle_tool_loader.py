# src/sunnyware/needle_tool_loader.py
def load_needle_tools(schema_list: list[dict]) -> list:
    """
    Converts a list of raw JSON schema dictionaries into a list of callables
    with the schema attached to the `_needle_tool` attribute.
    """
    tools = []
    for schema in schema_list:
        name = schema["name"]

        # Create a placeholder function. It will never be executed because we
        # only use the `complete()` method for routing.
        def _make_placeholder(tool_name):
            def _placeholder(**kwargs):
                return kwargs
            _placeholder.__name__ = tool_name
            return _placeholder

        fn = _make_placeholder(name)
        # Attach the raw schema to the attribute Needle inspects.
        fn._needle_tool = schema
        tools.append(fn)
    return tools
