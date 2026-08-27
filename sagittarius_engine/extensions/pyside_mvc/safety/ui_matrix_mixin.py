import logging


class UIMatrixMixin:
    """
    @brief Mixin that provides Data-Driven UI Matrix capabilities to any QWidget.

    @details
    By inheriting this mixin, a View (or Widget) can define its UI state transitions
    (enabled/disabled) using an external JSON matrix instead of imperative code.

    Usage:
        class MyView(QWidget, UIMatrixMixin):
            def __init__(self):
                super().__init__()
                # ... setup UI ...

            def on_state_changed(self, mode_enum):
                self.apply_ui_mode(mode_enum.value, "my_view_key")
    """

    def set_ui_matrix(self, matrix_data: dict) -> None:
        """
        @brief Inject the UI matrix data into the mixin.
        @param matrix_data A dictionary containing the UI state configurations.
        """
        self._ui_matrix = matrix_data

    def apply_ui_mode(self, mode: str, section_key: str = "main") -> None:
        """
        @brief Applies a specific UI mode by toggling widget states based on the matrix.

        @param mode The string representation of the mode (e.g. "IDLE", "LOCKED").
        @param section_key The root key in the JSON file containing the mode definitions.

        @details
        The JSON structure is expected to be:
        {
            "section_key": {
                "MODE_STRING": {
                    "widget_attr_name": true/false
                }
            }
        }
        """
        if not hasattr(self, "_ui_matrix"):
            raise RuntimeError(
                "[UIMatrixMixin] UI Matrix not loaded. Call load_ui_matrix() first."
            )

        logger = logging.getLogger("App.UI")

        section = self._ui_matrix.get(section_key, {})

        # Normalize Enum to string value if necessary
        mode_key = getattr(mode, "value", mode)
        if not isinstance(mode_key, str):
            mode_key = str(mode_key)

        if mode_key not in section:
            logger.warning(
                f"[UIMatrixMixin] Mode '{mode}' (key: {mode_key}) not found in matrix section '{section_key}'."
            )
            return

        logger.debug(
            f"[UIMatrixMixin] Applying mode '{mode_key}' for section '{section_key}'"
        )
        config = section[mode_key]

        # Use reflection (getattr) to find the widget inside this class instance
        for widget_name, is_enabled in config.items():
            widget = getattr(self, widget_name, None)
            if widget:
                # Type safe check for Qt Widgets having setEnabled
                if hasattr(widget, "setEnabled"):
                    widget.setEnabled(is_enabled)
            else:
                print(
                    f"[UIMatrixMixin] Warning: Widget '{widget_name}' not found in {self.__class__.__name__}"
                )
