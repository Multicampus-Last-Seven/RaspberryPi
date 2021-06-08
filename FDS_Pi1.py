import argparse
from threading import Thread
import time
import numpy
import cv2

import pigpio

import paho.mqtt.publish as publish
import paho.mqtt.client as mqtt

class Video(Thread):
    def __init__(self):
        super().__init__()

        # 촬영을 위한 Video객체 생성
        self.cap = cv2.VideoCapture(0)
        assert self.cap.isOpened(), f'Failed to open'
        print(self.cap)

        self.w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) % 100

    def run(self):
        ret, imgs = self.cap.read() # 첫 프레임 보장
        n = 0
        sending_imgs = 0
        accumulated_time = 0
        # num = 0
        while self.cap.isOpened():
            n += 1
            # num += 1
            sending_imgs += 1
            if sending_imgs == 1:
                start_time = time.time()
            if sending_imgs == 30:
                sending_imgs = 0
                frame_time = time.time() - start_time
                print(f'1frame time (30 imgs) : {frame_time}')
                accumulated_time += frame_time

            n %= 4
            self.cap.grab()
            if n == 0:  # read every 4th frame
                success, im = self.cap.retrieve()
                imgs = im if success else imgs * 0

            encode_param=[int(cv2.IMWRITE_JPEG_QUALITY), 90]
            result, imgencode = cv2.imencode('.jpg', imgs, encode_param)
            data = numpy.array(imgencode)
            byteData = bytearray(data)
            publish.single("mydata/stream/camera/ALR299PNY931", byteData, hostname="15.165.185.201") # Broker로 전송 (CLOUD)
            if accumulated_time > 10:
                print(f'accumulated time : {accumulated_time}, send img to AI model')
                accumulated_time = 0
                publish.single("mydata/fire/ALR299PNY931", byteData, hostname="15.165.185.201") # Broker로 전송 (AI)
            time.sleep(1 / self.fps)  # wait time

        self.cap.release()
        # cv2.destroyAllWindows()

# 사용전 서버 데몬 기동 필요
# sudo pigpiod
# 정지
# sudo killall pigpiod
class Window():
    def __init__(self):
        self.pin = 16
        self.pi = pigpio.pi()

    def windowOpen(self):
        try:
            print("window open")
            self.pi.set_servo_pulsewidth(self.pin, 1400)
        except KeyboardInterrupt:
            pass

    def windowClose(self):
        try:
            print("window close")
            self.pi.set_servo_pulsewidth(self.pin, 500)
        except KeyboardInterrupt:
            pass

def on_connect(client, usedata, flags, rc):
    print("connect.."+str(rc))
    if rc == 0:
        client.subscribe("mydata/stream/alarm/motor") # 토픽명
    else:
        print("연결실패")

# 메세지가 도착했을 때 처리할 일들
def on_message(client, userdata, msg):
    data = msg.payload.decode("utf-8")
    try:
        if data == "open":
            thread = Thread(target=window.windowOpen())
        elif data == "close":
            thread = Thread(target=window.windowClose())
        thread.start()
    except:
        pass

if __name__ == "__main__":
    mqttClient = mqtt.Client()
    mqttClient.on_connect = on_connect
    mqttClient.on_message = on_message
    mqttClient.connect("15.165.185.201", 1883, 60)

    window = Window()
    video = Video()
    video.start()

    mqttClient.loop_forever()