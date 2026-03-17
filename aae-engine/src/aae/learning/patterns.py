def extract_pattern(output: str):
    if "IndexError" in output:
        return "index_error"
    if "NoneType" in output:
        return "null_error"
    if "TypeError" in output:
        return "type_error"
    return "other"
