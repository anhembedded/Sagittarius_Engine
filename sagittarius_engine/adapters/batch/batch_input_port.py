import csv
import json
import os
from collections.abc import Iterator
from typing import Any

from sagittarius_engine.adapters.batch.const import FILE_TYPE_CSV, FILE_TYPE_JSON
from sagittarius_engine.base.base_input_port import BaseInputPort
from sagittarius_engine.exceptions import PathTraversalError
from sagittarius_engine.kernel.app_runner import COMMAND_KEY, EXIT_COMMAND


class BatchInputPort(BaseInputPort):
    """
    @brief Batch Input Port that reads data from CSV or JSON files.
    """

    def process(self, filepath: str) -> None:
        pass

    def __init__(
        self,
        file_path: str,
        file_type: str = FILE_TYPE_CSV,
        base_path: str = "",
    ) -> None:
        super().__init__()

        # SECURITY: Fail-closed path traversal defense.
        # By defaulting base_path to "" (current working directory),
        # we strictly confine the file resolution and avoid a fail-open state.
        base_path_real = os.path.realpath(base_path)
        full_path = (
            os.path.join(base_path, file_path)
            if not os.path.isabs(file_path)
            else file_path
        )
        full_path_real = os.path.realpath(full_path)

        if os.path.commonpath([base_path_real, full_path_real]) != base_path_real:
            raise PathTraversalError(f"Path traversal detected: {file_path}")
        self.file_path = full_path_real

        self.file_type = file_type
        self._iterator: Iterator[dict[str, Any]] | None = None
        self._initialized = False

    def _init_iterator(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        if not os.path.exists(self.file_path):
            if self.logger:
                self.logger.error(f"File not found: {self.file_path}")
            self._iterator = iter([])
            return
        try:
            if self.file_type == FILE_TYPE_CSV:
                with open(self.file_path, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    data = list(reader)
                    self._iterator = iter(data)
            elif self.file_type == FILE_TYPE_JSON:
                with open(self.file_path, encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._iterator = iter(data)
                    else:
                        if self.logger:
                            self.logger.error(
                                "JSON file must contain an array of objects"
                            )
                        self._iterator = iter([])
            else:
                if self.logger:
                    self.logger.error(f"Unsupported file type: {self.file_type}")
                self._iterator = iter([])
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error reading file {self.file_path}: {e}")
            self._iterator = iter([])

    def receive(self) -> dict[str, Any]:
        """
        @brief Yields rows from the batch file one by one. After the last row, returns the exit command.
        """
        self._init_iterator()
        try:
            if self._iterator is not None:
                return next(self._iterator)
            return {COMMAND_KEY: EXIT_COMMAND}
        except StopIteration:
            return {COMMAND_KEY: EXIT_COMMAND}
