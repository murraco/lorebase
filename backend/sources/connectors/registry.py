from collections.abc import Callable

from sources.connectors.base import Connector

_registry: dict[str, type[Connector]] = {}


def register_connector(source_type: str) -> Callable[[type[Connector]], type[Connector]]:
    def decorator(connector_class: type[Connector]) -> type[Connector]:
        _registry[source_type] = connector_class
        return connector_class

    return decorator


def get_connector_class(source_type: str) -> type[Connector]:
    try:
        return _registry[source_type]
    except KeyError:
        raise ValueError(f"No connector registered for source type: {source_type!r}") from None
