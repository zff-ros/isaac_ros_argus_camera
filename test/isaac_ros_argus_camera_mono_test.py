# SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
# Copyright (c) 2021-2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

import os
import pathlib
import shlex
import subprocess
import time

import cv2
from cv_bridge import CvBridge
from isaac_ros_test import IsaacROSBaseTest
from launch_ros.actions import ComposableNodeContainer
from launch_ros.descriptions import ComposableNode
import launch_testing
import pytest
import rclpy

from sensor_msgs.msg import CameraInfo, Image

SKIP_TEST = True


@pytest.mark.rostest
def generate_test_description():
    device_id = 0
    command = f'"if [ -c /dev/video{device_id} ]; then echo Device Found; \
                else echo Device Not Found; fi"'
    result = subprocess.run(shlex.split(command), shell=True, capture_output=True, text=True)

    if(result.stdout.strip() == 'Device Found'):
        IsaacArgusMonoNodeTest.skip_test = False

        argus_mono_node = ComposableNode(
            name='argus_mono',
            package='isaac_ros_argus_camera',
            plugin='nvidia::isaac_ros::argus::ArgusMonoNode',
            namespace=IsaacArgusMonoNodeTest.generate_namespace(),
            parameters=[{'camera_id': device_id}]
        )

        return IsaacArgusMonoNodeTest.generate_test_description([
            ComposableNodeContainer(
                name='argus_mono_container',
                package='rclcpp_components',
                executable='component_container_mt',
                composable_node_descriptions=[argus_mono_node],
                namespace=IsaacArgusMonoNodeTest.generate_namespace(),
                output='screen',
                arguments=['--ros-args', '--log-level', 'info',
                           '--log-level', 'isaac_ros_test.argus_mono:=debug',
                           '--log-level', 'NitrosImage:=debug',
                           '--log-level', 'NitrosCameraInfo:=debug'],
            )
        ])
    else:
        IsaacArgusMonoNodeTest.skip_test = True
        return IsaacArgusMonoNodeTest.generate_test_description(
            [launch_testing.actions.ReadyToTest()])


class IsaacArgusMonoNodeTest(IsaacROSBaseTest):
    filepath = pathlib.Path(os.path.dirname(__file__))
    skip_test = False

    def test_image_capture(self):
        """
        Test image capture from argus mono camera.

        Test that the functionality to read the image message from argus mono camera and save
        it to the disk.
        """
        if self.skip_test:
            self.skipTest('No camera detected! Skipping test.')
        else:
            TIMEOUT = 10
            received_messages = {}

            self.generate_namespace_lookup(['left/image_raw', 'left/camerainfo'])

            subs = self.create_logging_subscribers(
                [('left/image_raw', Image), ('left/camerainfo', CameraInfo)], received_messages,
                accept_multiple_messages=True)
            try:
                end_time = time.time() + TIMEOUT
                done = False

                while time.time() < end_time:

                    rclpy.spin_once(self.node, timeout_sec=(0.1))
                    if len(received_messages['left/image_raw']) > 0 and \
                            len(received_messages['left/camerainfo']) > 0:
                        done = True
                        break
                self.assertTrue(done, 'Appropriate output not received')
                left_image = received_messages['left/image_raw']

                left_cv_image = CvBridge().imgmsg_to_cv2(left_image[0], desired_encoding='bgr8')
                cv2.imwrite('left_image.png', left_cv_image)

            finally:
                self.node.destroy_subscription(subs)
