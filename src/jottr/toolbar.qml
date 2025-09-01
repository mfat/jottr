import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

ToolBar {
    RowLayout {
        anchors.fill: parent
        ToolButton {
            icon.source: "icons/new.svg"
            display: ToolButton.IconOnly
            onClicked: mainWindow.new_editor_tab()
            ToolTip.visible: hovered
            ToolTip.text: "New"
        }
        ToolButton {
            icon.source: "icons/open.svg"
            display: ToolButton.IconOnly
            onClicked: mainWindow.open_file_dialog()
            ToolTip.visible: hovered
            ToolTip.text: "Open"
        }
        ToolButton {
            icon.source: "icons/save.svg"
            display: ToolButton.IconOnly
            onClicked: mainWindow.save_file()
            ToolTip.visible: hovered
            ToolTip.text: "Save"
        }
        ToolSeparator {}
        ToolButton {
            icon.source: "icons/globe.svg"
            display: ToolButton.IconOnly
            onClicked: mainWindow.new_rss_tab()
            ToolTip.visible: hovered
            ToolTip.text: "RSS"
        }
        ToolButton {
            icon.source: "icons/menu.svg"
            display: ToolButton.IconOnly
            onClicked: mainWindow.show_settings()
            ToolTip.visible: hovered
            ToolTip.text: "Settings"
        }
        ToolSeparator {}
        ToolButton {
            icon.source: "icons/theme.svg"
            display: ToolButton.IconOnly
            onClicked: mainWindow.set_theme("light")
            ToolTip.visible: hovered
            ToolTip.text: "Light Theme"
        }
        ToolButton {
            icon.source: "icons/color-mode-invert-text.svg"
            display: ToolButton.IconOnly
            onClicked: mainWindow.set_theme("dark")
            ToolTip.visible: hovered
            ToolTip.text: "Dark Theme"

        }
    }
}
