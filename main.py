import cv2
import numpy as np
import av
import time
import copy
from enum import Enum

import streamlit as st
from streamlit_webrtc import AudioProcessorBase, WebRtcMode, RTCConfiguration, webrtc_streamer

from face_detectors import Ultralight320Detector
import mediapipe as mp

import pvcobra
from pvrecorder import PvRecorder

class GazeDirection(Enum):
    LEFT = "LEFT"
    CENTER = "CENTER"
    RIGHT = "RIGHT"


class HandsPosition(Enum):
    BOTTOM = "BOTTOM"
    TOP = "TOP"

cobra = pvcobra.create(access_key='your_access_key')
recorder = PvRecorder(frame_length=512, device_index=3)

FONT = cv2.FONT_HERSHEY_PLAIN
LEFT_EYE_POINTS = [36, 37, 38, 39, 40, 41]
RIGHT_EYE_POINTS = [42, 43, 44, 45, 46, 47]
BLUE = (0, 0, 255)
RED = (255, 0, 0)
WHITE = (255, 255, 255)

pose = mp.solutions.pose.Pose(model_complexity=0)
detector = Ultralight320Detector()

RTC_CONFIGURATION = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})

streaming_placeholder = st.empty()


def det_gaze_ratio(eye_points, facial_landmarks, height, width, gray):
    """

    Calculate white pixel ratio.

    """

    eye_region = np.array([(facial_landmarks[eye_points[0]][0], facial_landmarks[eye_points[0]][1]),
                           (facial_landmarks[eye_points[1]][0], facial_landmarks[eye_points[1]][1]),
                           (facial_landmarks[eye_points[2]][0], facial_landmarks[eye_points[2]][1]),
                           (facial_landmarks[eye_points[3]][0], facial_landmarks[eye_points[3]][1]),
                           (facial_landmarks[eye_points[4]][0], facial_landmarks[eye_points[4]][1]),
                           (facial_landmarks[eye_points[5]][0], facial_landmarks[eye_points[5]][1])], np.int32)

    mask = np.zeros((height, width), np.uint8)
    cv2.polylines(mask, [eye_region], True, 255, 2)
    cv2.fillPoly(mask, [eye_region], 255)
    eye = cv2.bitwise_and(gray, gray, mask=mask)

    min_x = np.min(eye_region[:, 0])
    max_x = np.max(eye_region[:, 0])
    min_y = np.min(eye_region[:, 1])
    max_y = np.max(eye_region[:, 1])

    gray_eye = eye[min_y: max_y, min_x: max_x]
    _, threshold_eye = cv2.threshold(gray_eye, 70, 255, cv2.THRESH_BINARY_INV)
    height, width = threshold_eye.shape

    left_side_threshold = threshold_eye[0: height, 0: int(width / 2)]
    left_side_white = cv2.countNonZero(left_side_threshold)

    right_side_threshold = threshold_eye[0: height, int(width / 2): width]
    right_side_white = cv2.countNonZero(right_side_threshold)

    if left_side_white == 0:
        gaze_ration = 1
    elif right_side_white == 0:
        gaze_ration = 5
    else:
        gaze_ration = left_side_white / right_side_white

    return gaze_ration


def get_gaze_direction(img, img_height, img_width):
    """

    Calculate the direction of the eye(left, center, right).

    """

    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    bbox = detector.detect_faces_keypoints(gray, get_all=True)

    landmarks = bbox[0]['keypoints']

    gaze_ration_left_eye = det_gaze_ratio(LEFT_EYE_POINTS, landmarks, img_height, img_width, gray)
    gaze_ration_right_eye = det_gaze_ratio(RIGHT_EYE_POINTS, landmarks, img_height, img_width, gray)
    gaze_ratio = (gaze_ration_right_eye + gaze_ration_left_eye) / 2

    if gaze_ratio <= 0.85:
        gaze_direction = GazeDirection.LEFT.value
    elif 0.85 < gaze_ratio < 1.6:
        gaze_direction = GazeDirection.CENTER.value
    else:
        gaze_direction = GazeDirection.RIGHT.value

    return gaze_direction


def get_coordinates(number, body, img_height, img_width):
    """

    Calculate the coordinates of a key point in an image.

    """

    x = int(body.pose_landmarks.landmark[number].x * img_width)
    y = int(body.pose_landmarks.landmark[number].y * img_height)

    return x, y


def hand_filling(hand_coordinates, image):
    """

    Fill hands with color to prevent mpPose from finding them again.

    """
	
    hand_coordinates = hand_coordinates.reshape((-1, 1, 2))
    cv2.fillPoly(image, [hand_coordinates], color=WHITE)


def callback(frame: av.VideoFrame) -> av.VideoFrame:

    img_rgb = frame.to_ndarray(format="rgb24")

    image_height, image_width, _ = img_rgb.shape

    try:
        cv2.putText(img_rgb, 'Eyes: ' + get_gaze_direction(img_rgb, image_height, image_width), (10, 120), FONT, 2,
                   (255, 0, 0), 3)
    except IndexError:
        cv2.putText(img_rgb, 'The examinee is absent!', (10, 200), cv2.FONT_HERSHEY_PLAIN, 3, (255, 0, 0), 3)

    body = pose.process(img_rgb)

    img_filled_person = copy.deepcopy(img_rgb)

    line_thickness = 1
    circle_size = 3
    point_color = BLUE

    if body.pose_landmarks:
	
	#################
        # Drawing hands #
        #################
	
        # shoulders
        p11 = get_coordinates(11, body, image_height, image_width)
        cv2.circle(img_rgb, p11, circle_size, point_color, -1)
        p12 = get_coordinates(12, body, image_height, image_width)
        cv2.circle(img_rgb, p12, circle_size, point_color, -1)

        cv2.line(img_rgb, p12, p11, WHITE, 2)

        # right hand
        p13 = get_coordinates(13, body, image_height, image_width)
        cv2.circle(img_rgb, p13, circle_size, point_color, -1)
        p15 = get_coordinates(15, body, image_height, image_width)
        cv2.circle(img_rgb, p15, circle_size, point_color, -1)
        p17 = get_coordinates(17, body, image_height, image_width)
        cv2.circle(img_rgb, p17, circle_size, point_color, -1)
        p19 = get_coordinates(19, body, image_height, image_width)
        cv2.circle(img_rgb, p19, circle_size, point_color, -1)
        p21 = get_coordinates(21, body, image_height, image_width)
        cv2.circle(img_rgb, p21, circle_size, point_color, -1)

        cv2.line(img_rgb, p11, p13, WHITE, line_thickness)
        cv2.line(img_rgb, p13, p15, WHITE, line_thickness)
        cv2.line(img_rgb, p15, p21, WHITE, line_thickness)
        cv2.line(img_rgb, p15, p17, WHITE, line_thickness)
        cv2.line(img_rgb, p15, p19, WHITE, line_thickness)

        # left hand
        p14 = get_coordinates(14, body, image_height, image_width)
        cv2.circle(img_rgb, p14, circle_size, point_color, -1)
        p16 = get_coordinates(16, body, image_height, image_width)
        cv2.circle(img_rgb, p16, circle_size, point_color, -1)
        p18 = get_coordinates(18, body, image_height, image_width)
        cv2.circle(img_rgb, p18, circle_size, point_color, -1)
        p20 = get_coordinates(20, body, image_height, image_width)
        cv2.circle(img_rgb, p20, circle_size, point_color, -1)
        p22 = get_coordinates(22, body, image_height, image_width)
        cv2.circle(img_rgb, p22, circle_size, point_color, -1)

        cv2.line(img_rgb, p12, p14, WHITE, line_thickness)
        cv2.line(img_rgb, p14, p16, WHITE, line_thickness)
        cv2.line(img_rgb, p16, p22, WHITE, line_thickness)
        cv2.line(img_rgb, p16, p20, WHITE, line_thickness)
        cv2.line(img_rgb, p16, p18, WHITE, line_thickness)

	#####################################
        # Filling a person for re-detection #
        #####################################

        # bbox for second person
        p1 = get_coordinates(1, body, image_height, image_width)
        p2 = get_coordinates(2, body, image_height, image_width)
        p3 = get_coordinates(3, body, image_height, image_width)
        p4 = get_coordinates(4, body, image_height, image_width)
        p5 = get_coordinates(5, body, image_height, image_width)
        p6 = get_coordinates(6, body, image_height, image_width)
        p7 = get_coordinates(7, body, image_height, image_width)
        p8 = get_coordinates(8, body, image_height, image_width)

        bbox_cor_x = np.array([p1[0], p2[0], p3[0], p4[0], p5[0], p6[0], p7[0], p8[0], p12[0], p13[0], p14[0]])
        bbox_cor_y = np.array([p1[1], p2[1], p3[1], p4[1], p5[1], p6[1], p7[1], p8[1], p12[1], p13[1], p14[1]])

        # Right hand polygon
        right_hand_points = np.array([[p20[0], p20[1] - 10], [p22[0], p22[1]], [p14[0], p14[1] - 10], [p14[0], p14[1] + 10], [p18[0], p18[1] + 10]], np.int32)
        hand_filling(right_hand_points, img_croped)

        # Left hand polygon
        reft_hand_points = np.array([[p13[0], p13[1] - 10], [p13[0], p13[1] + 10], [p21[0], p21[1]], [p19[0], p19[1] - 10], [p17[0], p17[1] + 10]], np.int32)
        hand_filling(reft_hand_points, img_croped)

        bb_y_min = np.min(bbox_cor_y)
        bb_y_max = np.max(bbox_cor_y)

        bb_x_min = np.min(bbox_cor_x)
        bb_x_max = np.max(bbox_cor_x)

        # Expand bbox
        if image_height - bb_y_max <= 35:
            bb_y_max = image_height

        if image_width - bb_x_max <= 35:
            bb_x_max = image_width

        # Draw filled bbox
        cv2.rectangle(img_filled_person, (bb_x_min, bb_y_min-70), (bb_x_max, bb_y_max), (255, 255, 255), -1)

        body_second = pose.process(img_filled_person)

        if body_second.pose_landmarks:
            cv2.putText(img_filled_person, 'Second person detected!', (10, 260), cv2.FONT_HERSHEY_PLAIN, 2, (255, 0, 0), 3)


        # Hands position detection
        hand_border = (image_height/100)*88

        if (p16[1] > hand_border and p18[1] > hand_border and p20[1] > hand_border and p22[1] > hand_border) or \
                (p15[1] > hand_border and p17[1] > hand_border and p19[1] > hand_border and p21[1] > hand_border):
            hands_positions = HandsPosition.BOTTOM.value
        else:
            hands_positions = HandsPosition.TOP.value

        cv2.putText(img_rgb, 'Hands: ' + hands_positions, (10, 90), cv2.FONT_HERSHEY_PLAIN, 2, (255, 0, 0), 3)

    return av.VideoFrame.from_ndarray(img_rgb, format="rgb24")


def process_audio(frame: av.AudioFrame) -> av.AudioFrame:

    recorder.start()
   
    while True:
        pcm = recorder.read()
        is_voiced = cobra.process(pcm)
        print(is_voiced)


with streaming_placeholder.container():
    webrtc_ctx = webrtc_streamer(
        key="object-detection",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
        video_frame_callback=callback,
        audio_frame_callback=process_audio,
        media_stream_constraints={"video": True, "audio": True},
        async_processing=True,
    )
