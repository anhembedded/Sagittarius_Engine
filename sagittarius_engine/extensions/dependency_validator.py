import importlib.util
import sys
from typing import Any

from sagittarius_engine.interfaces.i_extension import IExtension


class DependencyValidatorExtension(IExtension[Any]):
    """
    Fail-Fast Dependency Validator Extension.
    Checks for the presence of critical packages during boot.
    """

    def __init__(self, required_packages: list[str]):
        self.required_packages = required_packages

    def register(self, context: Any) -> None:
        pass

    def boot(self, context: Any) -> None:
        missing_packages = []
        for package in self.required_packages:
            # find_spec checks if the module exists without executing its code
            if importlib.util.find_spec(package) is None:
                missing_packages.append(package)

        if missing_packages:
            error_msg = (
                f"CRITICAL FAULT: Missing required dependencies: {', '.join(missing_packages)}\n"
                f"Please fix by running:\n"
                f"    pip install {' '.join(missing_packages)}"
            )
            # Use engine logger if available, otherwise print
            if hasattr(context, "logger"):
                context.logger.error(error_msg)
            else:
                print(error_msg)

            # Fail-fast
            sys.exit(1)
        else:
            if hasattr(context, "logger"):
                context.logger.info(
                    "Pre-flight check passed. All critical dependencies found."
                )
            else:
                print("INFO: Pre-flight check passed. All critical dependencies found.")

    def shutdown(self, context: Any) -> None:
        pass
