_REGISTRY = {}


def db_route(route_name: str):
    """Decoratore che registra un handler per una route DB."""
    def decorator(fn):
        _REGISTRY[route_name] = fn
        return fn
    return decorator


def get_handler(route_name: str):
    if route_name not in _REGISTRY:
        raise KeyError(f"db route non trovata: '{route_name}'")
    return _REGISTRY[route_name]
