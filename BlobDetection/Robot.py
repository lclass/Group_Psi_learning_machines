import math
import random
import time
from dataclasses import dataclass
from enum import Enum

import numpy as np

import robobo
from BlobDetector import BlobDetector


@dataclass
class Movement:
    l_speed: int
    r_speed: int
    duration: int


class Actions(Enum):
    STRAIGHT = 0
    LEFT = 1
    RIGHT = 2
    # STRONG_LEFT = 3
    # STRONG_RIGHT = 4


actions_movement_mapping = {
    Actions.STRAIGHT: Movement(15, 15, 1000),
    Actions.LEFT: Movement(-10, 10, 1000),
    Actions.RIGHT: Movement(10, -10, 1000),
    # Actions.STRONG_LEFT: Movement(-10, 10, 1000),
    # Actions.STRONG_RIGHT: Movement(10, -10, 1000)
}

LEARNING_RATE = 0.8
DISCOUNT_FACTOR = 0.95

AMOUNT_IMAGE_SPLITS = 5
AMOUNT_ACTIONS = 3

EPS_START = 0.9
EPS_END = 0.05
EPS_DECAY = 3000

PHONE_TILT = 0.5

class Robot:

    def __init__(self, simulated: bool = False, address: str = '127.0.0.1'):
        self.simulated = simulated
        self._address = address
        if simulated:
            self._rob = robobo.SimulationRobobo().connect(address=address, port=19997)
            self._rob.play_simulation()
        else:
            self._rob = robobo.HardwareRobobo(camera=True).connect(address=address)
        self._rob.set_phone_tilt(PHONE_TILT, 100)

        self._q_matrix = np.zeros((2 ** AMOUNT_IMAGE_SPLITS, AMOUNT_ACTIONS))
        # Load Q-Matrix
        # self.q_matrix = np.load('q_matrix.npy')
        self._collected_food = 0

    def run(self):
        # Load Q-Matrix
        self._q_matrix = np.load('matrices/q_matrix_new_7000.npy')
        i = 0
        while True:
            print(i)
            current_state_index = self._get_current_state_index()
            action_index = np.argmax(self._q_matrix[current_state_index])
            next_action = Actions(action_index)
            self._do_action(action=next_action)

    def train(self, iterations: int = 10000):
        self._q_matrix = np.load('matrices/q_matrix_new_3000.npy')
        current_state_index = self._get_current_state_index()
        count = 0
        for i in range(iterations):
            count += 1
            # See how much food was collected before movement
            collected_food_before = self._collected_food
            eps_threshold = EPS_END + (EPS_START - EPS_END) * math.exp(-1. * i / EPS_DECAY)
            if random.random() < eps_threshold:
                next_action = random.choice(list(Actions))
                action_index = next_action.value
            else:
                action_index = np.argmax(self._q_matrix[current_state_index])
                next_action = Actions(action_index)
            if i % 10 == 0:
                print(f"Iteration {i + 1}/{iterations}")
                print(f"Current Epsilon: {eps_threshold}")
            self._do_action(action=next_action)
            # Update food
            self._collected_food = self._rob.collected_food()
            reward = self._calculate_reward(collected_food_before)
            if next_action == Actions.RIGHT:
                reward += 3
            if next_action == Actions.STRAIGHT:
                reward += 2
            next_state_index = self._get_current_state_index()
            self._update_state_value(state_idx=current_state_index, next_state_idx=next_state_index,
                                     action_idx=action_index,
                                     reward=reward)
            current_state_index = next_state_index
            if i % 1000 == 0:
                np.save(f"matrices/q_matrix_new_{i}.npy", self._q_matrix)
            # Reset if all food is collected
            if self._collected_food == 7:  # or count % 500 == 0
                count = 0
                self._collected_food = 0
                self._rob.stop_world()
                print("Waiting for stop")
                self._rob.wait_for_stop()
                print("Stopped!")
                self._rob.play_simulation()
                print("Continue with simulation!")
                self._rob.set_phone_tilt(PHONE_TILT, 100)
                current_state_index = self._get_current_state_index()
        np.save(f"matrices/q_matrix_new_final.npy", self._q_matrix)

    def _update_state_value(self, state_idx: int, next_state_idx: int, action_idx: int, reward: int) -> None:
        old_value = self._q_matrix[state_idx][action_idx]
        next_q_value = np.amax(self._q_matrix[next_state_idx], axis=0)

        updated_value = (1 - LEARNING_RATE) * old_value + LEARNING_RATE * (reward + DISCOUNT_FACTOR * next_q_value)
        self._q_matrix[state_idx, action_idx] = updated_value

    def _calculate_reward(self, collected_food_before: int) -> int:
        if self._collected_food > collected_food_before:
            return 50
        return -1

    def _do_action(self, action: Actions):
        movement = actions_movement_mapping[action]
        self._rob.move(
            left=movement.l_speed,
            right=movement.r_speed,
            millis=movement.duration
        )

    def _get_current_state_index(self):
        # Make picture
        image = self._rob.get_image_front()
        # Get detection results
        detection_results = BlobDetector.detect_blobs(image)
        # Convert to string and transform base two to base ten for state index
        base_two_val = ''.join([str(int(x)) for x in detection_results])
        state_idx = int(base_two_val, 2)
        return state_idx