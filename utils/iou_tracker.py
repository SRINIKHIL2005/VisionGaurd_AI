from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


def _iou(a: List[int], b: List[int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    iw = max(0, inter_x2 - inter_x1)
    ih = max(0, inter_y2 - inter_y1)
    inter = iw * ih
    if inter <= 0:
        return 0.0

    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    denom = area_a + area_b - inter
    if denom <= 0:
        return 0.0
    return inter / denom


@dataclass
class Track:
    track_id: int
    bbox: List[int]
    first_seen_ts: float
    last_seen_ts: float
    hits: int = 1
    missed: int = 0


class IOUTracker:
    """Lightweight multi-object tracker using IoU matching.

    NOTE: This is not a full SORT implementation (no Kalman filter), but it provides
    stable IDs across frames which is enough for loitering/time-in-scene and basic
    behavior analytics.
    """

    def __init__(
        self,
        *,
        iou_threshold: float = 0.3,
        max_missed: int = 10,
    ):
        self.iou_threshold = float(iou_threshold)
        self.max_missed = int(max_missed)
        self._next_id = 1
        self._tracks: List[Track] = []

    def update(self, detections: List[List[int]]) -> Tuple[List[Track], Dict[int, int]]:
        """Update tracks.

        Args:
            detections: list of bboxes [x1,y1,x2,y2]

        Returns:
            (tracks, det_index_to_track_id)
        """
        now = time.time()
        det_to_track: Dict[int, int] = {}

        # Mark all tracks as missed; assigned ones will be reset
        for t in self._tracks:
            t.missed += 1

        if not self._tracks:
            for di, bbox in enumerate(detections):
                tid = self._next_id
                self._next_id += 1
                self._tracks.append(Track(track_id=tid, bbox=bbox, first_seen_ts=now, last_seen_ts=now))
                det_to_track[di] = tid
            return self._tracks.copy(), det_to_track

        # Greedy IoU assignment (good enough for small number of people)
        used_tracks = set()
        used_dets = set()

        # Build all candidate matches
        candidates: List[Tuple[float, int, int]] = []
        for ti, t in enumerate(self._tracks):
            for di, bbox in enumerate(detections):
                score = _iou(t.bbox, bbox)
                if score >= self.iou_threshold:
                    candidates.append((score, ti, di))
        candidates.sort(reverse=True, key=lambda x: x[0])

        for score, ti, di in candidates:
            if ti in used_tracks or di in used_dets:
                continue
            used_tracks.add(ti)
            used_dets.add(di)

            t = self._tracks[ti]
            t.bbox = detections[di]
            t.last_seen_ts = now
            t.hits += 1
            t.missed = 0
            det_to_track[di] = t.track_id

        # Create new tracks for unmatched detections
        for di, bbox in enumerate(detections):
            if di in used_dets:
                continue
            tid = self._next_id
            self._next_id += 1
            self._tracks.append(Track(track_id=tid, bbox=bbox, first_seen_ts=now, last_seen_ts=now))
            det_to_track[di] = tid

        # Drop tracks that have been missed too long
        self._tracks = [t for t in self._tracks if t.missed <= self.max_missed]

        return self._tracks.copy(), det_to_track

    def snapshot(self) -> List[Dict]:
        now = time.time()
        out: List[Dict] = []
        for t in self._tracks:
            out.append(
                {
                    "track_id": t.track_id,
                    "bbox": t.bbox,
                    "hits": t.hits,
                    "missed": t.missed,
                    "time_in_scene_s": round(max(0.0, now - t.first_seen_ts), 2),
                }
            )
        return out
