from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IView(Protocol):
    """
    @brief The one method a Presenter needs from any View, regardless of
    rendering backend.

    @details A structural (duck-typed) contract, matching this framework's
    existing convention for cross-cutting protocols (e.g.
    `database_module.IDatabaseContext`) rather than an ABC a View must
    inherit from — `QmlHostView`-based and plain-`QWidget`-based Views can
    both satisfy this with no shared base class beyond `BaseView` itself.

    Today `QmlHostView` subclasses expose a QML-specific two-call sequence
    instead (`set_view_model(vm)` then `load_qml(filename)`) because a
    Presenter written against them already knows it's talking to QML.
    `IView.bind()` exists for the opposite case: a Presenter written once
    against `IView` that must not know or care whether the concrete View
    it was handed loads a `.qml` document or builds a `QFormLayout` by
    hand — each concrete View's own `bind()` does whatever its own
    rendering backend needs internally.
    """

    def bind(self, view_model: Any) -> None:
        """
        @brief Wires this View to `view_model` — the one thing every View,
        QML or QWidget, must do before it can be shown.
        @param view_model Whatever ViewModel this View's Presenter
        constructed for it. Typed `Any` deliberately: IView does not — and
        must not — know anything about screen-specific ViewModel shapes.
        """
        ...
