def clean_json_encoding(json_data):
    if isinstance(json_data, str):
        # Maneja las secuencias de escape unicode y los caracteres especiales
        return json_data.encode('raw_unicode_escape').decode('unicode_escape')
    elif isinstance(json_data, dict):
        return {k: clean_json_encoding(v) for k, v in json_data.items()}
    elif isinstance(json_data, list):
        return [clean_json_encoding(item) for item in json_data]
    else:
        return json_data