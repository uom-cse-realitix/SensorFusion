from multiprocessing import Queue

import cv2


# from process_control import ProcessManager
# from operations import focus, count, color

# command_classes = ['count', 'color', 'focus', 'no_op']


class CameraFeed:
    def __init__(self, camera_port, queue: Queue):
        self.camera_port = camera_port
        self.queue = queue
        self.operation = 3
        self.is_zoomed = True
        self.frame_size = 608
        self.scale = 40
        self.object_id = -1

        # Initialize webcam feed
        self.capture = cv2.VideoCapture(self.camera_port)
        self.capture.set(3, 608)
        self.capture.set(4, 608)

    # def process_frame(self, operation, object_id):
    #     self.operation = int(operation[0])
    #     self.object_id = object_id
    #     print(command_classes[self.operation], self.operation)

    def zoom_in(self):
        self.is_zoomed = True
        # if self.scale == 50:
        #     self.is_zoomed = True
        #     self.scale -= 5
        # elif self.scale > 30:
        #     self.scale -= 5

    def zoom_out(self):
        self.is_zoomed = False
        # if self.scale == 50:
        #     self.is_zoomed = False
        #     self.scale += 5
        # elif self.scale < 50:
        #     self.scale += 5

    def perform(self, gesture):
        print(gesture)
        if gesture == 2:
            print("CameraFeed:zoom_in")
            self.zoom_in()
        elif gesture == 3:
            print("CameraFeed:zoom_out")
            self.zoom_out()

    def start_camera(self):

        while True:
            # Acquire frame and expand frame dimensions to have shape: [1, None, None, 3]
            # i.e. a single-column array, where each item in the column has the pixel RGB value
            while not self.queue.empty():
                self.perform(gesture=self.queue.get())

            ret, frame = self.capture.read()
            # frame = detect_objects(frame)
            # get the webcam size
            if self.is_zoomed:
                # get the webcam size
                height, width, channels = frame.shape

                # prepare the crop
                center = int(height / 2), int(width / 2)
                radius = int(self.scale * height / 100), int(self.scale * width / 100)

                minX, maxX = center[0] - radius[0], center[0] + radius[0]
                minY, maxY = center[1] - radius[1], center[1] + radius[1]

                cropped = frame[minX:maxX, minY:maxY]
                frame = cv2.resize(cropped, (width, height))

            # frame_expanded = np.expand_dims(frame, axis=0)
            # if self.operation == 2:
            #     focus(frame, self.object_id)
            # elif self.operation == 0:
            #     count(frame, self.object_id)
            # elif self.operation == 1:
            #     color(frame, self.object_id)

            # All the results have been drawn on the frame, so it's time to display it.
            cv2.imshow('Object detector', frame)
            # Press 'q' to quit
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
        # Clean up
        self.capture.release()
        cv2.destroyAllWindows()
