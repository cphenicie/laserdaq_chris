import sys
from PyQt4 import QtCore, QtGui, uic

qtCreatorFile = "practiceGUIio.ui"  # Enter file here.
Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)

class MyApp(QtGui.QMainWindow, Ui_MainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)

        self.boxText = self.textBox.toPlainText()
        self.number = self.spinBox.value()
        self.metadata.insertPlainText(self.boxText)
        self.metadata.insertPlainText('\n'+str(self.number))
        self.textBox.textChanged.connect(self.updateMetadata)
        self.spinBox.valueChanged.connect(self.updateMetadata)
        self.goButton.clicked.connect(self.initializeData)


    def updateMetadata(self):
        self.boxText = self.textBox.toPlainText()
        self.metadata.setPlainText(self.boxText)
        self.metadata.appendPlainText(str(self.spinBox.value()))

    def initializeData(self):
        metadataText = self.metadata.toPlainText()

        aiLines = list()
        aiNames = list()
        self.comboBox.clear()
        self.boxText = self.textBox.toPlainText()
        textLines = self.boxText.split('\n')
        for line in textLines:
            splitLine = line.split(':')
            if len(splitLine) == 2:  # In case there are trailing new lines
                aiLines.append(str.strip(str(splitLine[0])))  # str.strip() gets rid of any leading an trailing spaces
                aiNames.append(str.strip(str(splitLine[1])))
                self.comboBox.addItem(str.strip(str(splitLine[1])))

        aiNameDict = {}
        for line, name in zip(aiLines, aiNames):
            aiNameDict[line] = name
        print(aiNameDict)


    #     self.updateComboBox()
    #
    # def updateComboBox(self):
    #     self.comboBox.clear()
    #     self.boxText = self.textBox.toPlainText()
    #     textLines = self.boxText.split('\n')
    #     for line in textLines:
    #         splitLine = line.split(': ')
    #         if len(splitLine) == 2:  # In case there are trailing new lines
    #             self.comboBox.addItem(splitLine[1])



if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    window = MyApp()
    window.show()
    sys.exit(app.exec_())