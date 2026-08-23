import os

from sagittarius_engine.exceptions import PathTraversalError
from sagittarius_engine.interfaces.i_file_storage import IFileStorage


class LocalFileStorage(IFileStorage):
    """
    @brief File Storage implementation for the Local File System.
    """

    def __init__(self, base_path: str = "") -> None:
        """
        @brief Constructor.
        @param base_path The base directory for file operations. Defaults to current directory.
        """
        self.base_path = base_path

    def _get_full_path(self, path: str) -> str:
        if path is None:
            raise ValueError("Path cannot be None")

        base_path_real = os.path.realpath(self.base_path)
        full_path = os.path.join(self.base_path, path)
        full_path_real = os.path.realpath(full_path)

        if os.path.commonpath([base_path_real, full_path_real]) != base_path_real:
            raise PathTraversalError(f"Path traversal detected: {path}")

        return full_path_real

    def read(self, path: str) -> bytes:
        """@brief Reads a file from local storage."""
        full_path = self._get_full_path(path)
        with open(full_path, "rb") as f:
            return f.read()

    def write(self, path: str, data: bytes | str) -> None:
        """@brief Writes data to local storage. Creates directories if necessary."""
        full_path = self._get_full_path(path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        mode = "wb" if isinstance(data, bytes) else "w"
        with open(full_path, mode) as f:
            f.write(data)

    def delete(self, path: str) -> None:
        """@brief Deletes a file from local storage."""
        full_path = self._get_full_path(path)
        if os.path.exists(full_path):
            os.remove(full_path)

    def exists(self, path: str) -> bool:
        """@brief Checks if a file exists in local storage."""
        return os.path.exists(self._get_full_path(path))
