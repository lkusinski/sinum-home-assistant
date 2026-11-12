# Camera test — B7 and Sinum

Tested 2026-11-13 (Europe/Warsaw) on the destination B7 instance.

## B7 Generic Camera

Entity: `camera.kamera_230_prod` (`Kamera 230 (prod)`).

| Check | Result |
|---|---|
| HA state | `idle`, `supported_features=2` (stream) |
| HA snapshot proxy `/api/camera_proxy/...` | HTTP 200, `image/jpeg`, 22,202 bytes, 640×360 |
| Direct Frigate snapshot `http://192.168.1.104:5000/api/kamera_230/latest.jpg` | HTTP 200, `image/jpeg`, 22,202 bytes, 640×360, 6 ms |
| RTSP from CT310 | HEVC 2560×1920 @ 15 fps + AAC |
| RTSP from HA container | HEVC 2560×1920 + AAC |
| `camera.record` 5 s | HTTP 200, MP4 394,066 bytes, duration 5.65 s |

The test recording was written to `/config/www` only for verification and then
removed.

`camera.stream` is not a valid service in this Home Assistant build; HA exposes
`camera.play_stream` (requires a media player) and `camera.record`. The RTSP
source and HA recording path are healthy.

## Sinum camera state

| Check | Result |
|---|---|
| Cloud `/proxy/devices/video` | `{"data":[]}` |
| Cloud `/proxy/parent-devices/video` | `{"data":[]}` |
| Central info labels | includes `video` |
| Local API `192.168.1.16` | TCP 80/443/8080/8000 closed from CT310; local API unreachable |
| Previous virtual RTSP camera test | failed with `422 NvrDeviceNotFound` (cloud limitation) |

The Sinum hub reports video capability, but there is no configured video device
visible through the cloud proxy. The local video endpoints
(`/api/v1/devices/video/{id}/snapshot` and `/stream`) cannot be tested until the
hub's local API is reachable.

## Conclusion

- The B7 camera (Frigate snapshot + RTSP) works correctly and is safe for
  read-only use.
- The camera cannot be imported into Sinum through the current cloud API.
- Adding a Sinum camera entity would require either:
  1. a reachable local API and a configured hub video device, or
  2. a supported RTSP/NVR path on the hub (not a generic virtual camera).
- The existing B7 `camera.kamera_230_prod` should remain the primary HA camera.
