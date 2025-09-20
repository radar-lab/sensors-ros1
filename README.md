# Installation


Lidar:
We are using the official Hesai universal ros 1 driver

Radar:
We are using the official TI mmWave ROS repo and follow their instructions
Make sure to have 
```bash
sudo chmod 666 /dev/ttyACM0
sudo chmod 666 /dev/ttyACM1
```

In TI's mmWave ROS driver, we need to go into the launch file and change `/ti_mmwave_0` to `ti_mmwave_0` or the point cloud will not be displayed properly in RVIZ.

Camera:
We are using the develop branch of the usb-cam git repo
need to install libv4l first with 
```bash
sudo apt install libv4l-dev lib4l-utils
```
