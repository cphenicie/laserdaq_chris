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
    print("Wait for laser to reach initial wavelength")
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

def thread_waitForSlow(telnet, wavelength):
    t = threading.Thread(target=waitForSlew, args=(telnet, wavelength))
    t.start()
    while t.isAlive():
        pass  # Do nothing, this will just pause the code until the thread is done