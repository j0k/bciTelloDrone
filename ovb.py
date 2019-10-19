import struct

class OpenVibeBuffer:
    def __init__(self, title = []):
        self.head = b''
        self.nChannels = -1
        self.count = 0
        self.rawData = b''
        self.headRecieved = False
        self.title = title
        self.lastSeries = []

    def analyze(self, msg):
        # if len(self.head)>10:
        #     print(len(msg), msg, self.head, self.head[10:12])
        self.rawData += msg
        afterHead = 0
        if self.count < 32:
            buff = min(32, len(msg))
            self.head = self.rawData[0: 32]

        self.count += len(msg)

        c = self.count - len(msg)

        if self.count >= 32 and not self.headRecieved:
            self.nChannels = self.head[12]
            self.headRecieved = True

            self.rawData = self.rawData[32:]

        if self.count >= 32:
            # rawData
            data = self.getPack(self.rawData)
            if len(data) > 0:
                series = []
                for eData in data:

                    hD = {}
                    if len(self.title) == len(eData):
                        for i,e in enumerate(eData):
                            hD[self.title[i]] = e
                    else:
                        for i,e in enumerate(eData):
                            if len(self.title) == len(eData):
                                hD[i] = e
                    series += [ hD ]

                self.lastSeries = series
                return series


    def getPack(self, msg):
        n = self.nChannels if self.nChannels > 0 else 1
        # print("getPack ({}): {}, {}, {}".format(self.count, n,len(self.rawData), len(msg)))


        ret = []

        while len(self.rawData) >= 8 * n:
            data = self.rawData[0:8*n]
            self.rawData = self.rawData[8*n:]

            ret += [struct.unpack('d' * n, data)]
        return ret
