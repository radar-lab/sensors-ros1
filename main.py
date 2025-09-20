import yaml
import subprocess
from datetime import datetime
import os
import time
import signal

with open('./config.yaml') as f:
    config = yaml.safe_load(f)

arguments = []  # recording arguments passed to launch file
camera = config['use']['camera']['enabled']
lidar = config['use']['lidar']['enabled']
radar = config['use']['radar']['enabled']

arguments.append('use_camera:=true' if camera else 'use_camera:=false')
arguments.append('use_radar:=true' if radar else 'use_radar:=false')
arguments.append('use_lidar:=true' if lidar else 'use_lidar:=false')
arguments.append('show_rviz:=true' if config['show']['rviz'] else 'show_rviz:=false')
arguments.append('show_image_view:=true' if config['show']['image_view'] else 'show_image_view:=false')
arguments.append(f"lidar_ip:={config['use']['lidar']['ip']}")

radar_cfg_fullpath = os.path.abspath(config['use']['radar']['cfg_file'])
arguments.append(f"radar_cfg:={radar_cfg_fullpath}")

lidar_csv_fullpath = os.path.abspath(config['use']['lidar']['correction_csv'])
arguments.append(f"lidar_correction_file:={lidar_csv_fullpath}")

camera_yaml_fullpath = os.path.abspath(config['use']['camera']['config'])
arguments.append(f"camera_config:={camera_yaml_fullpath}")

launch_cmd = ["roslaunch", "use_sensors", "sensors.launch"] + arguments
launch_proc = subprocess.Popen(launch_cmd, start_new_session=True) # launch nodes, start new seesion to prevent ctrl c from affecting launch

def stop_roslaunch():
    """Send SIGINT to the roslaunch process group and wait for clean exit."""
    if launch_proc.poll() is None:
        try:
            os.killpg(launch_proc.pid, signal.SIGINT)
            launch_proc.wait(timeout=7)
        except Exception:
            # Fallback if it ignores SIGINT
            launch_proc.terminate()
            try:
                launch_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                launch_proc.kill()

# Recording to bag
def generate_record_cmd():
    bag_dir = os.path.abspath(config['record']['output_dir'])
    current_time = datetime.now()
    current_time_str = current_time.strftime("%Y-%m-%d_%H:%M:%S")  # e.g. 2025-09-20_16:21:55
    sensors_str = ''
    topics = []

    if camera:
        sensors_str += 'c'
        topics.append('/usb_cam/image_raw' if config['record']['raw_camera'] else '/usb_cam/image_raw/compressed')
    if lidar:
        sensors_str += 'l'
        topics.append('/hesai/pandar')
    if radar:
        sensors_str += 'r'
        topics.append('/ti_mmwave/radar_scan')

    bag_path = os.path.join(bag_dir, f'{sensors_str}_{current_time_str}.bag')

    
    # make output dir if it doesn't exist
    os.makedirs(bag_dir, exist_ok=True)

    record_cmd = ['rosbag', 'record', '-O', bag_path] + topics
    return record_cmd


if config['record']['enabled'] and (camera or lidar or radar):
    time.sleep(10)  # wait for nodes to launch first

    # recording loop to record unlimited number of times
    while True:
        try:
            choice = input("\n############## Enter 'r' to record, 'q' to quit ##############\n").strip().lower()
        except KeyboardInterrupt:
            continue
        if choice == 'q':
            break  # quit everything
        elif choice != 'r':
            continue  # prompt again, need valid input

        record_proc = subprocess.Popen(generate_record_cmd())
        print("Recording in progress, 'Ctrl + C' to stop...")
        start_time = time.time()
        try:
            record_proc.wait()  # block until user Ctrl+C or rosbag exits
        except KeyboardInterrupt:
            # stop bag process
            if record_proc.poll() is None:
                record_proc.send_signal(signal.SIGINT)
                try:
                    record_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    record_proc.terminate()
                    record_proc.wait()
            end_time = time.time()
            print(f"\nSuccesfully recorded {int((end_time - start_time)//60)}m {int((end_time - start_time) % 60)}s of data\n")
        finally:
            record_proc = None

    stop_roslaunch() # quit everyting
else:
    # no recording, only close launch on ctrl c
    try:
        launch_proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        stop_roslaunch()
        print("Quit successfully")
