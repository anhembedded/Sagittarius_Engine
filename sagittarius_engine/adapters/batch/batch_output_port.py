import json
import os
from typing import Any

from sagittarius_engine.base.base_output_port import BaseOutputPort
from sagittarius_engine.exceptions import PathTraversalError


class BatchOutputPort(BaseOutputPort):
    """
    @brief Batch Output Port that appends output to a file.
    """

    def __init__(self, output_path: str, base_path: str = "") -> None:
        super().__init__()

        base_path_real = os.path.realpath(base_path)
        full_path = (
            os.path.join(base_path, output_path)
            if not os.path.isabs(output_path)
            else output_path
        )
        full_path_real = os.path.realpath(full_path)

        if os.path.commonpath([base_path_real, full_path_real]) != base_path_real:
            raise PathTraversalError(f"Path traversal detected: {output_path}")

        self.output_path = full_path_real
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)

    def present(self, result: Any) -> None:
        """
        @brief Appends the result to the output file.
        """
        try:
            with open(self.output_path, "a", encoding="utf-8") as f:
                if isinstance(result, dict):
                    f.write(json.dumps(result) + "\n")
                else:
                    f.write(str(result) + "\n")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error writing to output file: {e}")

    def present_error(self, error: Exception) -> None:
        """
        @brief Appends the error to the output file.
        """
        try:
            with open(self.output_path, "a", encoding="utf-8") as f:
                f.write(f"ERROR: {error}\n")
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error writing to output file: {e}")
