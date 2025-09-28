# Usage: python3 convert_bag.py clr_2025-09-27_21_57_07.bag ./converted
# FIXME: we should use header timestamp instead of time when bag stored the data
# TODO: add binary capability for pcd
import rosbag
import argparse
import os
import numpy as np
import struct
from tqdm import tqdm
import cv2

def convert_lidar(bag, dir):
    '''Convert PointCloud 2 in bag to .pcd files'''

    def pc2_to_arr(msg):
        '''Convert PointCloud2 in bag to np array'''
        # Get point cloud info
        width = msg.width
        height = msg.height
        point_step = msg.point_step
        row_step = msg.row_step
        
        # Parse field information
        fields = {}
        for field in msg.fields:
            fields[field.name] = {
                'offset': field.offset,
                'datatype': field.datatype,
                'count': field.count
            }
        
        # convert pointcloud2 binary to numpy array of bytes
        data = np.frombuffer(msg.data, dtype=np.uint8)
        total_points = height * width

        point_data_list = []
        for i in range(total_points): # TODO: use numpy view() function to vectorize instead of for loop
            start_idx = i * point_step
            point_data = data[start_idx:start_idx + point_step] # point_step is how many bytes of data per point
            
            # extract x y z, each is float32 (4 bytes)
            x = struct.unpack('f', point_data[0:4])[0]
            y = struct.unpack('f', point_data[4:8])[0]
            z = struct.unpack('f', point_data[8:12])[0]
            
            # Extract intensity
            intensity_offset = fields['intensity']['offset']
            intensity = struct.unpack('f', point_data[intensity_offset:intensity_offset+4])[0] # float32

            # # Extract timestamp
            # ts_field = 'timestamp' if 'timestamp' in fields else 't'
            # ts_offset = fields[ts_field]['offset']
            # timestamp = struct.unpack('d', point_data[ts_offset:ts_offset+8])[0] # float64
            
            # # Extract ring
            # ring_offset = fields['ring']['offset']            
            # ring = struct.unpack('H', point_data[ring_offset:ring_offset+2])[0] # uint16

            point_data_list.append([x, y, z, intensity])
        
        return np.array(point_data_list)

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
            for point in arr:
                np.savetxt(f, [point])

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
        # message.data is the raw jpeg bytes, convert it to cv2 image
        img = cv2.imdecode(np.frombuffer(message.data, np.uint8), cv2.IMREAD_COLOR)
        cv2.imwrite(os.path.join(dir, f'{t}.jpg'), img)
    print()

def main():
    # get input and output paths from cli arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('bag', help='Bag file path')
    parser.add_argument('output', help='Output directory path')
    args = parser.parse_args()

    # check if bag file exists
    if not os.path.isfile(args.bag):
        print('Error: bag file does not exist')
        return

    bag = rosbag.Bag(args.bag)
    print(f'\nBag info:\n{bag}\n')

    # get topics from bag to see what we can convert
    topics = bag.get_type_and_topic_info().topics.keys()
    has_camera = '/usb_cam/image_raw/compressed' in topics # FIXME: process raw too
    has_lidar = '/hesai/pandar' in topics
    has_radar = '/ti_mmwave/radar_scan' in topics

    # make output directory if it doesn't exist
    os.makedirs(args.output, exist_ok=True)

    if has_camera:
        camera_dir = os.path.join(args.output, 'camera')
        os.makedirs(camera_dir, exist_ok=True)
        convert_camera(bag, camera_dir)

    if has_radar:
        radar_dir = os.path.join(args.output, 'radar')
        os.makedirs(radar_dir, exist_ok=True)
        convert_radar(bag, radar_dir)

    if has_lidar:
        lidar_dir = os.path.join(args.output, 'lidar')
        os.makedirs(lidar_dir, exist_ok=True)
        convert_lidar(bag, lidar_dir)

    print('Successfully finished conversion')

if __name__ == "__main__":
    main()