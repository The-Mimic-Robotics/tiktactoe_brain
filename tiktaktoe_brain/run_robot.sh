#!/bin/bash

# 1. Grab the command passed from the AI Python script
ROBOT_COMMAND="$1"

# 2. Activate your specific lerobot environment
# (Adjust this path depending on if you use conda, venv, or ROS)

#source ~/miniconda3/etc/profile.d/conda.sh
conda activate lerobot

# 3. Run the actual robot control script and pass the command
echo "Executing hardware move: $ROBOT_COMMAND"
# python perform_move.py "$ROBOT_COMMAND"

lerobot-record \
  --robot.type=mimic_follower \
  --robot.left_arm_port=/dev/arm_left_follower \
  --robot.right_arm_port=/dev/arm_right_follower \
  --robot.base_port=/dev/mecanum_base \
  --robot.id=mimic_follower \
  --robot.cameras='{"right_wrist": {"type": "opencv", "index_or_path": "/dev/camera_right_wrist", "width": 640, "height": 480, "fps": 30, "fourcc": "MJPG", "warmup_s": 0}, "left_wrist": {"type": "opencv", "index_or_path": "/dev/camera_left_wrist", "width": 640, "height": 480, "fps": 30, "fourcc": "MJPG", "warmup_s": 0}, "front": {"type": "opencv", "index_or_path": "/dev/camera_front", "width": 640, "height": 480, "fps": 30, "fourcc": "MJPG"}, "top": {"type": "zed_camera", "index_or_path": "23081456", "width": 1280, "height": 720, "fps": 30, "warmup_s": 0}}' \
  --teleop.type=mimic_leader \
  --teleop.left_arm_port=/dev/arm_left_leader \
  --teleop.right_arm_port=/dev/arm_right_leader \
  --teleop.base_control_mode=keyboard \
  --teleop.id=mimic_leader \
  --dataset.repo_id="Mimic-Robotics/eval_xvla_5b_30a_800k_v3" \
  --policy.path=Mimic-Robotics/xvla_odin_red_x_10a_30k \
  --dataset.single_task="$ROBOT_COMMAND" \
  --dataset.num_episodes=20 \
  --dataset.episode_time_s=180 \
  --dataset.reset_time_s=5 \
  --dataset.video=true \
  --dataset.fps=30 \
  --dataset.push_to_hub=false \
  --display_data=false

# 4. Deactivate to keep things clean (optional)
conda deactivate