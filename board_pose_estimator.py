import time
import socket
import struct
from _mobbo_setup_utilities import *
from aruco_realsense_related_utils import *
from LED_Image_capture import  *
from Find_led_region import*


def _query_board_id_via_udp(ip, port=23000, retries=3, timeout=1.5):
    """
    Ask a board its hardcoded BOARD_ID by sending "Hey!mobbos".

    Packet layout (all formats — 32, 34, 36 bytes):
      byte[0] = id       (runtime, starts 0xff, changeable via SET_ID)
      byte[1] = status1  (LED/motor/stream flags)
      byte[2] = status2  = board_id  ← always the fixed hardware identity
      byte[3] = status3  (reserved)

    We read byte[2] (status2) which always equals the firmware BOARD_ID constant.
    Returns the integer board ID, or None if no response.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    board_id = None
    try:
        for _ in range(retries):
            sock.sendto(b"Hey!mobbos", (ip, port))
            try:
                data, _ = sock.recvfrom(64)
                if len(data) >= 3:
                    board_id = int(data[2])   # status2 = board_id (fixed hardware ID)
                    print(f"  [UDP fallback] {ip} → board_id={board_id} (status2)")
                    break
            except (socket.timeout, ConnectionResetError):
                continue
    finally:
        sock.close()
    return board_id


def _udp_fallback_mapping(ip_list, polygon):
    """
    Fallback IP→board mapping used only when LED algorithm fails.

    Queries each board's firmware-hardcoded BOARD_ID (byte[0] of any
    UDP packet), then looks that ID up in the ArUco polygon to obtain
    the translation, rotation matrix, and angles.

    Returns results in the same [[{...}], ...] format as board_pose().
    """
    board_pos  = polygon['board_3dpos'][0]
    board_rot  = polygon['rotation_matrices']
    board_ids  = polygon['ids'][0]
    angles     = [rotation_matrix_to_euler(rot) for rot in board_rot]

    # Build lookup: aruco_id_int → polygon index
    id_to_idx = {}
    for i, bid in enumerate(board_ids):
        aruco_id = int(np.asarray(bid).flatten()[0])
        id_to_idx[aruco_id] = i

    results = []
    for ip in ip_list:
        board_id = _query_board_id_via_udp(ip)
        if board_id is None:
            print(f"  [UDP fallback] ❌ No response from {ip}")
            continue
        if board_id not in id_to_idx:
            print(f"  [UDP fallback] ❌ board_id={board_id} from {ip} not in ArUco detections {list(id_to_idx.keys())}")
            continue
        idx = id_to_idx[board_id]
        results.append([{
            'board_translation': board_pos[idx],
            'ip_address':        ip,
            'angle':             angles[idx],
            'rotation_matrix':   board_rot[idx],
            'board_aruco_ids':   board_ids[idx]
        }])
        print(f"  [UDP fallback] ✅ {ip} → ArUco ID={board_id}")

    return results


def _ip_from_path(image_path):
    """Extract IP address string from an image filename like image_led_192.168.0.102.jpg"""
    name = image_path.replace("\\", "/").split("/")[-1]
    return name.replace("image_led_", "").replace(".jpg", "").strip()


class board_pose_estimator():

    def __init__(self):
        self.LED_Process = ImageCaptureManager()
        self.trial_no    = 1

    def board_pose(self, frame):

        self.image_paths, self.setup_image, self.polygon = \
            self.LED_Process.capture_images(frame, self.trial_no)

        # ── Primary: LED red-intensity matching ───────────────────────────
        results     = []
        failed_ips  = []

        for image_path in self.image_paths:
            if image_path is None:
                continue
            match = find_high_red_intensity(image_path, image_path, self.polygon)
            time.sleep(0.5)
            if match:
                results.append(match)
            else:
                ip = _ip_from_path(image_path)
                print(f"⚠️  LED match failed for {ip} — queuing UDP fallback")
                failed_ips.append(ip)

        # ── Fallback: only for boards where LED algorithm failed ──────────
        if failed_ips:
            print(f"🔄 Running UDP ID fallback for {len(failed_ips)} board(s): {failed_ips}")
            fallback_results = _udp_fallback_mapping(failed_ips, self.polygon)
            results.extend(fallback_results)

        if not results:
            raise ValueError(
                "Both LED matching and UDP ID fallback failed for all boards. "
                "Check board power, camera view, and network connectivity."
            )
        return results
    
if __name__ == '__main__':

    mobbo = board_pose_estimator()
    mobbo.board_pose()
