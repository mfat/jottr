import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

ToolBar {
    RowLayout {
        anchors.fill: parent
        ToolButton {
            text: "New"
            onClicked: mainWindow.new_editor_tab()
        }
        ToolButton {
            text: "Open"
            onClicked: mainWindow.open_file_dialog()
        }
        ToolButton {
            text: "Save"
            onClicked: mainWindow.save_file()
        }
        ToolSeparator {}
        ToolButton {
            text: "RSS"
            onClicked: mainWindow.new_rss_tab()
        }
        ToolButton {
            text: "Settings"
            onClicked: mainWindow.show_settings()
        }
        ToolSeparator {}
        ToolButton {
            text: "Light"
            onClicked: mainWindow.set_theme("light")
        }
        ToolButton {
            text: "Dark"
            onClicked: mainWindow.set_theme("dark")
        }
    }
}
