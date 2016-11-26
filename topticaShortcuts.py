# A collection of functions to communicate with the Toptica laser. This is accomplished through a telnet connection, for
# instance, through an ethernet cable between the DAQ computer and the laser

######## Contents ########

### Functions ###
# setScan: Given a telnet connection to the laser, set up a scan that runs between two wavelengths at a specified speed
# waitForSlew: function runs until the laser is at a specified wavelength, then it returns nothing
# saveData: Save the data from a scan


import telnetlib
import time
import threading

def setScan(telnet, initWave, waveOffset, finalWave, speed):
    time.sleep(.1)
    telnet.write("(param-set! 'laser1:ctl:wavelength-set '" + str(initWave-waveOffset) + ") \r\n")
    telnet.write("(param-set! 'laser1:ctl:scan:wavelength-begin '" + str(initWave-waveOffset) + ") \r\n")
    telnet.write("(param-set! 'laser1:ctl:scan:wavelength-end '" + str(finalWave) + ")\r\n")
    telnet.write("(param-set! 'laser1:ctl:scan:trigger:output-enabled '#t)\r\n")
    telnet.write("(param-set! 'laser1:ctl:scan:trigger:output-threshold '" + str(initWave) + ")\r\n")
    telnet.write("(param-set! 'laser1:scan:enabled '#f)\r\n")
    telnet.write("(param-set! 'laser1:ctl:scan:speed '" + str(speed) + ")\r\n")
    telnet.write("(param-set! 'laser1:ctl:scan:microsteps '#t)\r\n")
    time.sleep(1)


def waitForSlew(telnet, wavelength):
    print("Wait for laser to reach set wavelength")
    telnet.read_very_eager()  # Clear out the buffer
    reList = ["wavelength-act = "]  # The expression we will look for in the output of the laser, we will end up basically deleting all the text up to and including this
    timeWait = 30  # The time we will wait for the laser to slew to the correct wavelength
    while timeWait > 0:
        telnet.write("(param-disp 'laser1:ctl:wavelength-act) \r\n")
        time.sleep(.03)
        telnet.expect(reList, 1)  # Wait up to 1 second to receive a message containing a string in reList
        waveActStr = telnet.read_very_eager()  # The beginning of the buffer is now the wavelength
        if waveActStr == '':
            waveAct = 0  # Arbitrary choice, anything would work as long as it's guaranteed not to be within 0.1nm of the set starting point
        else:
            waveAct = float(waveActStr[0:6])  # Just take up to the first decimal

        if abs(waveAct - wavelength) < 0.1:
            timeWait = 0
        else:
            # print("Difference = " + str(waveAct - self.startWave - waveOffset) + " , timeWait = " + str(timeWait) )
            timeWait = timeWait - 1
            time.sleep(1)
            if timeWait <= 0:
                print(
                "After 30 seconds we still aren't at the starting wavelength, code will now crash. Have a nice day!")
    return

def thread_waitForSlew(telnet, wavelength):
    t = threading.Thread(target=waitForSlew, args=(telnet, wavelength))
    t.start()
    while t.isAlive():
        pass  # Do nothing, this will just pause the code until the thread is done


# Unfortunately, the voltage steps taken by the USB6002 are noticably larger than the ones taken by the Toptica native
# signal generator, so we will run the piezo scan by generating the signal from the toptica, and then feeding it back
# into itself. Then, we can just measure the piezo voltage and the PD voltage on separate channels, in this case we have
# set up the system to take the signal out of the Toptica through Out A, and plugged this into a BNC tee with 2 other
# BNCs, one going to Fast in 3 and one going to the USB6002 ai3.
#
# (This isn't much more silly than generating the signal by the USB6002 since there's also no way to synchronize the
# input and the output from the USB6002, we'd still need to have a tee to measure the output, anyway)


#  Class that has all the functionality of the TOPAS DLC pro program
#  NOTE! This is incomplete, I've only implemented the features that I needed to do a piezo scan...
class TopticaDLCPro():
    def __init__(self):
        self.tn = telnetlib.Telnet("10.0.0.2", 1998)
        self.tnWaitTime = 0.1 # How long to wait (in seconds) between reading-to and writing-from the topica over the telnet
        time.sleep(self.tnWaitTime)
        # This is not a comprehensive list, just add them as you need them (there are too many we'd never use)
        self.paramList = ['laser1:emission',
                     'laser1:dl:pc:enabled',
                     'laser1:dl:pc:voltage-set',
                     'laser1:dl:pc:voltage-act',
                     'laser1:dl:pc:voltage-min',
                     'laser1:dl:pc:voltage-max',
                     'laser1:dl:pc:external-input:signal',
                     'laser1:dl:pc:external-input:factor',
                     'laser1:dl:pc:external-input:enabled',
                     'laser1:scan:enabled',
                     'laser1:scan:frequency',
                     'laser1:scan:output-channel',
                     'laser1:scan:unit',
                     'laser1:scan:amplitude',
                     'laser1:scan:offset'
                     ]
        self.paramVals = {}
        self.initializeParameters()


    def initializeParameters(self):
        # Read the current set value of these parameters parameters currently set on the Toptica
        print("Initializing toptica laser...")
        self.tn.read_very_eager() # Clear the buffer
        for param in self.paramList:
            self.tn.write("(param-ref '" + param + ") \r\n")
            time.sleep(self.tnWaitTime) # Give the Toptica time to respond
            paramString = self.tn.read_very_eager() # Apparently we need to save it as a variable before we use .split()
            self.paramVals[param] = paramString.split('\r\n')[1] # The synatx of the toptica is to surround the value with \r\n
            #print(paramString)
        print("done")

    def setParameter(self, param, value):
        self.tn.write("(param-set! '" + param + " '" + str(value) + ")") # The ' is only needed if the argument following it should be interpreted as a string, but it doesn't hurt to just always interpret the argument as a string for the Toptica

    def readParameter(self, param):
        self.tn.write("(param-ref '" + param + ") \r\n")
        time.sleep(self.tnWaitTime)
        paramString = self.tn.read_very_eager()  # Apparently we need to save it as a variable before we use .split()
        value = paramString.split('\r\n')[1]  # The synatx of the toptica is to surround the value with \r\n
        return value

    #  This is designed to just scan the piezo back and forth at its full range continually. This works by setting the
    #  piezo scan to come of pcVoltageOutChan and then get fed back in at pcVoltageInChan. This way, we can catch the
    #  signal in between these ports and measure it on the USB6002. This probably seems silly, but it's currently the
    #  best method we have since the USB6002 doesn't output analog voltages as smoothly as the toptica, and there's no
    #  way to sync the USB6002 ao with ai, anyway.
    def defaultPiezoScan(self):
        """ Place holder for when I figure out docstrings """

        #  From DLCpro-Command-Reference.pdf Appendix (pg 140)
        #  External signals (BNC connector)
        #  ID   Name
        #  0    Fast In 1
        #  1    Fast In 2
        #  2    Fast In 3
        #  4    Fast In 4
        #  20   Output A
        #  21   Output B

        # I've put these parameters here to make them more obvious so we're not reading the wrong channel
        pcVoltageOutChan = 2
        pcVoltageInChan = 20

        #  Parameters that set the voltages output by the Toptica function generator. Note that, if we're going to read
        #  this signal on the UBS6002, we should make sure the amplitude < 10V
        self.setParameter("laser1:scan:enabled", "#t")
        self.setParameter("laser1:scan:frequency", 30)
        self.setParameter("laser1:scan:output-channel", pcVoltageOutChan)
        self.setParameter("laser1:scan:unit", "V")
        #self.setParameter("laser1:scan:amplitude", 7.80776)
        self.setParameter("laser1:scan:amplitude", 7.0)
        # self.setParameter("laser1:scan:offset", 0.1)
        self.setParameter("laser1:scan:offset", 0.0)

        #  Parameters that define the piezo scan given an external voltage signal.
        self.setParameter("laser1:dl:pc:external-input:enabled", "#t")
        # self.setParameter("laser1:dl:pc:voltage-set", 65.0)
        self.setParameter("laser1:dl:pc:voltage-set", 70.0)
        self.setParameter("laser1:dl:pc:external-input:signal", pcVoltageInChan)  # Output the signal i
        self.setParameter("laser1:dl:pc:external-input:factor", 20)  # units of V/V