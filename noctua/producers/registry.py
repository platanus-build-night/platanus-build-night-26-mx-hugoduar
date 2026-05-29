from importlib.metadata import entry_points

_cache = {}

def get_producer(key: str):
    if key in _cache:
        return _cache[key]
    for ep in entry_points(group="noctua.producers"):
        if ep.name == key:
            cls = ep.load()
            inst = cls()
            _cache[key] = inst
            return inst
    raise LookupError(f"producer not found: {key}")
