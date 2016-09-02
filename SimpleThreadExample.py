import time
import numpy as np
import PyDAQmx as pydaqmx
import ctypes
from PyQt4.QtCore import QThread, SIGNAL
from PyQt4 import QtCore, QtGui, uic
import sys
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

class thread_generatedata(QThread):
    def __init__(self, parentObj):
        QThread.__init__(self)
        self.parentObj = parentObj

    def run(self):
        # do data processing, acquisition etc here.
        print('take 5 seconds to take data')
        self.parentObj.sayHi()
        time.sleep(5)
        data = np.random.rand(5)

        self.emit(SIGNAL('plot_data(PyQt_PyObject)'), data)

qtCreatorFile = "ScanUI.ui"  # Enter file here.
Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)

class MyApp(QtGui.QMainWindow, Ui_MainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)

        self.startScanButton.clicked.connect(self.startScan)
        self.figHand1 = Figure()
        self.axHand1 = self.figHand1.add_subplot(111)
        self.canvas1 = FigureCanvasQTAgg(self.figHand1)
        self.canvas1.setParent(self.graphHolder1)
        self.figHand1.subplots_adjust(bottom=0.7, top=0.95, right=0.69,
                                      left=0.15)  # Otherwise the axes seem to get cut off

    def startScan(self):
        # should initiate thread, and grab the data
        self.thdgendat = thread_generatedata(self)
        self.connect(self.thdgendat, SIGNAL('plot_data(PyQt_PyObject)'), self.plot_data)
        self.connect(self.thdgendat, SIGNAL('finished()'), self.stopScan)
        self.thdgendat.start()

    def stopScan(self):
        print('done')

    def plot_data(self, data):
        print('into plot')
        self.axHand1.plot(data)
        self.canvas1.draw()

    def sayHi(self):
        print("hello")

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = MyApp()
    window.show()
    sys.exit(app.exec_())