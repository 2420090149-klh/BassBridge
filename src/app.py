"""Application entry point for BassBridge."""

import sys
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from .ui.main_window import MainWindow


def main() -> int:
    """Run the BassBridge desktop application."""
    # Ensure Windows High-DPI scaling is enabled
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("BassBridge")
    app.setOrganizationName("BassBridgeAudio")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
