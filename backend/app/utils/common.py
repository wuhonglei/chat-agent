def remove_leading_whitespace(text: str) -> str:
    """移除每行前面的空白符"""
    lines = text.split('\n')
    processed_lines = [line.lstrip() for line in lines if line.strip()]
    return '\n'.join(processed_lines)


def remove_all_whitespace(text: str) -> str:
    """移除每行前面和后面的空白符"""
    lines = text.split('\n')
    processed_lines = [line.strip() for line in lines if line.strip()]
    return '\n'.join(processed_lines)


def exclude_fields(dict_data: dict, fields: list[str]) -> dict:
    """移除指定字段"""
    return {k: v for k, v in dict_data.items() if k not in fields}
