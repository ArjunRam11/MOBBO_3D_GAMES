 
import numpy as np
import cv2
import time
from _mobbo_setup_utilities import*

def rotation_matrix_to_euler(rotation_matrix):
    """
    Converts a 3x3 rotation matrix to Euler angles (roll, pitch, yaw).
    """
    return cv2.RQDecomp3x3(rotation_matrix)[0]
def is_white_vectorized(image):
    """
    Vectorized function to check if pixels in an image are white.
    """
    return (image[:, :, 0] > 200) & (image[:, :, 1] > 200) & (image[:, :, 2] > 200)

def find_high_red_intensity(image_path, image_name, polygon):
    """
    Find which board's LED region is glowing in a low-exposure image.

    At exposure ~60 the image is nearly black everywhere except the lit LED.
    Instead of using an absolute brightness threshold (which fails at low
    exposure), we:
      1. Compute a *relative red score* for each LED region:
         total_red − 0.5*(total_green + total_blue)   over non-zero pixels.
      2. Also compute total brightness as a fallback.
      3. Pick the region with the highest score, as long as it has meaningful
         signal above the dark background.

    A diagnostic image is saved next to the source so alignment can be
    visually verified.
    """
    import os

    image = cv2.imread(image_path)
    if image is None:
        print(f"⚠️ find_high_red_intensity: could not read image: {image_path}")
        return []

    start_time_red_intensity = time.time()

    # Extract relevant data from polygon
    board_pos = polygon['board_3dpos'][0]
    board_rot = polygon['rotation_matrices']
    board_ids = polygon['ids'][0]

    quadrilaterals = convert_to_quadrilaterals(polygon['led_regions'])

    # Precompute rotation angles
    angles = [rotation_matrix_to_euler(rot) for rot in board_rot]

    # Precompute ROI masks
    masks = []
    for corners in quadrilaterals:
        m = np.zeros(image.shape[:2], dtype=np.uint8)
        cv2.fillPoly(m, [np.array(corners, dtype=np.int32)], 255)
        masks.append(m)

    # Extract IP address from filename (e.g. "image_led_192.168.0.102.jpg")
    _address = image_name.split("_")[-1].replace(".jpg", "").strip()

    # ── Diagnostic image: draw LED regions on the captured frame ─────────
    diag = image.copy()
    for idx, corners in enumerate(quadrilaterals):
        pts = np.array(corners, dtype=np.int32)
        cv2.polylines(diag, [pts], True, (0, 255, 0), 2)
        cx, cy = pts.mean(axis=0).astype(int)
        bid = board_ids[idx] if idx < len(board_ids) else '?'
        label = f"R{idx}"
        cv2.putText(diag, label, (cx - 10, cy - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    diag_path = image_path.replace(".jpg", "_diag.jpg")
    cv2.imwrite(diag_path, diag)
    print(f"  📸 Diagnostic image saved: {diag_path}")

    # ── Score each LED region ────────────────────────────────────────────
    # At low exposure (~60), the image is mostly dark (pixel values 0-120)
    # with ambient noise spread across all regions.  The LED itself creates
    # a small cluster of SATURATED pixels (≥200) — only the region with
    # the lit LED will have those.  So we score by:
    #   Primary:  count of bright/saturated pixels  (value ≥ SATURATION_THRESH)
    #   Tiebreak: max pixel value in the region
    SATURATION_THRESH = 200
    best_score = 0
    best_index = -1
    region_scores = []

    for i, mask in enumerate(masks):
        if i >= len(board_ids) or i >= len(board_pos) or i >= len(board_rot):
            continue

        roi = cv2.bitwise_and(image, image, mask=mask)

        # Use max across all channels — the LED may saturate any channel
        max_channel = np.max(roi, axis=2).astype(np.float64)

        mask_pixels = (mask > 0)
        saturated   = (max_channel >= SATURATION_THRESH) & mask_pixels

        n_saturated = int(np.count_nonzero(saturated))
        max_val     = float(np.max(max_channel[mask_pixels])) if np.any(mask_pixels) else 0.0
        # Sum of brightness in saturated pixels (tiebreak for similar counts)
        sat_brightness = float(np.sum(max_channel[saturated])) if n_saturated else 0.0

        # Score: saturated pixel count (primary) + tiny brightness bonus (tiebreak)
        score = n_saturated * 1000.0 + sat_brightness * 0.001

        region_scores.append((i, n_saturated, max_val, sat_brightness, score))

        if score > best_score:
            best_score = score
            best_index = i

    # Debug output
    for idx, nsat, mx, satbrt, sc in region_scores:
        bid = board_ids[idx].flatten().tolist() if hasattr(board_ids[idx], 'flatten') else board_ids[idx]
        print(f"  LED region {idx}: saturated_px={nsat}  max_val={mx:.0f}  "
              f"score={sc:.0f}  (board_id={bid})")

    result_dict = []
    best_nsat = region_scores[best_index][1] if 0 <= best_index < len(region_scores) else 0

    if best_index >= 0 and best_nsat > 0:
        result_dict.append({
            'board_translation': board_pos[best_index],
            'ip_address': _address,
            'angle': angles[best_index],
            'rotation_matrix': board_rot[best_index],
            'board_aruco_ids': board_ids[best_index]
        })
        print(f"  ✅ Matched IP {_address} → LED region {best_index} "
              f"({best_nsat} saturated pixels)")
    else:
        print(f"  ❌ No saturated pixels in any LED region for IP {_address} — "
              f"check diagnostic image: {diag_path}")

    end_time_red_intensity = time.time()
    full_time = end_time_red_intensity - start_time_red_intensity
    print(f"The red intensity execution time: {full_time:.5f} seconds")

    return result_dict


 