"""Command-line interface for post-genesis4."""

import sys
from PyQt5 import QtWidgets


def main():
    """Main entry point for the post-genesis4 application."""
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet("""
        QLabel { color: black; font-size: 20px; }
        QLineEdit { font-size: 20px; }
        QPushButton { font-size: 20px; }
        QComboBox { font-size: 20px;}
        QCheckBox { font-size: 20px; }
    """)

    from post_genesis4.gui.main_window import PostGenesis4MainWindow
    win = PostGenesis4MainWindow()
    win.show()

    sys.exit(app.exec())

show = main

if __name__ == '__main__':
    main()
