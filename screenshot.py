import mss
import numpy as np
import cv2
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import ctypes
import sys
import time
import threading

# color & opacity (R, G, B, A) of the background and outline
BACKGROUND_COLOR = (255, 255, 255, 127)
OUTLINE_COLOR = (255, 0, 0, 255)
OUTLINE_THICKNESS = 1 # pixels

scap = mss.mss()
def grabRegion(region):
    return np.asarray(scap.grab(region))
    
def grabFrame(X, Y, W, H):
    return grabRegion({"left": X, "top": Y, "width": W, "height": H})

def getDesktopDimensions():
    # https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getsystemmetrics
    SM_XVIRTUALSCREEN = 76 # LEFTMOST POSITION (not always 0)
    SM_YVIRTUALSCREEN = 77 # TOPMOST POSITION  (not always 0)
    
    SM_CXVIRTUALSCREEN = 78 # WIDTH
    SM_CYVIRTUALSCREEN = 79 # HEIGHT
    
    
    # https://docs.microsoft.com/en-us/windows/win32/gdi/multiple-monitor-system-metrics
    return {
        "left": ctypes.windll.user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
        "top": ctypes.windll.user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
        "width": ctypes.windll.user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
        "height": ctypes.windll.user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    }

class ScreenshotWindow(QMainWindow):
    mpos = firstPosition = secondPosition = (0, 0)
    beganDragging = False
    imageRect = (-1, -1, 0, 0)
    complete = False
    running = False
    finish_callback = None
    
    def __init__(self, closeAfterFinish = False, *args, **kwargs):
        super(ScreenshotWindow, self).__init__(*args, **kwargs)
        
        self.dimensions = getDesktopDimensions()
        self.setFixedSize(self.dimensions['width'], self.dimensions['height'])
        self.move(self.dimensions['left'], self.dimensions['top'])

        self.setWindowTitle(" ")

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.setCursor(QCursor(Qt.CrossCursor))
        self.closeAfterFinish = closeAfterFinish
    
    def set_finish_callback(self, func):
        self.finish_callback = func
    
    def start(self):
        self.mpos = self.firstPosition = self.secondPosition = (0, 0)
        self.beganDragging = False
        self.imageRect = (-1, -1, 0, 0)
        self.complete = False
        self.running = True
        self.repaint()
        self.show()
    
    def getRect(self, a, b):
        xmin = 0
        xmax = 0
        ymin = 0
        ymax = 0
        if a[0] < b[0]:
            xmin = a[0]
            xmax = b[0]
        else:
            xmin = b[0]
            xmax = a[0]
        if a[1] < b[1]:
            ymin = a[1]
            ymax = b[1]
        else:
            ymin = b[1]
            ymax = a[1]
        return (xmin, ymin, xmax, ymax)
    
    def rectAbs2Rel(self, absrect):
        # (x1, y1, x2, y2) -> (x1, y1, width, height)
        rel = [absrect[0], absrect[1], absrect[2]-absrect[0], absrect[3]-absrect[1]]
        rel[2] = max(1, rel[2])
        rel[3] = max(1, rel[3])
        return tuple(rel)
    
    def moveEvent(self, event):
        if not self.running:
            self.hide()
            return
        # stop the window from moving
        self.move(self.dimensions['left'], self.dimensions['top'])
        super(ScreenshotWindow, self).moveEvent(event)
        
    def mouseMoveEvent(self, event):
        if not self.running:
            self.hide()
            return
        mpos = (event.x(), event.y())
        self.imageRect = self.rectAbs2Rel(self.getRect(self.firstPosition, mpos))
        super(ScreenshotWindow, self).mouseMoveEvent(event)
        self.repaint()
    
    def paintEvent(self, event):
        if not self.running:
            self.hide()
            return
        painter = QPainter(self)
        
        #background
        if self.beganDragging:
            # left
            painter.fillRect(QRect(0, 0, self.imageRect[0], self.dimensions['height']), QBrush(QColor(*BACKGROUND_COLOR)))
            # right
            painter.fillRect(QRect(self.imageRect[0]+self.imageRect[2], 0, self.dimensions['width'], self.dimensions['height']), QBrush(QColor(*BACKGROUND_COLOR)))
            # top middle
            painter.fillRect(QRect(self.imageRect[0], 0, self.imageRect[2], self.imageRect[1]), QBrush(QColor(*BACKGROUND_COLOR)))
            # bottom middle
            painter.fillRect(QRect(self.imageRect[0], self.imageRect[1] + self.imageRect[3], self.imageRect[2], self.dimensions['height'] - (self.imageRect[1] + self.imageRect[3])), QBrush(QColor(*BACKGROUND_COLOR)))
        else:
            painter.fillRect(QRect(0, 0, self.dimensions['width'], self.dimensions['height']), QBrush(QColor(*BACKGROUND_COLOR)))
            
        # outline
        painter.setPen(QPen(QColor(*OUTLINE_COLOR), OUTLINE_THICKNESS, Qt.SolidLine))
        painter.drawRect(*self.imageRect)
        
        self.setWindowState(Qt.WindowActive)
        self.activateWindow()
        self.raise_()
        self.show()
        
    def mousePressEvent(self, event):
        if not self.running:
            self.hide()
            return
        pos = (event.x(), event.y())
        
        self.firstPosition = pos
        self.beganDragging = True
        super(ScreenshotWindow, self).mouseReleaseEvent(event)
    
    def mouseReleaseEvent(self, event):
        self.hide()
        pos = (event.x(), event.y())
        
        self.secondPosition = pos
        self.final()
    
    def final(self):
        a, b = self.firstPosition, self.secondPosition
        absrect = self.getRect(a, b)
        relrect = self.rectAbs2Rel(absrect)
        self.imageRect = relrect
        self.complete = True
        self.running = False
        
        if self.finish_callback:
            img, dimensions = grabFrame(*self.imageRect), self.imageRect
            self.finish_callback(img, dimensions)
        
        if self.closeAfterFinish:
            self.close()

def promptScreenRegion():
    
    app = QApplication(sys.argv)
    window = ScreenshotWindow(closeAfterFinish = True)
    window.start()
    app.exec_()
    
    rect = window.imageRect
    return {"left": rect[0], "top": rect[1], "width": rect[2], "height": rect[3]}

def prompt():
    region = promptScreenRegion()
    return grabRegion(region), region

cv2WindowOffsets = (9, 32) # the offset to make a namedWindow position match up with top left of image 

def main():
    img, dimensions = prompt()
    dimensions = (dimensions['left'], dimensions['top'], dimensions['width'], dimensions['height'])
    cv2.namedWindow("sct")
    cv2.moveWindow("sct", dimensions[0]-cv2WindowOffsets[0], dimensions[1]-cv2WindowOffsets[1])
    cv2.imshow("sct", img)
    cv2.waitKey(0)

if __name__ == "__main__":
    while True:
        main()