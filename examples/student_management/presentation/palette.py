"""A distinct palette for this sample — deliberately not the reference
consumer's black/gold identity (Sagittarius_Elite_Warrior's), so this app
reads as its own thing rather than a copy-paste. Supplies exactly the 10
tokens `tokens.vocabulary.REQUIRED_COLOUR_TOKENS` requires; nothing more."""

STUDENT_MANAGEMENT_PALETTE: dict[str, str] = {
    "bg": "#101820",
    "bgSidebar": "#0c131a",
    "bgCard": "#16202b",
    "bgCardHeader": "#1c2833",
    "border": "#2a3744",
    "textPrimary": "#e6edf3",
    "accent": "#4fb0ff",
    "success": "#3ecf8e",
    "danger": "#f2545b",
    "muted": "#7c8b99",
}

#: image://icons/<name>/<token> lookups — kept distinct from the UI palette
#: per configure_app_qml()'s own docstring ("the two vocabularies evolved
#: independently").
STUDENT_MANAGEMENT_ICON_PALETTE: dict[str, str] = {
    "muted": "#7c8b99",
    "accent": "#4fb0ff",
}
