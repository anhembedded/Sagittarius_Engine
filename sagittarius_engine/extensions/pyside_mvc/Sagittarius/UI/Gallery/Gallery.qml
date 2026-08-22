import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Sagittarius.UI 1.0

// Runnable catalog of every Widget Kit component, driven entirely by real
// Theme tokens — no component here authors a single literal visual value.
// This is the gallery ui-architecture.md §6.2 requires: "a design system
// with no way to see everything it offers in one place is not verifiable."
// EPIC-001C. Not registered in qmldir — loaded directly by URL as a
// top-level document (see render_gallery_snapshot.py), the same way any
// consuming app's screen QML is loaded, not imported as a reusable type.
Rectangle {
    id: root
    width: 960
    height: 1200
    color: Theme.bg

    component SectionLabel: Text {
        color: Theme.accent
        font.pixelSize: Theme.fontSizeSm
        font.bold: true
        font.letterSpacing: 1
        textFormat: Text.PlainText
    }

    component Caption: Text {
        color: Theme.muted
        font.pixelSize: Theme.fontSizeSm
        textFormat: Text.PlainText
    }

    readonly property var sampleTrades: [
        { symbol: "BTCUSDT", side: "LONG", qty: 0.50, price: 65210.50, pnl: 128.40 },
        { symbol: "ETHUSDT", side: "SHORT", qty: 2.00, price: 3180.25, pnl: -42.10 },
        { symbol: "SOLUSDT", side: "LONG", qty: 15.0, price: 142.80, pnl: 305.60 },
        { symbol: "BNBUSDT", side: "LONG", qty: 4.20, price: 612.35, pnl: -8.75 }
    ]
    readonly property var tradeColumns: [
        { key: "symbol", title: "Symbol", weight: 2 },
        { key: "side", title: "Side", weight: 1 },
        { key: "qty", title: "Qty", weight: 1, align: Text.AlignRight },
        {
            key: "price", title: "Price", weight: 1, align: Text.AlignRight,
            formatter: function (v) { return "$" + v.toFixed(2) }
        },
        {
            key: "pnl", title: "PnL", weight: 1, align: Text.AlignRight,
            formatter: function (v) { return (v >= 0 ? "+" : "") + v.toFixed(2) }
        }
    ]

    ScrollView {
        anchors.fill: parent
        contentWidth: availableWidth
        clip: true

        ColumnLayout {
            width: root.width
            spacing: Theme.spaceXl

            ColumnLayout {
                Layout.fillWidth: true
                Layout.margins: Theme.spaceXl
                spacing: Theme.spaceXs

                Text {
                    text: "SAGITTARIUS UI ENGINE"
                    color: Theme.accent
                    font.pixelSize: Theme.fontSizeLg
                    font.bold: true
                    font.letterSpacing: 1
                    textFormat: Text.PlainText
                }
                Caption { text: "Widget Kit Gallery — every component, real tokens, zero hand-authored pixels" }
            }

            // ---- Buttons -------------------------------------------------
            ColumnLayout {
                Layout.fillWidth: true
                Layout.leftMargin: Theme.spaceXl
                Layout.rightMargin: Theme.spaceXl
                spacing: Theme.spaceMd

                SectionLabel { text: "BUTTONS — StatefulButton" }
                RowLayout {
                    spacing: Theme.spaceMd
                    StatefulButton { text: "Load History"; iconSource: "clock"; accentBorder: Theme.border }
                    StatefulButton { text: "Selected"; iconSource: "check"; isActive: true }
                    StatefulButton { text: "Confirm"; accentBorder: Theme.success }
                    StatefulButton { text: "Danger"; accentBorder: Theme.danger }
                    StatefulButton { text: "Disabled"; enabled: false }
                }
            }

            // ---- Fields ----------------------------------------------------
            ColumnLayout {
                Layout.fillWidth: true
                Layout.leftMargin: Theme.spaceXl
                Layout.rightMargin: Theme.spaceXl
                spacing: Theme.spaceMd

                SectionLabel { text: "FIELDS — FieldBackground, StyledCheck, DateTimePicker" }
                RowLayout {
                    spacing: Theme.spaceLg
                    TextField {
                        placeholderText: "Symbol (e.g. BTCUSDT)"
                        color: Theme.textPrimary
                        font.pixelSize: Theme.fontSizeMd
                        Layout.preferredWidth: 220
                        background: FieldBackground {}
                    }
                    StyledCheck { text: "Auto-restart on crash"; checked: true }
                    StyledCheck { text: "Dry-run mode"; checked: false }
                }
                //: Added because the new gallery-coverage guard caught it
                //: missing — DateTimePicker had been registered in qmldir
                //: since before the gallery existed and was never shown,
                //: which is precisely the decay that guard exists to stop.
                //: Shown standalone rather than inside TimeRangeCard (which
                //: embeds two of them) so its own chrome — the calendar
                //: toggle button — is visible.
                DateTimePicker {
                    Layout.preferredWidth: 220
                    text: "2026-08-23 09:30"
                }
            }

            // ---- Cards -------------------------------------------------
            ColumnLayout {
                Layout.fillWidth: true
                Layout.leftMargin: Theme.spaceXl
                Layout.rightMargin: Theme.spaceXl
                spacing: Theme.spaceMd

                SectionLabel { text: "CARDS — TimeRangeCard, LogPanel" }
                RowLayout {
                    spacing: Theme.spaceLg
                    Layout.fillWidth: true

                    TimeRangeCard {
                        Layout.preferredWidth: 320
                        useCustomTime: true
                        fromDateTime: "2026-08-01 00:00"
                        toDateTime: "2026-08-22 00:00"
                    }

                    LogPanel {
                        Layout.preferredWidth: 460
                        Layout.preferredHeight: 220
                        title: "SYSTEM MONITOR"
                        logModel: ListModel {
                            ListElement { timestamp: "16:20:41"; message: "Backtest chart host initialized"; level: "info"; icon: "info" }
                            ListElement { timestamp: "16:20:44"; message: "10098 klines loaded for ETHUSDT"; level: "success"; icon: "check" }
                            ListElement { timestamp: "16:21:02"; message: "Gap detected: missing candles since 17:58 UTC"; level: "error"; icon: "alert-triangle" }
                        }
                    }
                }
            }

            // ---- Data table --------------------------------------------
            ColumnLayout {
                Layout.fillWidth: true
                Layout.leftMargin: Theme.spaceXl
                Layout.rightMargin: Theme.spaceXl
                Layout.bottomMargin: Theme.spaceXl
                spacing: Theme.spaceMd

                SectionLabel { text: "DATA TABLE — AppDataTable (schema-driven, header/row share one column definition)" }
                AppDataTable {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 180
                    columns: root.tradeColumns
                    model: root.sampleTrades
                }
            }

            // ---- Modal caption (the modal itself is a sibling below —
            // a Popup does not participate in inline layout, same
            // precedent as DateTimePicker.qml's calendarPopup) -----------
            ColumnLayout {
                Layout.fillWidth: true
                Layout.leftMargin: Theme.spaceXl
                Layout.rightMargin: Theme.spaceXl
                Layout.bottomMargin: Theme.spaceXl
                spacing: Theme.spaceXs

                SectionLabel { text: "MODAL — AppModal (Popup shell, dynamic sizing, centers on Overlay.overlay)" }
                Caption { text: "Opened automatically below for this screenshot — real usage opens on demand." }
            }

            // ---- Compact mode ------------------------------------------
            ColumnLayout {
                Layout.fillWidth: true
                Layout.leftMargin: Theme.spaceXl
                Layout.rightMargin: Theme.spaceXl
                Layout.bottomMargin: Theme.spaceXl
                spacing: Theme.spaceMd

                SectionLabel { text: "COMPACT MODE — every BaseCard descendant, same three properties" }
                Caption { text: "Icon when set; first letter of title as fallback; \"?\" when a card has neither." }

                RowLayout {
                    spacing: Theme.spaceLg

                    // Same components as the full-size sections above — only
                    // `compact: true` differs. Sized by this container, not
                    // by the cards themselves (they only expose compactSize
                    // as an intent).
                    //: LogPanel is deliberately absent from this row. Its
                    //: ListView delegate evaluates regardless of the
                    //: container's `visible`, and reading `model.timestamp`
                    //: throws "Value is null and could not be converted to
                    //: an object" for a second LogPanel instance — with an
                    //: unset model, an empty `ListModel {}`, *and* a
                    //: populated one. Isolated by bisecting this exact item
                    //: out of the gallery; invisible in a snapshot and
                    //: caught only by test_gallery_emits_no_qml_runtime_warnings
                    //: (which spins a real event loop — `app.processEvents()`
                    //: alone does not reach it).
                    //:
                    //: This is a genuine LogPanel robustness gap, not a
                    //: compact-mode one: its delegate assumes a live model
                    //: with rows. Recorded as follow-up rather than patched
                    //: here — fixing it means changing LogPanel's delegate
                    //: contract, which is out of scope for adding compact
                    //: mode and deserves its own change.
                    TimeRangeCard {
                        compact: true
                        Layout.preferredWidth: compactSize
                        Layout.preferredHeight: compactSize
                    }
                    // No icon set -> falls back to first letter of title.
                    AppDataTable {
                        compact: true
                        icon: ""
                        title: "Positions"
                        Layout.preferredWidth: compactSize
                        Layout.preferredHeight: compactSize
                    }
                    // Neither icon nor title -> renders "?" rather than
                    // failing or rendering an empty badge.
                    AppDataTable {
                        compact: true
                        icon: ""
                        Layout.preferredWidth: compactSize
                        Layout.preferredHeight: compactSize
                    }
                }
            }
        }
    }

    AppModal {
        id: demoModal
        title: "Confirm Backtest Run"
        actions: [
            StatefulButton { text: "Cancel"; onClicked: demoModal.close() },
            StatefulButton {
                text: "Run Backtest"
                accentBorder: Theme.success
                onClicked: demoModal.close()
            }
        ]

        Text {
            Layout.fillWidth: true
            text: "This will execute the strategy against 90 days of ETHUSDT 1m data. Continue?"
            color: Theme.textPrimary
            wrapMode: Text.WordWrap
            textFormat: Text.PlainText
        }
    }

    Component.onCompleted: demoModal.open()
}
