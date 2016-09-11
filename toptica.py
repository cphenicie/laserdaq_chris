# Self contained class to interface with a Toptica laser.

import telnetlib
import time
import threading

class TopticaLaser:
    def __init__(self):
        self.tn = telnetlib.Telnet("10.0.0.2", 1998)
        self.getCurrentSettings()


    def getCurrentSettings(self):
        #self.waveAct = ...
        pass

    def setWavelength(self, wavelength):
        self.tn.write("(param-set! 'laser1:ctl:wavelength-set '" + str(wavelength) + ") \r\n")

    def setScan(self, initWave, waveOffset, finalWave, speed):
        time.sleep(.1)
        self.tn.write("(param-set! 'laser1:ctl:wavelength-set '" + str(initWave - waveOffset) + ") \r\n")
        self.tn.write("(param-set! 'laser1:ctl:scan:wavelength-begin '" + str(initWave - waveOffset) + ") \r\n")
        self.tn.write("(param-set! 'laser1:ctl:scan:wavelength-end '" + str(finalWave) + ")\r\n")
        self.tn.write("(param-set! 'laser1:ctl:scan:trigger:output-enabled '#t)\r\n")
        self.tn.write("(param-set! 'laser1:ctl:scan:trigger:output-threshold '" + str(initWave) + ")\r\n")
        self.tn.write("(param-set! 'laser1:scan:enabled '#f)\r\n")
        self.tn.write("(param-set! 'laser1:ctl:scan:speed '" + str(speed) + ")\r\n")
        self.tn.write("(param-set! 'laser1:ctl:scan:microsteps '#t)\r\n")
        time.sleep(1)
        return

    def startScan(self):
        #self.waitForSlew()  # Wait until we reach the starting wavelength of the scan
        self.tn.write("(exec 'laser1:ctl:scan:start) \r\n")


    def waitForSlew(self, wavelength):
        print("Wait for laser to reach initial wavelength")
        self.tn.read_very_eager()  # Clear out the buffer
        reList = ["wavelength-act = "]  # The expression we will look for in the output of the laser, we will end up basically deleting all the text up to and including this
        timeWait = 30  # The time we will wait for the laser to slew to the correct wavelength
        while timeWait > 0:
            self.tn.write("(param-disp 'laser1:ctl:wavelength-act) \r\n")
            time.sleep(.03)
            self.tn.expect(reList, 1)  # Wait up to 1 second to receive a message containing a string in reList
            waveActStr = self.tn.read_very_eager()  # The beginning of the buffer is now the wavelength
            if waveActStr == '':
                waveAct = 0  # Arbitrary choice, anything would work as long as it's guaranteed not to be within 0.1nm of the set starting point
            else:
                waveAct = float(waveActStr[0:6])  # Just take up to the first decimal

            if abs(waveAct - wavelength) < 0.1:
                timeWait = 0
            else:
                timeWait = timeWait - 1
                time.sleep(1)
                if timeWait <= 0:
                    print(
                        "After 30 seconds we still aren't at the starting wavelength, code will now crash. Have a nice day!")
        return

    def thread_waitForSlow(self, wavelength):
        t = threading.Thread(target=self.waitForSlew, args=(wavelength))
        t.start()
        while t.isAlive():
            pass  # Do nothing, this will just pause the code until the thread is done
        return

    class Scan():
        def __init__(self):
