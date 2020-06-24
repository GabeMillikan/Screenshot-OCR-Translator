import OCR
import threading
import multiprocessing
import screenshot
import cv2
import os
import translate

'''
    Gui imports
'''
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

'''
    Utils
'''
def rgb2hex(r, g, b):
    r = hex(int(r))[2:].upper()
    g = hex(int(g))[2:].upper()
    b = hex(int(b))[2:].upper()
    if len(r) < 2: r = "0" + r;
    if len(g) < 2: g = "0" + g;
    if len(b) < 2: b = "0" + b;
    return "#"+r+g+b

'''
    App
'''

css_ocrWindow = '''
QMainWindow{
    background-color: rgb(30, 30, 30);
};
'''
class OCRWindow(QMainWindow):
    dying = False
    image = None
    language = 'eng'
    active = False
    activeChanged = lambda a: 0
    ocrThreads = []
    isTranslating = False
    translation = {"text": "", "src": "en", "dest": "ru", "result": "", "translating": False, "translated": False, "updated": False}
    
    def __init__(self, *args, **kwargs):
        super(OCRWindow, self).__init__(*args, **kwargs)
        self.setWindowTitle("OCR Result")
        self.setStyleSheet(css_ocrWindow)
        
        self.periodicTimer = QTimer(self)
        self.periodicTimer.setInterval(100)
        self.periodicTimer.timeout.connect(self.periodic)
        self.periodicTimer.start()
        
        self.sourceText = QPlainTextEdit(self, objectName = "souceText")
        self.sourceText.setFont(QFont("Consolas", 14, 10, False))
        self.sourceText.setStyleSheet("background-color: rgb(70, 70, 70); color: white; height: 100%;")
        self.sourceText.setPlaceholderText("Scanning Image...")
        self.sourceText.textChanged.connect(self.sourceTextChanged)
        
        self.translatedText = QPlainTextEdit(self, objectName = "destinationText")
        self.translatedText.setFont(QFont("Consolas", 14, 10, False))
        self.translatedText.setStyleSheet("background-color: rgb(70, 70, 70); color: white; height: 100%;")
        self.translatedText.setPlaceholderText("Translating...")
        
        self.translateCheckbox = QCheckBox('', self)
        self.translateCheckbox.setFixedSize(50, 40)
        self.translateCheckbox.move(10, 5)
        self.translateCheckbox.stateChanged.connect(self.translateStateChange)
        self.translateCheckbox.setCheckState(0)
        self.translateCheckbox.setStyleSheet("QCheckBox::indicator { width: 20; height: 20;}")
        
        self.sourceLanguageLabel = QLabel('Source Language', self)
        self.sourceLanguageLabel.setFont(QFont("Consolas", 14, 10, False))
        self.sourceLanguageLabel.setStyleSheet('color: white;');
        self.sourceLanguageLabel.setAlignment(Qt.AlignCenter)
        self.sourceLanguageLabel.setFixedSize(100, 30)
        self.sourceLanguageLabel.move(0, 50)
        
        self.destLanguageLabel = QLabel('Destination Language', self)
        self.destLanguageLabel.setFont(QFont("Consolas", 14, 10, False))
        self.destLanguageLabel.setStyleSheet('color: white;');
        self.destLanguageLabel.setAlignment(Qt.AlignCenter)
        self.destLanguageLabel.setFixedSize(100, 30)
        self.destLanguageLabel.move(120, 50)
        
        self.translateLabel = QLabel('Translate from', self)
        self.translateLabel.setFont(QFont("Consolas", 14, 10, False))
        self.translateLabel.setStyleSheet('color: white;');
        self.translateLabel.setFixedSize(140, 40)
        self.translateLabel.move(40, 5)
        
        self.translateToLabel = QLabel('to', self)
        self.translateToLabel.setFont(QFont("Consolas", 14, 10, False))
        self.translateToLabel.setStyleSheet('color: white;');
        self.translateToLabel.setFixedSize(30, 40)
        self.translateToLabel.move(300, 5)
        
        self.sourceLanguageDropdown = QComboBox(self)
        self.sourceLanguageDropdown.addItem("Detect Language")
        for (code, language) in translate.languages.items():
            self.sourceLanguageDropdown.addItem(language)
        self.sourceLanguageDropdown.setFixedSize(100, 30)
        self.sourceLanguageDropdown.move(190, 10)
        self.sourceLanguageDropdown.currentIndexChanged.connect(self.translateLanguageChanged)
        
        self.destinationLanguageDropdown = QComboBox(self)
        for (code, language) in translate.languages.items():
            self.destinationLanguageDropdown.addItem(language)
        self.destinationLanguageDropdown.setFixedSize(100, 30)
        self.destinationLanguageDropdown.move(330, 10)
        self.destinationLanguageDropdown.currentIndexChanged.connect(self.translateLanguageChanged)
        
        self.sizeUI()
    
    def translateLanguageChanged(self, new):
        self.newTranslation()
    
    def translateStateChange(self, state):
        state = int(state) > 0
        self.isTranslating = state
        self.newTranslation()
        self.sizeUI()
    
    def sizeUI(self):
        if self.isTranslating:
            self.setMinimumSize(600, 300)
            
            self.sourceText.setFixedSize(int(self.width()/2 - 10), self.height() - 80)
            self.sourceText.move(0, 80)
            
            self.translatedText.setFixedSize(int(self.width()/2 - 10), self.height() - 80)
            self.translatedText.move(int(self.width()/2 + 10), 80)
            
            self.sourceLanguageLabel.setFixedSize(int(self.width()/2 - 10), 40)
            
            self.destLanguageLabel.setFixedSize(int(self.width()/2 - 10), 40)
            self.destLanguageLabel.move(int(self.width()/2 + 10), 50)
            
            self.translatedText.show()
            self.sourceLanguageLabel.show()
            self.destLanguageLabel.show()
        else:
            self.setMinimumSize(440, 300)
            
            self.sourceText.setFixedSize(self.width(), self.height() - 50)
            self.sourceText.move(0, 50)
            
            self.translatedText.hide()
            self.sourceLanguageLabel.hide()
            self.destLanguageLabel.hide()
    
    def newTranslation(self):
        srcLangIndex = self.sourceLanguageDropdown.currentIndex()
        destLangIndex = self.destinationLanguageDropdown.currentIndex()
        srcText = self.sourceText.toPlainText()
        
        codelangs = [x for x in translate.languages.items()]
        
        src = None
        if srcLangIndex == 0:
            src = None # detect
        else:
            (code, lang) = codelangs[(srcLangIndex-1) % len(translate.languages)]
            src = code
        
        dest = None # English
        (code, lang) = codelangs[(destLangIndex) % len(translate.languages)]
        dest = code
        
        self.translation = {
            "src": src,
            "dest": dest,
            "text": srcText,
            "result": "",
            "translating": False,
            "translated": False,
            "updated": False,
        }
    
    def resizeEvent(self, event):
        self.sizeUI()
    
    def begin(self, img, language):
        self.image = img
        self.language = language
        self.sourceText.setPlaceholderText("Scanning image...")
        self.translatedText.setPlaceholderText("Translating...")
        self.activate()
        
        ID = len(self.ocrThreads)
        ocrThread = threading.Thread(target = self.ocr, args = [ID])
        self.ocrThreads.append({"thread": ocrThread, "status": "waiting", "error": None, "result": "Loading...", "handled": False}) # will have index = ID
        self.ocrThreads[ID]['thread'].start()
    
    def sourceTextChanged(self):
        self.newTranslation()
    
    def ocr(self, id):
        self.ocrThreads[id]['status'] = 'converting image'
        img = cv2.cvtColor(self.image, cv2.COLOR_RGB2BGR)
        self.ocrThreads[id]['status'] = 'waiting for tesseract'
        
        txt = None
        try:
            # 5 minute timeout
            # I can't imagine a scenario that you would need more time
            txt = OCR.getText(self.image, timeout = 300, language = self.language)
        except BaseException as e:
            self.ocrThreads[id]['error'] = e
            self.ocrThreads[id]['result'] = "[OCR ERROR]: %s" % str(e)
            self.ocrThreads[id]['status'] = 'complete'
            return
        
        self.ocrThreads[id]['result'] = txt
        self.ocrThreads[id]['status'] = 'complete'
    
    def periodic(self):
        id = len(self.ocrThreads) - 1
        if id < 0:
            return
        output = self.ocrThreads[id]
        if (not output['handled']):
            self.ocrThreads[id]['handled'] = self.updateOCRResult()
        
        if self.isTranslating and self.active:
            if self.translation['translated'] and not self.translation['updated']:
                self.translatedText.setPlainText(self.translation['result']) 
                self.translatedText.setPlaceholderText("No translation avaliable")
                
                srclang = "unknown (%s)" % str(self.translation['src'])
                destlang = "unknown (%s)" % str(self.translation['dest'])
                if self.translation['src'] in translate.languages:
                    srclang = translate.languages[self.translation['src']]
                if self.translation['dest'] in translate.languages:
                    destlang = translate.languages[self.translation['dest']]
                
                self.sourceLanguageLabel.setText(srclang)
                self.destLanguageLabel.setText(destlang)
                
                self.translation['updated'] = True
            elif not self.translation['translated'] and not self.translation['translating']:
                srclang = "Detecting..."
                destlang = "unknown (%s)" % str(self.translation['dest'])
                if self.translation['src'] in translate.languages:
                    srclang = translate.languages[self.translation['src']]
                if self.translation['dest'] in translate.languages:
                    destlang = translate.languages[self.translation['dest']]
                self.sourceLanguageLabel.setText(srclang)
                self.destLanguageLabel.setText(destlang)
                threading.Thread(target = self.preformTranslation).start()
            
    
    def preformTranslation(self):
        self.translation['translating'] = True
        
        ogText = self.translation['text']
        ogSrc = self.translation['src']
        ogDest = self.translation['dest']
        kwargs = {k:v for k,v in {"src":ogSrc, "dest":ogDest}.items() if v is not None}
        
        if ogText == "":
            self.translation['result'] = ""
            self.translation['translated'] = True
            return
        
        if (ogSrc == ogDest) and (ogDest is not None):
            self.translation['result'] = ogText
            self.translation['translated'] = True
            return
        
        
        res = translate.translate(ogText, **kwargs)
        
        # if translation unchanged
        if self.translation['text'] == ogText and self.translation['src'] == ogSrc and self.translation['dest'] == ogDest:
            self.translation['result'] = res.text
            self.translation['src'] = res.src
            self.translation['dest'] = res.dest
            self.translation['translated'] = True
    
    # Hello World
    
    def updateOCRResult(self):
        output = self.ocrThreads[-1]
        if output['status'] == 'complete':
            if output['error'] is not None:
                self.ocrError(output['error'])
            elif output['result'] is None:
                self.ocrError("Tesseract failed to find text, returned `None`")
            else:
                self.ocrComplete(output['result'])
            return True
        return False
    
    def ocrComplete(self, txt):
        self.sourceText.setPlainText(txt)
        self.sourceText.setPlaceholderText("Nothing found")
        self.translation['text'] = txt
    
    def ocrError(self, e):
        print("[ERROR]: \n%s" % str(e))
    
    def activate(self):
        self.show()
        self.active = True
        self.activeChanged(True)
    
    def deactivate(self):
        self.hide()
        self.active = False
        self.activeChanged(False)
    
    def setActiveChangedCallback(self, callback):
        self.activeChanged = callback
    
    def die(self):
        self.dying = True
        self.close()
        
    def closeEvent(self, event):
        if self.dying:
            event.accept()
        else:
            event.ignore()
            self.deactivate()

css_mainWindow = '''
QMainWindow{
    background-color: rgb(30, 30, 30);
}

QPushButton{
    background-color: rgb(70,70,70);
    color: white;
    border-radius: 5px;
}

QPushButton#newScreenshot{
    background-color: rgb(100, 200, 100);
}
QPushButton#newScreenshot:hover{
    background-color: rgb(75, 150, 75);
}
QPushButton#openImage{
    background-color: rgb(75, 100, 250);
}
QPushButton#openImage:hover{
    background-color: rgb(50, 75, 188);
}


QComboBox{
    border-radius: 3px;
}

'''
class MainWindow(QMainWindow):
    image = None
    image_src = None
    processedOCR = False
    enableAutoOCR = False

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self.ocrWindow = OCRWindow()
        self.ocrWindow.setActiveChangedCallback(self.ocrWindowActivityChange)
        
        self.setWindowTitle("Gabe's Tesseract GUI")
        self.setStyleSheet(css_mainWindow)
        
        self.sctobj = screenshot.ScreenshotWindow()
        self.sctobj.set_finish_callback(self.screenshotFinished)
        self.sctobj.hide()
        
        self.newScreenshotButton = QPushButton('NEW', self, objectName = "newScreenshot")
        self.newScreenshotButton.setToolTip('Take a screenshot for analysis')
        self.newScreenshotButton.setFont(QFont("Consolas", 25, 10, False))
        self.newScreenshotButton.setFixedSize(90, 40)
        self.newScreenshotButton.move(5, 5)
        self.newScreenshotButton.clicked.connect(self.beginScreenshot)
        
        self.openImageButton = QPushButton('OPEN', self, objectName = "openImage")
        self.openImageButton.setToolTip('Open an image for analysis')
        self.openImageButton.setFont(QFont("Consolas", 25, 10, False))
        self.openImageButton.setFixedSize(90, 40)
        self.openImageButton.move(100, 5)
        self.openImageButton.clicked.connect(self.openImage)
        
        self.startOCRButton = QPushButton('SCAN', self, objectName = "startOCR")
        self.startOCRButton.setToolTip('Preform OCR in the selected language')
        self.startOCRButton.setFont(QFont("Consolas", 25, 10, False))
        self.startOCRButton.setFixedSize(90, 40)
        self.startOCRButton.move(195, 5)
        self.startOCRButton.clicked.connect(self.pressedStartOCR)
        self.setOCRButtonAvaliable(True)
        
        # Avaliable languages for OCR, put english at top of list
        ocrlangs = OCR.getLanguages()
        self.sourceLanguageDropdown = QComboBox(self)
        codes = [cl[0] for cl in ocrlangs]
        if "eng" in codes:
            self.sourceLanguageDropdown.addItem("English")
        for (code, lang) in ocrlangs:
            if code != "eng":
                self.sourceLanguageDropdown.addItem(lang)
        self.sourceLanguageDropdown.setFixedSize(90, 20)
        self.sourceLanguageDropdown.move(290, 25)
        
        self.autoOCRCheckbox = QCheckBox('Auto Scan', self)
        self.autoOCRCheckbox.setFixedSize(90, 20)
        self.autoOCRCheckbox.move(290, 5)
        self.autoOCRCheckbox.stateChanged.connect(self.setAutoOCR)
        self.autoOCRCheckbox.setCheckState(2) # by default
        self.autoOCRCheckbox.setStyleSheet("QCheckBox{color: white} QCheckBox::indicator {width: 15; height: 15;}")
        
        self.imagePreviewFrame = QLabel(self, objectName = "imagePreview")
        self.imagePreviewFrame.setFixedSize(10, 10) # to be set once image exists
        self.imagePreviewFrame.move(5, 50)
        
        self.paintUI()
        self.show()
    
    def ocrWindowActivityChange(self, isActive):
        if not isActive:
            # closed output, disable auto ocr
            self.autoOCRCheckbox.setCheckState(0)
            self.processedOCR = False
            self.setOCRButtonAvaliable(True)
    
    def pressedStartOCR(self):
        if not self.processedOCR:
            if self.enableAutoOCR:
                self.autoOCR()
            else:
                self.startOCR()
    
    def setAutoOCR(self, state):
        self.enableAutoOCR = int(state) > 0
        self.autoOCR()
    
    def beginScreenshot(self):
        self.sctobj.start()
        self.hide()
    
    def screenshotFinished(self, img, dimensions):
        self.show()
        self.newImage(img)
    
    def openImage(self):
        (fname, x) = QFileDialog.getOpenFileName(self, "Open file", os.getcwd(), "Image files (*.png *.jpg *.jpeg *.jpe *jp2 *.bmp *.tiff *.tif *.sr *.ras *.pbm *.pgm *.ppm)")
        if x == '':
            # they canceled
            return
        else:
            try:
                img = cv2.imread(fname)
                self.newImage(img)
            except:
                self.imreadFail()
    
    def imreadFail(self):
        print("imread failed")
    
    def newImage(self, image):
        self.processedOCR = False
        if not self.enableAutoOCR:
            self.setOCRButtonAvaliable(True)
        
        self.image_src = image
        self.image_src = cv2.cvtColor(self.image_src, cv2.COLOR_BGR2RGB)
        h, w, ch = self.image_src.shape
        bytesPerLine = ch * w
        self.image = QImage(self.image_src.data.tobytes(), w, h, bytesPerLine, QImage.Format_RGB888)
        
        self.paintUI()
        self.autoOCR()
        
    def autoOCR(self):
        if self.enableAutoOCR and not self.processedOCR:
                self.processedOCR = True
                self.startOCR()
    
    def setOCRButtonAvaliable(self, avaliable):
        if avaliable:
            self.startOCRButton.setStyleSheet('''
                QPushButton#startOCR{
                    background-color: rgb(200, 50, 200);
                }
                QPushButton#startOCR:hover{
                    background-color: rgb(150, 37, 150);
                }
            ''')
        else:
            self.startOCRButton.setStyleSheet('''
                QPushButton#startOCR{
                    background-color: rgb(100, 100, 100);
                }
                QPushButton#startOCR:hover{
                    background-color: rgb(100, 100, 100);
                }
            ''')
    
    def startOCR(self):
        self.processedOCR = True
        self.setOCRButtonAvaliable(False)
        if self.image_src is not None:
            self.ocrWindow.begin(self.image_src, 'eng')
    
    def paintUI(self):
        if self.image is None:
            self.paintNoImage()
        else:
            self.paintWithImage()
            
    def paintNoImage(self):
        self.setFixedSize(195, 50)
    
    def paintWithImage(self):
        self.imagePreviewFrame.setPixmap(QPixmap.fromImage(self.image))
        self.imagePreviewFrame.setFixedSize(self.image_src.shape[1], self.image_src.shape[0])
        minWidth = 385
        imgWidth = self.image_src.shape[1] + 10 # + padding
        finalWidth = max(minWidth, imgWidth)
        finalHeight = self.image_src.shape[0] + 55
        self.setFixedSize(finalWidth, finalHeight)
    
    def closeEvent(self, event):
        self.ocrWindow.die()
        

app = QApplication([])
app.setStyle("fusion")

window = MainWindow()

app.exec_()