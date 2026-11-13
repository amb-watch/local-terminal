import sys
import os

os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

from PyQt6.QtWidgets import QApplication, QSplashScreen, QLabel
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor
import styles
from display_picker import DisplayPickerDialog

LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "amb-logo.png")


def create_splash(screen):
    pixmap = QPixmap(760, 520)
    pixmap.fill(QColor("#0A0D12"))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    logo_pixmap = QPixmap(LOGO_PATH)
    if not logo_pixmap.isNull():
        logo_w = 420
        logo_h = int(logo_w * logo_pixmap.height() / logo_pixmap.width())
        scaled = logo_pixmap.scaled(
            logo_w, logo_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        logo_x = (pixmap.width() - scaled.width()) // 2
        logo_y = 90
        painter.drawPixmap(logo_x, logo_y, scaled)
        text_top = logo_y + scaled.height() + 30
    else:
        painter.setPen(QColor("#C76B52"))
        font = QFont(styles.UI_FONT_FAMILY, 30, QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.drawText(pixmap.rect().adjusted(0, 60, 0, 0), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, "AMB TERMINAL")
        text_top = 160

    painter.setPen(QColor("#F2B39A"))
    font_sub = QFont(styles.UI_FONT_FAMILY, 15, QFont.Weight.DemiBold)
    font_sub.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4)
    painter.setFont(font_sub)
    painter.drawText(
        pixmap.rect().adjusted(0, text_top, 0, 0),
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
        "TERMINAL",
    )

    painter.setPen(QColor("#8791A3"))
    font2 = QFont(styles.UI_FONT_FAMILY, 11)
    painter.setFont(font2)
    painter.drawText(
        pixmap.rect().adjusted(0, text_top + 40, 0, 0),
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
        "Learn to invest. Test your strategies.\nReal market data, powered by Yahoo Finance.\nLoading market data...",
    )

    painter.setPen(QColor("#C76B52"))
    painter.drawRect(0, 0, pixmap.width() - 1, pixmap.height() - 1)
    painter.drawRect(2, 2, pixmap.width() - 5, pixmap.height() - 5)
    painter.end()

    splash = QSplashScreen(screen, pixmap, Qt.WindowType.WindowStaysOnTopHint)
    geo = screen.geometry()
    splash.move(
        geo.x() + (geo.width() - pixmap.width()) // 2,
        geo.y() + (geo.height() - pixmap.height()) // 2,
    )
    splash.show()
    return splash


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AMB Terminal")
    app.setOrganizationName("AMB Financial")

    font = QFont(styles.UI_FONT_FAMILY, 11)
    app.setFont(font)
    app.setStyleSheet(styles.TERMINAL_STYLE)

    picker = DisplayPickerDialog()
    if picker.exec() != picker.DialogCode.Accepted or picker.selected_screen is None:
        sys.exit(0)
    target_screen = picker.selected_screen

    splash = create_splash(target_screen)
    app.processEvents()

    from main_window import AMBTerminal
    window = AMBTerminal(target_screen)

    def finish_splash():
        splash.finish(window)
        window.showFullScreen()

    QTimer.singleShot(2000, finish_splash)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
