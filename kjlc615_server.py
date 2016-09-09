from labrad import types as T, util
from labrad.server import LabradServer, setting
from twisted.internet.defer import inlineCallbacks, returnValue
import serial

class KJLC615(LabradServer):
    name = 'kjlc615'  # This is how you will access this class from a labrad connection (with name.replace(" ", "_") and name.lower() )

    @inlineCallbacks
    def initServer(self):
        self.ser = serial.Serial('COM3', 9600, timeout=0, parity=serial.PARITY_NONE, rtscts=1)
        yield None


    @setting(1,'echo',msg='?',returns='?')
    def echo(self,c,msg):
        print(msg)
        return msg

    @setting(2, 'readPressure', returns='?')
    def readPressure(self, c):
        pressStr = self.ser.readline()
        return T.Value(float(pressStr[1:4]), 'torr')

__server__ = KJLC615()

if __name__ == '__main__':
    util.runServer(__server__)