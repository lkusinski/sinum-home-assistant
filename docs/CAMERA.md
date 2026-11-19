# Camera test — target HA and Sinum

Tested 2026-11-13 (Europe/Warsaw) on the target Home Assistant instance.

## Target HA generic camera

Entity: `camera.example_camera` (`Example Camera`).

| Check | Result |
|---|---|
| HA state | `idle`, `supported_features=2` (stream) |
| HA snapshot proxy `/api/camera_proxy/...` | HTTP 200, `image/jpeg`, 640×360 |
| Direct Frigate snapshot `http://frigate.local:5000/api/<camera>/latest.jpg` | HTTP 200, `image/jpeg`, 640×360 |
| RTSP from the test host | HEVC 2560×1920 @ 15 fps + AAC |
| RTSP from the HA container | HEVC 2560×1920 + AAC |
| `camera.record` 5 s | HTTP 200, MP4, duration 5.65 s |

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
| Local API `<hub-LAN-IP>` | TCP 80/443/8080/8000 closed from the test host; local API unreachable |
| Previous virtual RTSP camera test | failed with `422 NvrDeviceNotFound` (cloud limitation) |

The Sinum hub reports video capability, but there is no configured video device
visible through the cloud proxy. The local video endpoints
(`/api/v1/devices/video/{id}/snapshot` and `/stream`) cannot be tested until the
hub's local API is reachable.

## Cloud API video-parent probe

The cloud proxy exposes `POST /proxy/parent-devices/video`, but it is not a
generic RTSP/ONVIF camera endpoint:

- `type: "nvr"` requires `driver` and `user`; the allowed `driver` value is
  `p6s` (P6S-compatible NVR).
- `type: "generic"` and `type: "video_server"` return `422 NvrDeviceNotFound`
  (`id 13293`) even with a valid RTSP URL and reachable host.
- The official Sinum documentation requires the camera and the central unit to
  be in the same subnet and to support ONVIF; the test hub has no camera on its
  LAN and reports `video` capability only.

A P6S NVR is not present in this environment, so the cloud path cannot create
a Frigate camera. The local UI/API is the supported route for a normal RTSP or
ONVIF camera, but it is unreachable from the current test networks.

## Conclusion

- The target HA camera (Frigate snapshot + RTSP) works correctly and is safe for
  read-only use.
- The camera cannot be imported into Sinum through the current cloud API.
- Adding a Sinum camera entity would require either:
  1. a reachable local API and a configured hub video device, or
  2. a supported RTSP/NVR path on the hub (not a generic virtual camera).
- The existing target HA camera should remain the primary HA camera.
