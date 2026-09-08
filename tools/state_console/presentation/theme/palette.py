"""The console's own palette — `ADR-002` §2.2: deliberately not inherited
from `examples/student_management`'s. A diagnostic console that looked like
one of the apps it inspects would be actively confusing when both are on
screen. Supplies exactly the 11 tokens `tokens.vocabulary.REQUIRED_COLOUR_TOKENS`
requires; nothing more."""

STATE_CONSOLE_PALETTE: dict[str, str] = {
    "bg": "#14121a",
    "bgSidebar": "#0f0d14",
    "bgCard": "#1e1b26",
    "bgCardHeader": "#262231",
    "border": "#332e40",
    "textPrimary": "#ece8f5",
    "accent": "#a682ff",
    "success": "#3ecf8e",
    "warning": "#e0a23c",
    "danger": "#f2545b",
    "muted": "#8b8499",
}

#: image://icons/<name>/<token> lookups — kept distinct from the UI palette
#: per configure_app_qml()'s own docstring ("the two vocabularies evolved
#: independently").
STATE_CONSOLE_ICON_PALETTE: dict[str, str] = {
    "muted": "#8b8499",
    "accent": "#a682ff",
}
