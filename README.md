# ROS 1 Package for Hesai Lidar, TI mmWave Radar, and USB Camera

This ROS 1 package allows for simulatneous data visualization and recording of camera, lidar, and radar data for sensor fusion.

This has been tested on ROS 1 Noetic on the Nvidia Jetson Xavier AGX with Hesai Pandar40P and TI AWR1843. This package uses the official Hesai and TI packages for ROS 1.

## Installation
Prerequisites: ensure that ROS 1 is installed using official [instructions](https://wiki.ros.org/noetic/Installation/Ubuntu) and `source /opt/ros/[YOUR_ROS_VERSION]/setup.bash` in `~/.bashrc`. We can add this with `nano ~/.bashrc`.

First, clone the repository
```bash
cd ~
git clone https://github.com/11iu/sensors-ros1.git
cd ~/sensors-ros1
```

Install the dependencies for the packages
```bash
sudo apt install libv4l-dev lib4l-utils
```

Then, build the package with
```bash
catkin_make
```

Use `nano ~/.bashrc` and add these lines to the end:
```bash
source ~/sensors-ros1/devel/setup.bash
export DISABLE_ROS1_EOL_WARNINGS=1
```

We need to fix permissions for the radar with
```bash
sudo chmod 666 /dev/ttyACM0
sudo chmod 666 /dev/ttyACM1
```

## Usage
To receive data from the sensors, modify `config.yaml` to select which sensors you want to use. We can modify the `.cfg` configuration for the radar and `.csv` angle correction file for the lidar. Modify the `camera_config.yaml` and `camera_calibration.yaml` to adjust the USB camera parameters.

After configuring the `.yaml` files, simply run
```bash
cd ~/sensors-ros1
python3 main.py
```

### Common Issues
Cannot receive data from lidar: Ensure the host computer and lidar are on the same subnet (e.g. Lidar is 192.168.1.201, computer is 192.168.1.100). Verify this in Wireshark or going to the lidar control webpage at the lidar's IP address

Cannot receive data from radar: Ensure the computer can connect to the radar by using the [demo visualizer](https://dev.ti.com/mmwavedemovisualizer). Give permissions to the ports as shown above and ensure the configuration file and path in the `config.yaml` are valid

Cannot receive data from camera: Ensure the correct video device is selected in `camera_config.yaml`.

## Future Features
- [ ] Support multiple cameras, radars, and lidars
- [ ] Create GUI tool
- [ ] Modify for ROS 2 support