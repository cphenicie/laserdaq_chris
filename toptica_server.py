from labrad import types as T, util
from labrad.server import LabradServer, setting
from twisted.internet.defer import inlineCallbacks, returnValue
import telnetlib
import time


class TopticaServer(LabradServer):
    name = 'TopticaCTL1500'  # This is how you will access this class from a labrad connection (with name.replace(" ", "_") and name.lower() )

    @inlineCallbacks
    def initServer(self):
        self.tn = telnetlib.Telnet("10.0.0.2", 1998)
        self.unitDict = {"wavelength-set": "nm",
                    "wavelength-act": "nm",
                    "wavelength-begin": "nm",
                    "wavelength-end": "nm",
                    "speed": "nm/s",
                    "progress": "",
                    "remaining-time": "s",
                    "input-channel": "",
                    "output-threshold": "nm"}
        self.valueDict = self.getCurrentSettings(self)
        yield None

    @setting(1,'echo',msg='?',returns='?')
    def echo(self,c,msg):
        print(msg)
        return msg

    @setting(2, 'getCurrentSettings', returns='?')
    def getCurrentSettings(self,c ):
        localValueDict = {}
        for item in self.unitDict:  # This iterates over the element, NOT the definition
            localValueDict[item] = self.getFloatSetting(self, item)
        return localValueDict

    @setting(3, 'setScan', initWave='v[nm]', waveTrigger='v[nm]', finalWave='v[nm]', speed='v[nm/s]', returns='?')
    def setScan(self, c, initWave, waveTrigger, finalWave, speed):
        time.sleep(.1)
        self.tn.write("(param-set! 'laser1:ctl:wavelength-set '" + str(initWave['nm']) + ") \r\n")
        self.tn.write("(param-set! 'laser1:ctl:scan:wavelength-begin '" + str(initWave['nm']) + ") \r\n")
        self.tn.write("(param-set! 'laser1:ctl:scan:wavelength-end '" + str(finalWave['nm']) + ")\r\n")
        self.tn.write("(param-set! 'laser1:ctl:scan:trigger:output-enabled '#t)\r\n")
        self.tn.write("(param-set! 'laser1:ctl:scan:trigger:output-threshold '" + str(waveTrigger['nm']) + ")\r\n")
        self.tn.write("(param-set! 'laser1:scan:enabled '#f)\r\n")
        self.tn.write("(param-set! 'laser1:ctl:scan:speed '" + str(speed['nm/s']) + ")\r\n")
        self.tn.write("(param-set! 'laser1:ctl:scan:microsteps '#t)\r\n")
        time.sleep(1)
        return None

    @setting(4, 'waitForSlew', returns='?')
    def waitForSlew(self, c):
        timeWait = 30  # The time we will wait for the laser to slew to the correct wavelength
        while timeWait > 0:
            waveAct = self.getFloatSetting(self, 'wavelength-act')
            waveSet = self.getFloatSetting(self, 'wavelength-set')
            if abs(waveAct['nm'] - waveSet['nm']) < 0.1:
                timeWait = 0
            else:
                timeWait = timeWait - 1
                time.sleep(1)
                if timeWait <= 0:
                    print("After 30 seconds we still aren't at the starting wavelength, something is amiss...")
        return None

    @setting(5, 'startScan')
    def startScan(self, c):
        waveBegin = self.getFloatSetting(self, 'wavelength-begin')
        self.tn.write("(param-set! 'laser1:ctl:wavelength-set '" + str(waveBegin['nm']) + ") \r\n")
        self.waitForSlew(self)  # Make sure we are at the starting wavelength before we begin the scan
        self.tn.write("(exec 'laser1:ctl:scan:start) \r\n")
        return None

    @setting(6, 'write', msg='s', returns='?')
    def write(self, c, msg):
        self.tn.write(msg)
        return None

    # @setting(1000, 'getCurrWave')
    # def getCurrWave(self, c):
    #     reList = ["wavelength-act = "]
    #     self.tn.write("(param-disp 'laser1:ctl:wavelength-act) \r\n")
    #     time.sleep(0.3)
    #     self.tn.expect(reList, 15)  # Wait up to 1 second to receive a message containing a string in reList
    #     waveActStr = self.tn.read_very_eager()  # The beginning of the buffer is now the wavelength
    #     print("here")
    #     print(waveActStr)
    #     waveActFloat = float(waveActStr[0:7])
    #     waveAct = T.Value(waveActFloat, 'nm')
    #     return waveAct

    @setting(1000, 'getFloatSetting', setting='s')
    def getFloatSetting(self, c, setting):
        self.tn.read_very_eager()  # Clear the buffer
        reListBefore = [setting + " = "]  # A list of regular expressions. In our case, this is trivially a list with 1 string
        self.tn.write("(param-disp 'laser1:ctl) \r\n")
        time.sleep(0.3)  # Wait for the laser to be able to respond (otherwise we just see an emtpy string)
        self.tn.expect(reListBefore, 1)  # Wait up to 1 second to receive a message containing a string in reList. Stop reading once you hit it
        reListAfter = ['\n']
        valStrArr = self.tn.expect(reListAfter, 1)
        valStr = valStrArr[2]
        # print(valStr)
        valFloat = float(valStr[0:-1])  # Last two characters are "\r\n". But, for some reason, int values need to go back 3 characters
        val = T.Value(valFloat, self.unitDict[setting])
        return val

    @setting(1001, 'setFloatSetting', setting='s', value='?')
    def setFloatSetting(self, c, setting, value):
        if setting[0:10] == "wavelength":
            try:
                valnm = value['nm']
            except TypeError:
                valnm = 2.99792458*10**17 / value['Hz']

            self.tn.write("(param-set! 'laser1:ctl:" + setting + " '" + str(valnm) + ") \r\n")
        ## Insert code for other types of parameters

        return None




__server__ = TopticaServer()

if __name__ == '__main__':
    util.runServer(__server__)