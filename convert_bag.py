# Usage: python3 convert_bag.py ./bags ./converted
# FIXME: we should use header timestamp instead of time when bag stored the data
# TODO: add binary capability for pcd
import rosbag
import argparse
import os
import numpy as np
import struct
from tqdm import tqdm
import cv2
import json

def convert_lidar(bag, dir):
    '''Convert PointCloud 2 in bag to .pcd files'''

    def pc2_to_arr(msg):
        '''Convert PointCloud2 in bag to np array'''
        # Get point cloud info
        width = msg.width
        height = msg.height
        point_step = msg.point_step
        
        # Parse field information
        fields = {}
        for field in msg.fields:
            fields[field.name] = {
                'offset': field.offset,
                'datatype': field.datatype,
                'count': field.count
            }
        
        # Convert pointcloud2 binary to numpy array using vectorized operations
        total_points = height * width
        
        # Create a structured dtype based on point_step
        dt = np.dtype([
            ('x', np.float32),
            ('y', np.float32),
            ('z', np.float32),
            ('intensity', np.float32)
        ])
        
        # Use numpy's frombuffer with stride to extract data efficiently
        # This assumes x, y, z are at offsets 0, 4, 8 and intensity at its offset
        data = np.frombuffer(msg.data, dtype=np.uint8)
        
        # Reshape to (num_points, point_step) to process all points at once
        data_reshaped = data.reshape(total_points, point_step)
        
        # Extract x, y, z, intensity using numpy views (vectorized)
        x = data_reshaped[:, 0:4].view(np.float32).flatten()
        y = data_reshaped[:, 4:8].view(np.float32).flatten()
        z = data_reshaped[:, 8:12].view(np.float32).flatten()
        
        intensity_offset = fields['intensity']['offset']
        intensity = data_reshaped[:, intensity_offset:intensity_offset+4].view(np.float32).flatten()
        
        # Stack into final array
        return np.column_stack((x, y, z, intensity))

    # write numpy array to PCD file
    def arr_to_pcd(filename, arr):
        num_points = arr.shape[0] # number of points, rows in pcd
        header = f'''VERSION .7
FIELDS x y z intensity
SIZE 4 4 4 4
TYPE F F F F
COUNT 1 1 1 1
WIDTH {num_points}
HEIGHT 1
VIEWPOINT 0 0 0 1 0 0 0
POINTS {num_points}
DATA ascii
'''
        with open(filename, 'w') as f:
            f.write(header)
            # write each point to txt
            np.savetxt(f, arr, fmt='%.6f')

    # save every frame as a new pcd file
    print('Converting lidar...')
    num_messages = bag.get_type_and_topic_info().topics['/hesai/pandar'].message_count
    for topic, message, t in tqdm(bag.read_messages(topics=['/hesai/pandar']), total=num_messages):
        points_arr = pc2_to_arr(message)
        arr_to_pcd(os.path.join(dir, f'{t.to_nsec()}.pcd'), points_arr)
    print()

def convert_radar(bag, dir):
    def arr_to_pcd(filename, arr):
        num_points = arr.shape[0] # number of points, rows in pcd
        header = f'''VERSION .7
FIELDS x y z velocity
SIZE 4 4 4 4
TYPE F F F F
COUNT 1 1 1 1
WIDTH {num_points}
HEIGHT 1
VIEWPOINT 0 0 0 1 0 0 0
POINTS {num_points}
DATA ascii
'''
        with open(filename, 'w') as f:
            f.write(header)
            for point in arr:
                np.savetxt(f, [point])

    print('Converting radar...')
    current_frame = []
    frame_start_time = 0
    num_messages = bag.get_type_and_topic_info().topics['/ti_mmwave/radar_scan'].message_count
    for topic, message, t in tqdm(bag.read_messages(topics=['/ti_mmwave/radar_scan']), total=num_messages):
        point = [message.x, message.y, message.z, message.velocity]

        # new frame when point_id is 0
        if message.point_id == 0:
            # no previous frames on first frame
            if len(current_frame) > 0:
                # write complete frame to pcd
                arr_to_pcd(os.path.join(dir, f'{frame_start_time}.pcd'), np.array(current_frame))

            # start new frame
            frame_start_time = t.to_nsec()
            current_frame = [point]
        else:
            current_frame.append(point)

    # add last frame
    if current_frame:
        arr_to_pcd(os.path.join(dir, f'{frame_start_time}.pcd'), np.array(current_frame))
    print()

def convert_camera(bag, dir):
    print('Converting camera...')
    num_messages = bag.get_type_and_topic_info().topics['/usb_cam/image_raw/compressed'].message_count
    for topic, message, t in tqdm(bag.read_messages(topics=['/usb_cam/image_raw/compressed']), total=num_messages):
        # write jpg
        with open(os.path.join(dir, f'{t.to_nsec()}.jpg'), 'wb') as f:
            f.write(message.data)
    print()

def synchronize_sensors(camera_files, radar_files, lidar_files, output_file):
    '''Synchronizes timestamps of sensors with brute force and writes output to json'''
    # TODO: make this algorithm not O(n^3), use binary search
    matches = []

    # match a radar and lidar frame to each camera frame
    if len(camera_files) > 0 and len(camera_files) <= len(radar_files) and len(camera_files) <= len(lidar_files):
        for camera_file in camera_files:
            camera_time = int(os.path.splitext(camera_file)[0])
            
            # match radar
            radar_diff = float('inf')
            closest_radar_file = ''
            for radar_file in radar_files:
                radar_time = int(os.path.splitext(radar_file)[0])
                diff = abs(radar_time - camera_time)
                if diff < radar_diff:
                    radar_diff = diff  # Update the difference!
                    closest_radar_file = radar_file

            # match lidar
            lidar_diff = float('inf')
            closest_lidar_file = ''
            for lidar_file in lidar_files:
                lidar_time = int(os.path.splitext(lidar_file)[0])
                diff = abs(lidar_time - camera_time)
                if diff < lidar_diff:
                    lidar_diff = diff  # Update the difference!
                    closest_lidar_file = lidar_file

            matches.append({
                'camera': camera_file,
                'lidar': closest_lidar_file,
                'radar': closest_radar_file
            })

    # match a camera and lidar frame to each radar frame
    elif len(radar_files) > 0 and len(radar_files) <= len(camera_files) and len(radar_files) <= len(lidar_files):
        for radar_file in radar_files:
            radar_time = int(os.path.splitext(radar_file)[0])
            
            # match camera
            camera_diff = float('inf')
            closest_camera_file = ''
            for camera_file in camera_files:
                camera_time = int(os.path.splitext(camera_file)[0])
                diff = abs(camera_time - radar_time)
                if diff < camera_diff:
                    camera_diff = diff  # Update the difference!
                    closest_camera_file = camera_file

            # match lidar
            lidar_diff = float('inf')
            closest_lidar_file = ''
            for lidar_file in lidar_files:
                lidar_time = int(os.path.splitext(lidar_file)[0])
                diff = abs(lidar_time - radar_time)
                if diff < lidar_diff:
                    lidar_diff = diff  # Update the difference!
                    closest_lidar_file = lidar_file

            matches.append({
                'camera': closest_camera_file,
                'lidar': closest_lidar_file,
                'radar': radar_file
            })

    # match a camera and radar frame to each lidar frame
    else:
        for lidar_file in lidar_files:
            lidar_time = int(os.path.splitext(lidar_file)[0])
            
            # match camera
            camera_diff = float('inf')
            closest_camera_file = ''
            for camera_file in camera_files:
                camera_time = int(os.path.splitext(camera_file)[0])
                diff = abs(camera_time - lidar_time)
                if diff < camera_diff:
                    camera_diff = diff  # Update the difference!
                    closest_camera_file = camera_file

            # match radar
            radar_diff = float('inf')
            closest_radar_file = ''
            for radar_file in radar_files:
                radar_time = int(os.path.splitext(radar_file)[0])
                diff = abs(radar_time - lidar_time)
                if diff < radar_diff:
                    radar_diff = diff  # Update the difference!
                    closest_radar_file = radar_file

            matches.append({
                'camera': closest_camera_file,
                'lidar': lidar_file,
                'radar': closest_radar_file
            })

    with open(output_file, 'w') as f:
        json.dump(matches, f, indent=2)

def main():
    # get input and output paths from cli arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('bag', help='Bag directory path')
    parser.add_argument('output', help='Output directory path')
    args = parser.parse_args()

    # check if bag directory exists
    if not os.path.isdir(args.bag):
        print('Error: bag directory does not exist')
        return
    
    # loop through every bag in directory and convert
    for filename in tqdm(os.listdir(args.bag)):
        print(filename)
        if os.path.splitext(filename)[1] != '.bag':
            continue
        
        full_filename = os.path.join(args.bag, filename)

        bag = rosbag.Bag(full_filename)
        print(f'\nBag info:\n{bag}\n')

        # get topics from bag to see what we can convert
        topics = bag.get_type_and_topic_info().topics.keys()
        has_camera = '/usb_cam/image_raw/compressed' in topics # FIXME: process raw too
        has_lidar = '/hesai/pandar' in topics
        has_radar = '/ti_mmwave/radar_scan' in topics

        # make output directory with bag name if it doesn't exist
        output_dir = os.path.join(args.output, os.path.splitext(filename)[0])
        os.makedirs(output_dir, exist_ok=True)
        camera_dir = os.path.join(output_dir, 'camera')
        radar_dir = os.path.join(output_dir, 'radar')
        lidar_dir = os.path.join(output_dir, 'lidar')

        if has_camera:
            os.makedirs(camera_dir, exist_ok=True)
            convert_camera(bag, camera_dir)

        if has_radar:
            os.makedirs(radar_dir, exist_ok=True)
            convert_radar(bag, radar_dir)

        if has_lidar:
            os.makedirs(lidar_dir, exist_ok=True)
            convert_lidar(bag, lidar_dir)

        # create a json with synchronized sensors
        camera_files = os.listdir(camera_dir) if os.path.exists(camera_dir) else []
        radar_files = os.listdir(radar_dir) if os.path.exists(radar_dir) else []
        lidar_files = os.listdir(lidar_dir) if os.path.exists(lidar_dir) else []
        synchronize_sensors(camera_files, radar_files, lidar_files, os.path.join(output_dir, 'synchronized.json'))

        print('Successfully finished conversion and synchronization')

if __name__ == "__main__":
    main()
