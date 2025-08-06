from gerenciador_postgres.gui.main_window import MainWindow
from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QTimer
import sys


def main():
    app = QApplication(sys.argv)

    pixmap = QPixmap()
    splash = QSplashScreen(pixmap)
    splash.show()
    app.processEvents()

    window = MainWindow()
    window.show()

    QTimer.singleShot(1000, lambda: splash.finish(window))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
