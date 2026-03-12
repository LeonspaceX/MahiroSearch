import lancedb
from pathlib import Path


_connections: dict[str, lancedb.DBConnection] = {}


def get_db_connection(data_dir: Path) -> lancedb.DBConnection:
    key = str(data_dir)
    if key not in _connections:
        data_dir.mkdir(parents=True, exist_ok=True)
        _connections[key] = lancedb.connect(str(data_dir))
    return _connections[key]
