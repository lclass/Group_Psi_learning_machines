from enum import Enum

from util import Task
from Robot import Robot



def main():
    #rob = Robot(simulated=True)
    rob = Robot(address="172.20.10.9")
    rob.run()
    #rob.train(task=Task.COLLECT_FOOD)


if __name__ == "__main__":
    main()
