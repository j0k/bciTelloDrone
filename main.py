
import time
import threading
from threading import Timer
from threading import Event, Thread

import socket
import sys
import struct
from djitellopy import Tello
import cv2


import signal
import sys
import os, signal, subprocess
import json

from ovb import OpenVibeBuffer

def signal_handler(signal, frame):
        global drone
        global sock
        drone.finish()
        sock.close()
        print('You pressed Ctrl+C!')
        os._exit(1)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

class RepeatedTimer:
    """Repeat `function` every `interval` seconds."""
    def __init__(self, interval, function, *args, **kwargs):
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.start = time.time()
        self.event = Event()
        self.thread = Thread(target=self._target)
        self.thread.start()

    def _target(self):
        while not self.event.wait(self._time):
            self.function(*self.args, **self.kwargs)

    @property
    def _time(self):
        return self.interval - ((time.time() - self.start) % self.interval)

    def stop(self):
        self.event.set()
        self.thread.join()


sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
port = 5679

config = json.loads(open(sys.argv[1], 'r').read())
print(config)
# sys.exit(0)

class Drone:
    def __init__(self, config, ovbuffer):
        self.config  = config
        self.every   = config["time"]["updateEverySec"]
        self.runTime = time.time()
        self.state_takeoff = False
        self.state_land    = False

        self.ovbuffer = ovbuffer
        self.simulate = config["simulate"]
        if not self.simulate:
            self.tello = Tello()
            self.tello.connect()

        self.height = 0
        self.cntrlChannel = config["cntrlChannel"]
        self.power2height = config["power2height"]
        self.minStep      = config["minimalStepCM"]
        self.speed        = config["speed"]
        # 20 mkV^2 = 30 cm above the ground.
        # 80 mkV^2 = 200 cm above the ground.


        self.timer = RepeatedTimer(self.every, self.scene)

    def time(self):
        return time.time() - self.runTime

    def start(self):
        config = self.config
        if self.time() > config["time"]["takeOff"] and not self.state_takeoff:
            self.logPos("takeoff")
            self.state_takeoff = True
            self.height = config["defaultHeightCM"]
            try:
                if not self.simulate:
                    self.tello.takeoff()
            except Exception as e:
                print(e)


    def finish(self, force = False):
        if self.state_takeoff or force:
            self.logPos("land")
            try:
                if not self.simulate:
                    self.tello.land()
            except Exception as e:
                print(e)

            self.state_land = True
            try:
                if not self.simulate:
                    self.tello.end()
            except Exception as e:
                print(e)



    def scene(self):
        config = self.config
        self.logPos("scene")
        if not self.state_takeoff:
            self.start()

        if self.time()  > config["time"]["maxLand"] and not self.state_land:
            self.finish()

        if self.time() > config["time"]["rythmAnalyzeStart"] and not self.state_land and self.state_takeoff:
            self.onRythm()

    def onRythm(self):
        channelPower = self.ovbuffer.lastSeries[-1]
        eegPower = 0

        if self.cntrlChannel in channelPower:
            eegPower = channelPower[self.cntrlChannel]

        minEegP, maxEegP = self.power2height[0]
        minH, maxH       = self.power2height[1]

        self.logPos("eegPower={}, minEegP={}, maxEegP={}".format(eegPower, minEegP, maxEegP))

        if eegPower >= minEegP and eegPower <= maxEegP:
            h = (eegPower - minEegP)/(maxEegP - minEegP) * (maxH - minH)
            realH = minH + h;

            changeH = int(realH - self.height)
            if abs(changeH) > self.minStep:
                self.height = realH
                self.logPos("eegPower={}, go to XYZ, change={}".format(eegPower, changeH))
                if not self.simulate:
                    self.tello.go_xyz_speed(0,0,changeH, self.speed)
            else:
                self.logPos("eegPower={}, change to small, change={}".format(eegPower, changeH))


    def logPos(self, title=""):
        print("time={}: height={} {}".format(self.time(), self.height, title))


toStop = False
def hello():
    # signal.signal(signal.SIGINT, signal_handler)
    print("hello, world")
    if toStop:
        global timer
        timer.stop()

server_address = ('localhost', port)
print('connecting to {} port {}'.format(*server_address))
sock.connect(server_address)

OVBuffer = OpenVibeBuffer()
OVBuffer.title = ['TP9', 'AF7', 'AF8', 'TP10', 'RAUX']

t = Timer(7.0, hello)

eegPower = []
try:
    drone = Drone(config, OVBuffer)
    #timer = RepeatedTimer(10, hello)
    t.start()
    while True:
        data = sock.recv(40)
        eegPower = OVBuffer.analyze(data)
        #print(eegPower)

except KeyboardInterrupt:
    pass
    #print("KeyboardInterrupt has been caught.")
